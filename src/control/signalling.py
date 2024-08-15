from operator import itemgetter
import functools
from functools import partial, wraps
import operator
from abc import ABC, abstractmethod
import dataclasses
from dataclasses import dataclass, is_dataclass
from collections import UserList, UserDict
from enum import Enum
import inspect
from typing import Optional, Dict, List, Callable, Any, Union, Generic, Type, MutableMapping, Mapping, Sequence, Tuple, Iterable, Protocol, runtime_checkable
import warnings

import statemachine as sm
from statemachine.states import States

import messenger
import notifier

import videorotate_constants
import videorotate_utils

TagName = str
TagValue = Union[str, int]

@dataclass
class Tag:
    name: TagName
    value: TagValue

class Command:
    class ParameterType(Enum):
        GENERATED = 0
        REQUIRED = 1
        OPTIONAL = 2
        INHERITED = 3
    
    @property
    @abstractmethod
    def command(self) -> Tag:
        pass
    
    @abstractmethod
    def task_completed(self, reply, reply_history: List[Any]) -> bool:
        pass
    
    @classmethod
    def field(cls, usage: ParameterType, **field_kwargs) -> dataclasses.Field:
        field_params = {}
        if isinstance(field_kwargs, Mapping):
            field_params = dict(field_kwargs)

        metadata = field_params.setdefault('metadata', {})
        field: dataclasses.Field = dataclasses.field(**field_params)

        metadata[Command] = {
            Command.ParameterType: usage
        }
        return field
    
    @classmethod
    def get_parameters(cls) -> Mapping[str, Tuple[Type, ParameterType]]:
        field_parameters = dataclasses.fields(cls) if is_dataclass(cls) else ()
        init_parameters = inspect.signature(cls).parameters
        
        parameter_map = {}
        # Get __init__ parameter signature first
        # so the correct field-informations are written in the next for cycle
        for name, parameter in init_parameters.items():
            parameter_map[name] = (parameter.annotation, cls.ParameterType.REQUIRED)
        
        for field in field_parameters:
            parameter_map[field.name] = (field.type, cls.get_field_usage(field))
        
        return parameter_map
    
    @staticmethod
    def get_field_usage(field: dataclasses.Field) -> Optional[ParameterType]:
        assert isinstance(field, dataclasses.Field)
        return field.metadata.get(Command, {}).get(Command.ParameterType, None)

@runtime_checkable
class ResourceBound(Protocol):
    @property
    def target_resource_id(self) -> Any:
        pass

class MessagingContext(ABC):
    @abstractmethod
    def send(self, update: Optional[Union[notifier.Update, ResourceBound]] = None) -> notifier.UpdateChannel:
        pass

# TODO: a better place
class StreamingCommand(Command, ABC):
    @abstractmethod
    def context_ended(self, reply, reply_history: List[Any]) -> bool:
        pass

# must be dataclass to work with
class Stage(ABC):
    class PARAM(Enum):
        ALL = 0
        REQUIRED = 1
        OPTIONAL = 2
    
    # TODO: documentation
    # 'init' = False
    # 'default' is None if no 'default' or 'default_factory' given
    @classmethod
    def derived_field(cls,
                      dependent_stage: Type['Stage'],
                      name: str,
                      **field_kwargs) -> dataclasses.Field:
        has_default = ('default' in field_kwargs
                       or 'default_factory' in field_kwargs)
        
        if not has_default:
            field_kwargs['default'] = None
        
        METADATA_KEY = 'metadata'
        metadata = field_kwargs.get(METADATA_KEY, {}) # get
        metadata = field_kwargs[METADATA_KEY] = dict(metadata) # convert to dict
        
        stage_metadata = metadata.setdefault(Stage, {})
        stage_metadata[Stage] = (dependent_stage, name) # source -> param_name
        
        field = dataclasses.field(**field_kwargs)
        return field
    
    @property
    @abstractmethod
    def generated_parameters(self) -> Mapping[str, Any]:
        pass
    
    @abstractmethod
    def map_result(self,
                   update: notifier.Update,
                   previous_map: Optional[Mapping[str, Any]]
                   ) -> Mapping[str, Any]:
        pass
    
    @classmethod
    def dependent_stages(cls,
                         add_indirect_dependencies: bool = False
                         ) -> Mapping[str, Type['Stage']]:
        assert is_dataclass(cls)
        
        stage_map = {}
        for field in dataclasses.fields(cls):
            direct_dep = cls.is_direct_dependency(field)
            
            if add_indirect_dependencies:
                derived_param = cls.is_derived_parameter(field)
                
                derived_dep = derived_param[0] if derived_param else None
                stage = direct_dep or derived_dep
            else:
                stage = direct_dep
            
            if stage:
                stage_map[field.name] = stage
        
        return stage_map
    
    # TODO: inherited_parameters; get generated parameters only IF inherited
    @classmethod
    def defined_parameters(cls, param_type: PARAM) -> List[str]:
        assert is_dataclass(cls)

        param_list = []
        for field in dataclasses.fields(cls):
            has_default = cls.is_required_parameter(field)
            
            applicable_parameter = (not cls.is_direct_dependency(field)
                                    and not cls.is_derived_parameter(field))
            put_parameter = ((not has_default and param_type == cls.PARAM.REQUIRED)
                             or (has_default and param_type == cls.PARAM.OPTIONAL)
                             or param_type == cls.PARAM.ALL)
            
            if applicable_parameter and put_parameter:
                param_list.append(field.name)

        return param_list
    
    # parameters that arrives as message
    @classmethod
    def derived_parameters(cls) -> Mapping[str, Tuple[Type['Stage'], str]]:
        assert is_dataclass(cls)

        parameter_map = {}
        # TODO: cleanup
        source_fields = filter(
            None,
            map(cls.is_derived_parameter, dataclasses.fields(cls))
        )

        for field in dataclasses.fields(cls):
            derived_param = cls.is_derived_parameter(field)
            
            if derived_param:
                parameter_map[field.name] = derived_param
        
        return parameter_map
    
    
    
    # preferably a generator function which selects the Commands to run
    @abstractmethod
    def command_sequence(self, *target_args, **target_kwargs) -> Optional[Iterable[Command]]:
        pass
    
    @classmethod
    def is_direct_dependency(cls,
                            field: dataclasses.Field
                            ) -> Optional[Type['Stage']]:
        assert isinstance(field, dataclasses.Field)

        if isinstance(field.type, type) and issubclass(field.type, Stage):
            return field.type
        
        # TODO
        #return cls.is_derived_parameter(field)
        return None
    
    @classmethod
    def is_derived_parameter(cls,
                             field: dataclasses.Field
                             ) -> Optional[Tuple[Type['Stage'], str]]:
        assert isinstance(field, dataclasses.Field)
        
        return field.metadata.get(Stage, {}).get(Stage, None)
    
    @classmethod
    def is_required_parameter(cls,
                             field: dataclasses.Field
                             ) -> bool:
        assert isinstance(field, dataclasses.Field)
        
        return (field.default is not dataclasses.MISSING
                or field.default_factory is not dataclasses.MISSING)


@dataclass
class CommandProgress:
    stage_inst: Stage
    command: Command
    
    @property
    def task_completed(self) -> bool:
        return self._completed

    @property
    def stage(self) -> Type[Stage]:
        return type(self.stage_inst)

    def __call__(self, update: notifier.Update) -> None:
        reply = update.value
        self._completed = self.command.task_completed(
            reply,
            self._reply_history
        )
        
        if self._completed and isinstance(update, notifier.MultiContextUpdate):
            is_streaming = isinstance(self.command, StreamingCommand)
            
            if not is_streaming or self.command.context_ended(reply, self._reply_history):
                update.context_channel.deregister_context()
        
        self._reply_history.append(reply)
    
    def __post_init__(self) -> None:
        self._reply_history = []
        self._completed = False

@dataclass
class CommandState:
    progress: CommandProgress
    channel: notifier.UpdateChannel
    stage: Stage

class BuiltCommandList(list[Command]):
    # sends CommandState
    @functools.cached_property
    def command_sent(self) -> notifier.UpdateChannel:
        return notifier.UpdateChannel()
    
    # sends CommandState
    @functools.cached_property
    def command_completed(self) -> notifier.UpdateChannel:
        return notifier.UpdateChannel()
    
    # sends CommandState
    @functools.cached_property
    def command_incomplete(self) -> notifier.UpdateChannel:
        return notifier.UpdateChannel()

# TODO: make StageProcess (as separate concept)
# TODO: unique parameter map per stage
# TODO: simplify connection between Command.task_completed and Stage.map_result
#       e.g. create a dictionary in Command.task_completed like last_map -> predicate, current_value -> predicate or somthng
@dataclass
class LinearBuilderProgress:
    controller: 'LinearStageBuilder'
    target_iterator: Union[Iterable[Tuple[Stage, Command, notifier.MultiContextChannel]], Any]
    
    target_go_immediate: dataclasses.InitVar[bool]
    
    @property
    def processed_commands(self) -> BuiltCommandList:
        return self._command_list
    
    # TODO create blocking version of updatechannel
    # TODO introduce basic Result and DelayedResult object handlers
    @functools.cached_property
    def completion_channel(self) -> notifier.UpdateChannel:
        return notifier.UpdateChannel()
    
    @functools.cached_property
    def reply_distributor(self) -> notifier.Distributor:
        return notifier.Distributor()

    def __call__(self, update: notifier.Update) -> None:
        # Call on subsequent replies
        
        # check if current task completed
        if not self.command_progress:
            return
        
        self.command_progress(update)
        
        distributor_key = type(self.command_progress.command)
        self.reply_distributor.init_channel(distributor_key, False)
        self.reply_distributor.send(
            notifier.Update(
                key=distributor_key,
                value=update.value,
                emitted_by=update.key
            )
        )
        
        command_update = notifier.Update(
            key=type(self._last_command),
            value=CommandState(
                progress=self.command_progress,
                channel=self._last_channel,
                stage=self.command_progress.stage_inst
            ),
            emitted_by=self._last_command
        )
        if self.command_progress.task_completed:
            self.processed_commands.command_completed.send(command_update)
        else:
            self.processed_commands.command_incomplete.send(command_update)
            return

        if hasattr(self.command_progress, 'unsubscribe_callback'):
            self.command_progress.unsubscribe_callback()
            pass
        
        # map result
        self.parameter_map = self.command_progress.stage_inst.map_result(
            update,
            self.parameter_map
        )
        self.controller.add_parameters(self.parameter_map)
        
        next_phrase = self._go_next_command()
        if not next_phrase:
            if not self._last_command:
                self._last_command = (None, None, None)
            stage_inst, _, channel = self.command_progress.stage_inst, self._last_command, self._last_channel
            #stage_inst, command, channel = self._last_command
            stage = type(stage_inst)
            
            self.completion_channel.send(
                # TODO simplify - do not send out stage..
                notifier.Update(
                    key=stage,
                    value=self.parameter_map,
                    emitted_by=stage_inst
                )
            )
        else:
            _, self._last_command, self._last_channel = next_phrase
            #self._last_command = next_command
            
            ctrl = self.controller
            
            stage_inst, command, channel = next_phrase
            stage = type(stage_inst)
            
            stage_state = ctrl.stage_state(stage)
            stage_state.process_channel = channel

    def go(self):
        if not self._target_init_done:
            self._target_init_done = True
            self._go_next_command()

    def __post_init__(self, target_go_immediate: bool) -> None:
        self.parameter_map = None
        self.command_progress = None
        self._last_command = None
        self._last_channel = None
        
        self._command_list = BuiltCommandList()
        
        self._target_init_done = False
        
        
        if target_go_immediate:
            self.go()
    
    def _go_next_command(self) -> Optional[Tuple[Stage, Command, notifier.UpdateChannel]]:
        ctrl = self.controller
        try:
            if not isinstance(self.target_iterator, Iterable):
                raise StopIteration
            stage_inst, command, channel = next(self.target_iterator)
            stage = type(stage_inst)

            ctrl.stage_state(stage).reached = True
            ctrl.stage_state(stage).latest_instance = stage_inst
            
            if isinstance(command, ResourceBound):
                ctrl.stage_state(stage).resource_id = command.target_resource_id
            
            
            if self.command_progress is not None and stage != self.command_progress.stage:
                # stage ending
                ctrl.stage_state(self.command_progress.stage).exhausted = True

            self.command_progress = CommandProgress(stage_inst, command)

            subscribe_handler = self
            self.command_progress.unsubscribe_callback = partial(
                channel.unsubscribe, subscribe_handler)
            channel.subscribe(subscribe_handler)
            
            cmd_state = CommandState(
                progress=self.command_progress,
                channel=channel,
                stage=stage_inst
            )
            self._command_list.append(cmd_state)
            self._command_list.command_sent.send(
                notifier.Update(
                    key=type(command),
                    value=cmd_state,
                    emitted_by=command
                )
            )
            # send notify after parameters has been published
            ctrl.stage_state(stage).command_notify.send(
                notifier.Update(
                    key=type(command),
                    value=command,
                    emitted_by=stage_inst
                )
            )
            
            return stage_inst, command, channel

        except StopIteration:
            if self.command_progress is not None:
                # stage ending
                ctrl.stage_state(self.command_progress.stage).exhausted = True
        
        return None

# TODO: make the distinction between add_parameters and generated parameters, when to use which
# TODO: refactoring: separate the controller storage and operational parts
class LinearStageBuilder:
    PARAMETER_GENERATED = 'generated'
    
    @dataclass
    class StageState:
        reached: bool = False
        exhausted: bool = False
        latest_instance: Optional[Stage] = None
        resource_id: Optional[Any] = None
        
        command_notify: notifier.UpdateChannel = dataclasses.field(default_factory=notifier.UpdateChannel)
        
    
    @property
    def messaging_context(self) -> MessagingContext:
        return self._messaging_context
    
    @functools.cached_property
    def _target_parameters(self) -> MutableMapping[Union[Type[Stage], None], MutableMapping[str, Any]]:
        return {}
    
    def __init__(self, context: MessagingContext) -> None:
        self._messaging_context = context
        
        # self._stage_state[init_params] = {<Stage>: <StageState>,...}
        self._stage_state = {}
    
    def add_parameters(self, parameters: Mapping[str, Any], bind_stage: Optional[Stage] = None):
        container = self._target_parameters.setdefault(bind_stage, {})
        container.update(parameters)
    
    # TODO: proper documentation
    # TODO: check available parameters before activating stage
    def set_target(self, stage: Type[Stage], *target_args, target_go_immediate: bool = True, **target_kwargs) -> LinearBuilderProgress:
        sender_iterator = self._go_target(stage, target_args, target_kwargs)

        return LinearBuilderProgress(self, sender_iterator, target_go_immediate)
    
    # TODO: delete fn
    

    def _go_target(self,
                   stage: Type[Stage],
                   target_args: Tuple,
                   target_kwargs: Mapping
                   ) -> Iterable[Tuple[Stage, Command, notifier.UpdateChannel]]:
        # states_reached = map(operator.attrgetter('reached'), self._stage_state.values())
        # if any(states_reached):
        #     states = []
        #     order = self._generate_order([stage])

        for stage_inst, parameter_mapping in self._build_stage(stage):
            cmd_iterator = stage_inst.command_sequence(*target_args, **target_kwargs)

            for command in cmd_iterator:
                update = notifier.MultiContextUpdate(
                    key=Command.__name__,
                    value=command,
                    emitted_by=stage
                )
                channel = self.messaging_context.send()
                update.context_channel = channel
                
                channel.send(update)
                yield stage_inst, command, channel
    
    
    # current_stage, stage_parameter_mapping, next_stage
    def _build_stage(self, stage: Type[Stage]) -> Iterable[Tuple[Stage, Mapping[Union[Type[Stage], None], Mapping[str, Any]]]]:
        # load global and stage-dependent parameters
        mapping = self._target_parameters
        # mapping = videorotate_utils.OverlayDict()
        # mapping.set_roots(self._target_parameters)
        #mapping = {stage: dict(params) for stage, params in self._target_parameters.items()}
        #mapping.setdefault(None, {})
        
        # search stages and build them
        for stage in self.generate_order([stage]):
            stage_mapping = mapping.setdefault(stage, {})
            
            # skip if stage has instance
            if stage in stage_mapping:
                continue
            
            stage_environment = dict(mapping.get(None, {}))
            stage_environment.update(stage_mapping)
            
            # TODO: add parameter only if inherited
            stage_params = {param: stage_environment[param]
                            for param in stage.defined_parameters(stage.PARAM.REQUIRED)}
            
            stage_params.update({param: stage_environment[param]
                                 for param in stage.defined_parameters(stage.PARAM.OPTIONAL)
                                 if param in stage_environment})
            
            for name, dependent_stage in stage.dependent_stages().items():
                stage_params[name] = mapping[dependent_stage][dependent_stage]
            
            
            for field_name, dependency in stage.derived_parameters().items():
                dependent_stage, dependent_name = dependency
                
                parameter = mapping[dependent_stage][self.PARAMETER_GENERATED].get(dependent_name, None)
                parameter = parameter or mapping[dependent_stage].get(dependent_name, None)
                parameter = parameter or mapping[None].get(dependent_name, None)
                
                if field_name not in stage_params or (stage_params[field_name] is None and parameter is not None):
                    stage_params[field_name] = parameter
                
            
            assert stage not in stage_mapping
            stage_inst = stage(**stage_params)
            
            stage_mapping[stage] = stage_inst
            stage_mapping[self.PARAMETER_GENERATED] = stage_inst.generated_parameters()
            
            yield stage_inst, mapping
    
    
    # TODO: check if works with .cache
    #@functools.cached_property
    def generate_order(self,
                        stage_list: Sequence[Type[Stage]]
                        ) -> Sequence[Type[Stage]]:
        level_table = self._dependency_lookup(stage_list, [])
        
        reverse_ordered = sorted(
            level_table.items(),
            key=lambda item: item[1],
            reverse=True
        )
        
        return [stage for stage,level in reverse_ordered]
    
    def _dependency_lookup(self,
                           stage_list: Sequence[Type[Stage]],
                           parent_path: List[Type[Stage]]
                           ) -> MutableMapping[Type[Stage], int]:
        level_table = {}
        
        for stage in stage_list:
            if stage in parent_path:
                raise LookupError(f"Recursive dependency graph: {stage} in path {parent_path}")
            stage_path = parent_path.copy()
            stage_path.append(stage)
            
            level_table.update(
                self._dependency_lookup(
                    stage.dependent_stages(True).values(),
                    stage_path
                )
            )
            
            level = len(stage_path)
            in_list = stage in level_table
            if (in_list and level_table[stage] < level) or not in_list:
                level_table[stage] = len(stage_path)
        
        return level_table

    def stage_state(self, stage) -> StageState:
        return self._stage_state.setdefault(stage, self.StageState())


    def _is_derived_parameters_received(self, next_stage: Type[Stage]) -> bool:
        global_stage_params = self._target_parameters.get(None)
        specific_stage_params = self._target_parameters.get(next_stage)
        
        
        is_param_in = partial(operator.contains, self._target_parameters.values())
        
        return all(map(is_param_in, next_stage.derived_parameters()))
