from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import functools
from functools import partial
from enum import Enum
from typing import Callable, Optional, Any, Union, Mapping, NewType, List
from multiprocessing import Process, current_process

import statemachine as sm
from statemachine.states import States

#from backend_context import BackendProcess
import control.signalling as signalling

from videorotate_utils import print_exception, log_context
from messaging.topic import TopicMessaging, MessageThreadRegistry, ReplyControl, SentMessage



from backend_context import BackendTask, BackendProcessContext

import videorotate_utils

class Status(Enum):
    OK = 0
    FAILED = 1


@dataclass
class Result:
    status: Status
    resource_change: bool
    additional_data: Any

# Means 'next message is related to this context'
@dataclass
class DelayedResult:
    status: Status
    resource_change: bool
    immediate_result: Any = None

@dataclass
class DelayedResultSource:
    status: DelayedResult
    control_callback: Callable[[ReplyControl], Any]
    send_immediate_result: bool


ResultVector = Optional[Union[Result, DelayedResultSource, bool]]

ProcessTagName = 'process'
class Command(Enum):
    ALLOCATE = signalling.Tag(ProcessTagName, 'allocate')
    START = signalling.Tag(ProcessTagName, 'start')
    STOP = signalling.Tag(ProcessTagName, 'stop')
    DELETE = signalling.Tag(ProcessTagName, 'delete')

class CreateCommand(signalling.Command): command = Command.ALLOCATE.value
class StartCommand(signalling.Command): command = Command.START.value
class StopCommand(signalling.Command): command = Command.STOP.value
class DeleteCommand(signalling.Command): command = Command.DELETE.value

class StateList(Enum):
    created = 'Created'
    allocated = 'Allocated'
    started = 'Started'
    stopped = 'Stopped'
    removed = 'Removed'


class StateMachine(sm.StateMachine):
    # States from StateList
    states = States.from_enum(StateList, initial=StateList.created, final=StateList.removed)
    
    # Call these functions when desired
    allocate = states.created.to(states.allocated)
    start = states.allocated.to(
        states.started) | states.stopped.to(states.started)
    stop = states.started.to(states.stopped)
    delete = states.created.to(states.removed) | states.allocated.to(
        states.removed) | states.stopped.to(states.removed)

# Control Resource Lifecycle
# TODO: Enhancement: make a getter for the context[ControlTask] if possible - store certain tasks instead of using context[] storage
class ControlTask(BackendTask, signalling.Command, ABC):
    @property
    def backend__process(self):#) -> BackendProcess:
        return self.__backend__process
    
    class State(StateMachine):
        # Proxy functions
        def on_allocate(self, control_task):
            assert isinstance(control_task, ControlTask)

            return control_task.allocate(context=control_task.backend__process.context)

        def on_start(self, control_task):
            assert isinstance(control_task, ControlTask)

            return control_task.start(context=control_task.backend__process.context)

        def on_stop(self, control_task):
            assert isinstance(control_task, ControlTask)

            return control_task.stop(context=control_task.backend__process.context)

        def on_delete(self, control_task):
            assert isinstance(control_task, ControlTask)

            return control_task.delete(context=control_task.backend__process.context)

    @abstractmethod
    def allocate(self, context: BackendProcessContext) -> ResultVector:
        pass

    @abstractmethod
    def start(self, context: BackendProcessContext) -> ResultVector:
        pass

    @abstractmethod
    def stop(self, context: BackendProcessContext) -> ResultVector:
        pass

    @abstractmethod
    def delete(self, context: BackendProcessContext) -> ResultVector:
        pass
    
    # Give ControlTask a process-level unique id for bookkeeping
    @property
    @abstractmethod
    def backend__resource_id(self) -> Any:
        pass
    
    # default result mapping
    def task_completed(self, reply, reply_history: List[Any]) -> bool:
        return isinstance(reply, (Result, DelayedResult)) and reply.status == Status.OK

    # Masks StateMachine's disambiguous behavior on function return values
    def _run_command(self,
                     resource_state: State,
                     command: str) -> Optional[Union[Result, DelayedResultSource, bool]]:
        def is_result_type(data): return isinstance(data, (Result, DelayedResultSource, bool))

        transition_result = resource_state.send(command, control_task=self)

        if transition_result is None or is_result_type(transition_result):
            return transition_result

        # Try to iterate through
        try:
            for output in transition_result:
                if is_result_type(output):
                    return output
        except TypeError:
            import sys
            print('TypeError')
            sys.stdout.flush()
            pass

        return None

    def run(self, control: ReplyControl, process) -> Result: #: BackendProcess) -> Result:
        self.__backend__process = process
        context = process.backend__context

        context.setdefault(ControlTask, {})
        resource_state: self.State = context[ControlTask].setdefault(self.backend__resource_id, self.State())

        control.reply_to_message = True
        error_obj = None
        # Run command
        try:
            command_tag = self.command
            
            result = self._run_command(resource_state, str(command_tag.value))
            reply = None
            if isinstance(result, Result):
                reply = result
            
            elif isinstance(result, DelayedResultSource):
                res = result.control_callback(control)
                
                if result.send_immediate_result:
                    result.status.immediate_result = res
                
                control.keep_control = True
                reply = result.status
            
            elif isinstance(result, bool) or result is None:
                if result or result is None:
                    reply = Result(Status.OK, True, None)
                else:
                    reply = Result(Status.FAILED, False, None)
            
            is_removed = resource_state.current_state == StateMachine.states.removed
            if reply is not None:
                if is_removed and reply.status == Status.OK:
                    del context[ControlTask][self.backend__resource_id]
                
                return reply

        except sm.StateMachine.TransitionNotAllowed as e:
            import sys
            print('Error:', e, self)
            sys.stdout.flush()
            error_obj = e
            pass
        return Result(Status.FAILED, False, str(error_obj))

