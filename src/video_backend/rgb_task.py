import os
import os.path
import glob
from dataclasses import dataclass, field, InitVar
import functools
from functools import cache
import datetime
import itertools
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional, Union, MutableMapping, List, Sequence, Iterable
import importlib

from valkka.core import ForkFrameFilterN
from control.generic_resource import Result, DelayedResult

import video_backend.rtsp.filterchain as filterchain

import messaging.topic as topic
from backend_context import ProcessBoundTask, BackendProcessContext, BackendProcess, CallbackBasedTask, GeneratedProcessTask

from IFrameProcessAdapter import IFrameProcessAdapter

from video_backend.consumer import Consumer, RGBSharedMemoryImage, RecorderControl

from video_backend.processing.register_bgr_transform import get_bgr_transform, list_bgr_transforms

from backend_context import PropertyObserverTask

import control.generic_resource as generic_resource
from control.generic_resource import CreateCommand, StartCommand, StopCommand, DeleteCommand, ResultVector
import control.signalling as signalling
import notifier

import backend_context

CommandField = signalling.Command.field
CommandType = signalling.Command.ParameterType

# Patch
import video_backend.processing.preview

@dataclass
class Filename:
    dirname: Optional[str]
    filename_parts: List[str]
    filename_part_delimiter: List[str]
    file_extension: str
    
    def __str__(self):
        filename_base = ''
        delim_list = self.filename_part_delimiter
        
        last_delim = delim_list[-1] if len(delim_list) else ''
        last_index = len(self.filename_parts)-1
        
        fn_iter = itertools.zip_longest(self.filename_parts, delim_list)
        for i, (fn_part, delimiter) in enumerate(fn_iter):
            if fn_part is None:
                break
            if delimiter is None:
                delimiter = last_delim
            
            if i == last_index:
                filename_base += f"{fn_part}"
            else:
                filename_base += f"{fn_part}{delimiter}"
        
        filename_base += f".{self.file_extension}"
        
        if self.dirname is not None:
            return os.path.join(self.dirname, filename_base)
        else:
            return filename_base

@dataclass
class CurrentRecording:
    filepath: Optional[str]
    started: bool
    finished: bool
    property_id: str

@dataclass
class RecorderRemoteStatus:
    source_property: notifier.KeyId
    fn_builder_iterable: Iterable
    recording_status: CurrentRecording
    activation_channel: notifier.UpdateChannel = field(default_factory=notifier.UpdateChannel)
    

class ReceiverBootstrapControl(GeneratedProcessTask):
    def create_process(self) -> Consumer:
        consumer = Consumer()
        consumer.messenger_timeout_sec = 1.0
        return consumer
    
    @property
    def target_resource_id(self) -> Any:
        return self.process_id


class ReceiverDerivativeControl(ProcessBoundTask):
    def create_process(self) -> Consumer:
        raise RuntimeError
    
    @property
    def target_resource_id(self) -> Any:
        return self.process_id


class ReceiverControlBase(generic_resource.ControlTask):
    def allocate(self, context: BackendProcessContext) -> ResultVector:
        consumer: Consumer = self.backend__process
        consumer.adapter = self.adapter_factory(**self.adapter_parameters)

        return True

    def start(self, context: BackendProcessContext) -> ResultVector:
        consumer: Consumer = self.backend__process
        consumer.backend__start_processing()

        return True

    def stop(self, context: BackendProcessContext) -> ResultVector:
        # ...
        raise NotImplementedError
        return False

    def delete(self, context: BackendProcessContext) -> ResultVector:
        # ...
        raise NotImplementedError
        return False

    @property
    def backend__resource_id(self) -> Any:
        return ReceiverControlBase


@dataclass
class Receiver_Create(CreateCommand, ReceiverControlBase, ReceiverBootstrapControl):
    adapter_factory: Callable = CommandField(CommandType.REQUIRED)
    adapter_parameters: Dict = CommandField(CommandType.REQUIRED)


@dataclass
class Receiver_Start(StartCommand, ReceiverControlBase, ReceiverDerivativeControl):
    pass


@dataclass
class Receiver_Stop(StopCommand, ReceiverControlBase, ReceiverDerivativeControl):
    pass


@dataclass
class Receiver_Delete(DeleteCommand, ReceiverControlBase, ReceiverDerivativeControl):
    pass



class FilterControlBase(generic_resource.ControlTask):
    IMPORTED_MODULE_BASE = 'video_backend.processing'

    def allocate(self, context: BackendProcessContext) -> ResultVector:
        process: Consumer = self.backend__process

        # import neccessary module so filter will register itself
        # importlib.import_module(
        #     '.'.join([self.IMPORTED_MODULE_BASE, self.module_name]))

        filter_cb = get_bgr_transform(self.filter)
        filter_search = process.backend__filter_tree.get_filter_by_id(
            self.filter_id)

        if filter_search:
            filter_obj: Dict = filter_search['filter_obj']

            filter_obj.update(self.filter_run_parameters)
        else:
            process.backend__filter_tree.add_filter(
                self.filter_id,
                self.parent_id,
                {
                    'filter': self.filter,
                    'filter_obj': filter_cb,
                    'filter_parameters': self.filter_run_parameters or {}
                }
            )

        return True

    def start(self, context: BackendProcessContext) -> ResultVector:
        # ...
        return True

    def stop(self, context: BackendProcessContext) -> ResultVector:
        # ...
        return True

    def delete(self, context: BackendProcessContext) -> ResultVector:
        process: Consumer = self.backend__process
        filter_search = process.backend__filter_tree.get_filter_by_id(
            self.filter_id)

        if filter_search:
            process.backend__filter_tree.delete_filter(self.filter_id)
            return True
        return False

    @property
    def backend__resource_id(self) -> Any:
        return tuple([FilterControlBase, self.filter_id])


@dataclass
class Filter_Create(CreateCommand, FilterControlBase, ReceiverDerivativeControl):
    filter_id: Any = CommandField(CommandType.REQUIRED)
    parent_id: Any = CommandField(CommandType.REQUIRED)
    filter: str = CommandField(CommandType.REQUIRED)
    # under video_backend.processing
    module_name: str = CommandField(CommandType.REQUIRED)
    filter_run_parameters: Optional[Dict[str, Any]
                                    ] = CommandField(CommandType.REQUIRED, default=None)
    
    @classmethod
    def available_filters(cls) -> Sequence[Any]:
        cur_module_dir = os.path.dirname(__file__)
        relative_module_path = os.path.join(*__name__.split('.')[:-1])
        
        root_module_path = cur_module_dir.rstrip(relative_module_path)
        
        filter_relative_path = cls.IMPORTED_MODULE_BASE.replace('.', os.path.sep)
        filter_root_path = os.path.join(root_module_path, filter_relative_path)
        
        for py_file in glob.glob(os.path.join(filter_root_path, '*.py')):
            py_module = os.path.basename(py_file).rstrip('.py')
            
            # if py_module != '__init__':
            #     importlib.import_module('.'.join([cls.IMPORTED_MODULE_BASE, py_module]))
        
        return list_bgr_transforms()


@dataclass
class Filter_Start(StartCommand, FilterControlBase, ReceiverDerivativeControl):
    filter_id: Any = CommandField(CommandType.INHERITED)


@dataclass
class Filter_Stop(StopCommand, FilterControlBase, ReceiverDerivativeControl):
    filter_id: Any = CommandField(CommandType.INHERITED)


@dataclass
class Filter_Delete(DeleteCommand, FilterControlBase, ReceiverDerivativeControl):
    filter_id: Any = CommandField(CommandType.INHERITED)


# TODO
# valamelyik módszert - generated params vagy add_parameters - ki kéne dobni, vagy meghatározni, hogy futás közben mit engedünk
# TODO: not getting Start reply. Maybe the DelayedResultSource type is the problem?
class FilterTerminalControlBase(generic_resource.ControlTask):
    def allocate(self, context: BackendProcessContext) -> ResultVector:
        # NOT TODO: move back the terminal initialization snippet
        process: Consumer = self.backend__process
        process.backend__request_filter_output(self.filter_id)

        return True

    def start(self, context: BackendProcessContext) -> ResultVector:
        return generic_resource.DelayedResultSource(
            status=generic_resource.DelayedResult(
                status=generic_resource.Status.OK,
                resource_change=True
            ),
            control_callback=self._filter_send_out,
            send_immediate_result=False
        )

    def stop(self, context: BackendProcessContext) -> ResultVector:
        process: Consumer = self.backend__process
        process.backend__revoke_filter_output(self.shmem_image, False)
        return True

    def delete(self, context: BackendProcessContext) -> ResultVector:
        process: Consumer = self.backend__process
        process.backend__revoke_filter_output(self.shmem_image, True)
        return True

    def _filter_send_out(self, control: topic.ReplyControl):
        process: Consumer = self.backend__process
        process.backend__send_filter_output_when_ready(control, self.filter_id)

    @property
    def backend__resource_id(self) -> Any:
        return tuple([FilterTerminalControlBase, self.filter_id])


@dataclass
class FilterTerminal_Create(CreateCommand, FilterTerminalControlBase, ReceiverDerivativeControl):
    filter_id: Any = CommandField(CommandType.REQUIRED)


@dataclass
class FilterTerminal_Start(StartCommand, FilterTerminalControlBase, ReceiverDerivativeControl):
    filter_id: Any = CommandField(CommandType.INHERITED)
    
    def task_completed(self, reply, reply_history: List[Any]) -> bool:
        if not len(reply_history):
            return False

        basic_check = (isinstance(reply_history[0], (Result, DelayedResult))
                       and reply_history[0].status == generic_resource.Status.OK)
        has_image = isinstance(reply, RGBSharedMemoryImage)
        return basic_check and has_image
        


@dataclass
class FilterTerminal_Stop(StopCommand, FilterTerminalControlBase, ReceiverDerivativeControl):
    filter_id: Any = CommandField(CommandType.INHERITED)
    shmem_image: RGBSharedMemoryImage = CommandField(CommandType.REQUIRED)


@dataclass
class FilterTerminal_Delete(DeleteCommand, FilterTerminalControlBase, ReceiverDerivativeControl):
    filter_id: Any = CommandField(CommandType.INHERITED)
    shmem_image: RGBSharedMemoryImage = CommandField(CommandType.INHERITED)



class RecorderControlBase(generic_resource.ControlTask):
    @property
    def control(self) -> RecorderControl:
        context = self.backend__process.context
        return context[RecorderControlBase][self.input_filter_id]

    def allocate(self, context: BackendProcessContext) -> ResultVector:
        self.backend__process: Consumer
        context.setdefault(RecorderControlBase, {})

        print('TEMPP')
        recorder = RecorderControl(self.fps, self.recording_dir)
        recorder.recording_dir = self.recording_dir
        recorder.recording_basename = self.recording_basename

        context[RecorderControlBase][self.input_filter_id] = recorder
        
        self.backend__process.backend__save_stream_to_file(self.input_filter_id, self.control)
        return True

    def start(self, context: BackendProcessContext) -> ResultVector:
        if not self.build_only:
            self.control.activate()
        return True

    def stop(self, context: BackendProcessContext) -> ResultVector:
        self.control.deactivate()
        return True

    def delete(self, context: BackendProcessContext) -> ResultVector:
        del context[RecorderControlBase][self.input_filter_id]
        return True

    @property
    def backend__resource_id(self) -> Any:
        return tuple([RecorderControlBase, self.input_filter_id])


@dataclass
class Recorder_Create(CreateCommand, RecorderControlBase, ReceiverDerivativeControl):
    input_filter_id: Any = CommandField(CommandType.REQUIRED)
    fps: int = CommandField(CommandType.REQUIRED)
    recording_dir: Optional[str] = CommandField(CommandType.REQUIRED)
    recording_basename: str = CommandField(CommandType.REQUIRED, default='video')


@dataclass
class Recorder_Start(StartCommand, RecorderControlBase, ReceiverDerivativeControl):
    input_filter_id: Any = CommandField(CommandType.INHERITED)
    build_only: bool = True

@dataclass
class Recorder_Stop(StopCommand, RecorderControlBase, ReceiverDerivativeControl):
    input_filter_id: Any = CommandField(CommandType.INHERITED)


@dataclass
class Recorder_Delete(DeleteCommand, RecorderControlBase, ReceiverDerivativeControl):
    input_filter_id: Any = CommandField(CommandType.INHERITED)


class RecorderRemoteControlBase(generic_resource.ControlTask):
    @property
    def backend__activation_channel(self) -> notifier.UpdateChannel:
        base = self.backend__process.context.setdefault(RecorderRemoteControlBase, {})
        return base[self.input_filter_id].activation_channel
    
    @property
    def backend__current_recording(self) -> CurrentRecording:
        base = self.backend__process.context.setdefault(RecorderRemoteControlBase, {})
        return base[self.input_filter_id].recording_status
    
    @property
    def recorder_control(self) -> RecorderControl:
        context = self.backend__process.context
        return context[RecorderControlBase][self.input_filter_id]
    
    @property
    def metadata(self) -> RecorderRemoteStatus:
        context = self.backend__process.context
        return context[RecorderRemoteControlBase][self.input_filter_id]

    def allocate(self, context: BackendProcessContext) -> ResultVector:
        base = context.setdefault(RecorderRemoteControlBase, {})
        
        base[self.input_filter_id] = metadata = RecorderRemoteStatus(
            source_property=self.input_filter_id,
            fn_builder_iterable=self.date_iterable(),
            recording_status=CurrentRecording(None, False, False, '')
        )
        
        return True

    def start(self, context: BackendProcessContext) -> ResultVector:
        self.backend__process: Consumer
        self.backend__activation_channel.subscribe(self.backend__handle_update)
        
        if self.start_recording:
            self.backend__activation_channel.send(
                notifier.Update(
                    key=RecorderRemoteControlBase,
                    value=True
                )
            )
        return True

    def stop(self, context: BackendProcessContext) -> ResultVector:
        if self.stop_recording:
            self.backend__activation_channel.send(
                notifier.Update(
                    key=RecorderRemoteControlBase,
                    value=False
                )
            )
        
        self.backend__activation_channel.unsubscribe(self.backend__handle_update)
        return True

    def delete(self, context: BackendProcessContext) -> ResultVector:
        # del context[RecorderRemoteControlBase][self.input_filter_id]
        # ...
        raise NotImplementedError
        return True

    
    def backend__handle_update(self, update: notifier.Update):
        record = self.backend__current_recording
        change = update.extract_nested_value()
        
        if (change and record.started and not record.finished) or (not change and record.finished):
            return
        
        if change:
            record.started = True
            record.finished = False

            
            record.filepath = os.path.join(
                str(self.recorder_control.recording_dir),
                str(self.generate_filename(change))
            )
            self.recorder_control.activate(record.filepath)
        else:
            self.recorder_control.deactivate()

            record.finished = True

    @property
    def property_id(self) -> Any:
        return self.backend__current_recording.property_id

    @property_id.setter
    def property_id(self, property_id: Any) -> None:
        self.backend__current_recording.property_id = property_id

    def generate_filename(self, change: Any) -> str:
        return str(self.assemble_filename(next(self.metadata.fn_builder_iterable)))

    @property
    def backend__resource_id(self) -> Any:
        return tuple([RecorderRemoteControlBase, self.input_filter_id])
    
    def date_iterable(self) -> Iterable[str]:
        while True:
            path = datetime.datetime.today().strftime('%Y-%m-%d_%H-%M-%S')
            path_modded = None
            
            counter = itertools.count()
            next(counter) # +1
            while os.path.exists(str(self.assemble_filename(path_modded or path, True))):
                path_modded = f"{path}.{next(counter)}"
            
            yield path_modded or path
    
    def assemble_filename(self, unique_part: str, absolute_path: bool = False) -> Filename:
        return Filename(
            self.recorder_control.recording_dir,
            [
                self.recorder_control.recording_basename,
                unique_part
            ],
            ['_'],
            self.recorder_control.filename_extension
        )


@dataclass
class RecorderRemote_Create(CreateCommand, RecorderRemoteControlBase, ReceiverDerivativeControl):
    input_filter_id: Any = CommandField(CommandType.REQUIRED)
    backend_source_property: notifier.KeyId = CommandField(
        CommandType.REQUIRED)

    # fps: Optional[int] = None
    # recording_dir: Optional[str] = None
    # recording_basename: Optional[str] = None


@dataclass
class RecorderRemote_Start(StartCommand, RecorderRemoteControlBase, ReceiverDerivativeControl):
    input_filter_id: Any = CommandField(CommandType.INHERITED)
    start_recording: bool = True


@dataclass
class RecorderRemote_Stop(StopCommand, RecorderRemoteControlBase, ReceiverDerivativeControl):
    input_filter_id: Any = CommandField(CommandType.INHERITED)
    stop_recording: bool = True


@dataclass
class RecorderRemote_Delete(DeleteCommand, RecorderRemoteControlBase, ReceiverDerivativeControl):
    input_filter_id: Any = CommandField(CommandType.INHERITED)


@dataclass
class FilterParameterChangeCommand(backend_context.BackendTask, signalling.Command):
    filter_id: Any = CommandField(CommandType.REQUIRED)
    filter_run_parameters: Optional[Dict[str, Any]
                                    ] = CommandField(CommandType.REQUIRED)
    
    target_resource_id: Any = CommandField(CommandType.REQUIRED)
    
    def command(self) -> signalling.Tag:
        return signalling.Tag('process', 'filter_parameters_change')

    def task_completed(self, reply, reply_history: List[Any]) -> bool:
        return reply

    def run(self, control: backend_context.ReplyControl, process: Consumer) -> Any:
        assert isinstance(process, Consumer)
        
        filter_search = process.backend__filter_tree.get_filter_by_id(
            self.filter_id)

        if filter_search:
            filter_obj: Dict = filter_search['filter_obj']['filter_parameters']

            filter_obj.update(self.filter_run_parameters)
        else:
            raise LookupError(f"Filter {self.filter_id} not found")
        
        control.reply_to_message = True
        return True
    
    def create_process(self) -> Consumer:
        raise RuntimeError
    
