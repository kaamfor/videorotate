from dataclasses import dataclass, field
from typing import Any, Optional, Union

from valkka.core import ForkFrameFilterN

from video_backend.rtsp.filterchain import FilterchainNetworkSource, IFilterchainSource, RTSPStreamSpec, FilterchainDecoder, DecoderSpec, RGBDecodingTerminalData, RGBDecodingTerminalComponents, RGBDecodingTerminal, SourceSpec#, FilterchainRecorder

from messaging.topic import TopicMessaging, MessageThreadRegistry, ReplyControl, SentMessage
from backend_context import ProcessBoundTask, BackendProcessContext, BackendProcess, TaskProcess, GeneratedProcessTask
import control.generic_resource as generic_resource
from control.generic_resource import CreateCommand, StartCommand, StopCommand, DeleteCommand, ResultVector
import control.signalling as signalling

CommandField = signalling.Command.field
CommandType = signalling.Command.ParameterType

class ReceiverBootstrapControl(GeneratedProcessTask):
    def create_process(self) -> TaskProcess:
        return TaskProcess()
    
    @property
    def target_resource_id(self) -> Any:
        return self.process_id

class ReceiverDerivativeControl(ProcessBoundTask):
    def create_process(self) -> BackendProcess:
        raise RuntimeError
    
    @property
    def target_resource_id(self) -> Any:
        return self.process_id


class ReceiverControlBase(generic_resource.ControlTask):
    def allocate(self, context: BackendProcessContext) -> ResultVector:
        receiver = context[ReceiverControlBase] = self.source.create()
        context['filter_forks'] = {}
        return True
    
    def start(self, context: BackendProcessContext) -> ResultVector:
        receiver: IFilterchainSource = context[ReceiverControlBase]
        
        receiver.start()
        return True
    
    def stop(self, context: BackendProcessContext) -> ResultVector:
        receiver: IFilterchainSource = context[ReceiverControlBase]

        receiver.stop()
        return True
    
    def delete(self, context: BackendProcessContext) -> ResultVector:
        del context[ReceiverControlBase]
        return True
    
    @property
    def backend__resource_id(self) -> Any:
        return ReceiverControlBase

@dataclass
class Receiver_Create(CreateCommand, ReceiverControlBase, ReceiverBootstrapControl):
    source: SourceSpec = CommandField(CommandType.REQUIRED)

@dataclass
class Receiver_Start(StartCommand, ReceiverControlBase, ReceiverDerivativeControl):
    pass

@dataclass
class Receiver_Stop(StopCommand, ReceiverControlBase, ReceiverDerivativeControl):
    pass

@dataclass
class Receiver_Delete(DeleteCommand, ReceiverControlBase, ReceiverDerivativeControl):
    pass


class DecoderControlBase(generic_resource.ControlTask):
    def allocate(self, context: BackendProcessContext) -> ResultVector:
        assert isinstance(self.decoder, DecoderSpec)

        decoder = self.decoder.create()
        
        source: IFilterchainSource = context[ReceiverControlBase]
        input_fork = source.root_fork
        if self.input_filter_id is not None:
            input_fork = context['filter_forks'][self.input_filter_id]
        
        # TODO: modify tag name
        input_fork.connect(str(id(source))+str(id(decoder)), decoder.input_framefilter)
        
        context[self.decoder_id] = decoder
        return True

    def start(self, context: BackendProcessContext) -> ResultVector:
        decoder: FilterchainDecoder = context[self.decoder_id]

        decoder.start_decoder_thread(True)
        return True

    def stop(self, context: BackendProcessContext) -> ResultVector:
        decoder: FilterchainDecoder = context[self.decoder_id]

        decoder.kill_decoder()
        return True

    def delete(self, context: BackendProcessContext) -> ResultVector:
        del context[self.decoder_id]
        return True
    
    @property
    def backend__resource_id(self) -> Any:
        return tuple([DecoderControlBase, self.decoder_id])

@dataclass
class Decoder_Create(CreateCommand, DecoderControlBase, ReceiverDerivativeControl):
    decoder: DecoderSpec = CommandField(CommandType.REQUIRED)
    input_filter_id: Any = CommandField(CommandType.REQUIRED) # None = root filter
    decoder_id: Any = CommandField(CommandType.GENERATED, init=False)
    
    def __post_init__(self):
        super().__post_init__()
        self.decoder_id = id(self.decoder)

@dataclass
class Decoder_Start(StartCommand, DecoderControlBase, ReceiverDerivativeControl):
    decoder_id: Any = CommandField(CommandType.INHERITED)

@dataclass
class Decoder_Stop(StopCommand, DecoderControlBase, ReceiverDerivativeControl):
    decoder_id: Any = CommandField(CommandType.INHERITED)

@dataclass
class Decoder_Delete(DeleteCommand, DecoderControlBase, ReceiverDerivativeControl):
    decoder_id: Any = CommandField(CommandType.INHERITED)


class RGBTerminalControlBase(generic_resource.ControlTask):
    def allocate(self, context: BackendProcessContext) -> ResultVector:
        assert isinstance(self.terminal_data, RGBDecodingTerminalData)
        
        decoder: FilterchainDecoder = context[self.decoder_id]

        data = self.terminal_data
        components = RGBDecodingTerminalComponents(
            data.avthread_fork_filter_basename,
            data.shmem_filter_name,
            data.shmem_buffer_size,
            data.width,
            data.height,
            data.con_timeout_ms,
            decoder.output_fork,
            data.frame_interval_ms,
            data.middleware
        )
        assert isinstance(decoder.output_fork, ForkFrameFilterN)
        
        decoder_terminal = RGBDecodingTerminal(components)
        
        rgb_link_data = decoder_terminal.add_output('')
        # rgb_link_data = decoder_terminal.add_output(sync_fd, '')

        context[decoder] = decoder_terminal

        return generic_resource.Result(
            status=generic_resource.Status.OK,
            resource_change=True,
            additional_data=rgb_link_data
        )

    def start(self, context: BackendProcessContext) -> ResultVector:
        decoder: FilterchainDecoder = context[self.decoder_id]

        terminal: RGBDecodingTerminal = context[decoder]
        # ...
        #raise NotImplementedError
        return True

    def stop(self, context: BackendProcessContext) -> ResultVector:
        # ...
        raise NotImplementedError
        return True

    def delete(self, context: BackendProcessContext) -> ResultVector:
        decoder: FilterchainDecoder = context[self.decoder_id]

        del context[decoder]
        # ...
        return True
    
    @property
    def backend__resource_id(self) -> Any:
        return tuple([RGBTerminalControlBase, self.decoder_id])


@dataclass
class RGBTerminal_Create(CreateCommand, RGBTerminalControlBase, ReceiverDerivativeControl):
    decoder_id: Any = CommandField(CommandType.REQUIRED)
    terminal_data: RGBDecodingTerminalData = CommandField(CommandType.REQUIRED)

@dataclass
class RGBTerminal_Start(StartCommand, RGBTerminalControlBase, ReceiverDerivativeControl):
    decoder_id: Any = CommandField(CommandType.INHERITED)

@dataclass
class RGBTerminal_Stop(StopCommand, RGBTerminalControlBase, ReceiverDerivativeControl):
    decoder_id: Any = CommandField(CommandType.INHERITED)

@dataclass
class RGBTerminal_Delete(DeleteCommand, RGBTerminalControlBase, ReceiverDerivativeControl):
    decoder_id: Any = CommandField(CommandType.INHERITED)



@dataclass
class FilterchainRecording(ProcessBoundTask):
    input_filter_id: any  # None means root
    output_fork_name: str
    recording_dir: str

    # deregister: bool = False

    def run(self, control: ReplyControl, process: BackendProcess):
        context = process.backend__context
        source_spec: SourceSpec = context[SourceSpec]

        input_fork = context[RTSPTask].root_fork
        if self.input_filter_id is not None:
            input_fork = context['filter_forks'][self.input_filter_id]

        self._output_fork = ForkFrameFilterN(self.output_fork_name)

        self._recorder = FilterchainRecorder(
            self.recording_dir,
            writer_slot_id=4,
            source_slot_id=source_spec.source_slot_id,
            output_fork=self._output_fork
        )
        context['filter_forks'][self.output_fork_name] = self._output_fork

        # self._recorder.manager.getCurrentTime()

    def create_process(self) -> BackendProcess:
        raise RuntimeError
