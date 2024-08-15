from enum import Enum
import functools
import dataclasses
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from multiprocessing import Pipe
from multiprocessing.connection import Connection
from typing import Type, List, Mapping, Union, Sequence, Optional, Tuple, Any, MutableMapping, Callable, Protocol, runtime_checkable
import threading
from socketserver import BaseServer, BaseRequestHandler, ThreadingMixIn

from backend_context import BackendProcess, TaskProcess, GeneratedProcessTask, ProcessBoundTask, BackendProcessContext
import control.generic_resource as generic_resource
from control.generic_resource import CreateCommand, StartCommand, StopCommand, DeleteCommand, ResultVector
import control.signalling as signalling
from event.tunneling import TunneledEventSource
import notifier
import messenger
import event.tunneling as tunneling

import videorotate_utils

CommandField = signalling.Command.field
CommandType = signalling.Command.ParameterType

# ENHANCEMENT: using ReplyControl & messaging infrastructure
#  to receive messages this way? -> possible bidir. communication

@dataclass
class IncomingEvent:
    data: Any
    received_by: object


@dataclass
class ChangeEvent:
    value: Any
    source: Optional[Any] = None

@runtime_checkable
class EventParser(Protocol):
    def __call__(self, msg: IncomingEvent) -> Optional[ChangeEvent]:
        pass


@runtime_checkable
class EventDistributor(Protocol):
    def __call__(self, event: Optional[ChangeEvent]) -> Optional[Any]:
        pass


@dataclass
class EventProcessor:
    property_id: notifier.KeyId
    parser: Union[EventParser, Type[EventParser]]
    distributor: Union[EventDistributor, Type[EventDistributor]]

    @functools.cached_property
    def parser_input(self) -> notifier.UpdateChannel:
        return self._parser_input

    @functools.cached_property
    def event_output(self) -> notifier.UpdateChannel:
        return self._event_output

    def __post_init__(self):
        self._parser_input = notifier.UpdateChannel()
        self._event_output = notifier.UpdateChannel()

        if isinstance(self.parser, type):
            self.__parser = self.parser()
        else:
            self.__parser = self.parser

        if isinstance(self.distributor, type):
            self.__distributor = self.distributor()
        else:
            self.__distributor = self.distributor

        self._parser_input.thenPermanent(
            self._process_message
        )

    def _process_message(self, update: notifier.Update) -> None:
        assert isinstance(update.value, IncomingEvent)
        change_evt = self.__parser(update.value)

        property_value = self.__distributor(change_evt)

        emitted_by = update.value.received_by or update.emitted_by
        if change_evt is not None:
            emitted_by = change_evt.source or emitted_by

        self.event_output.send(notifier.Update(
            key=self.property_id,
            value=property_value,
            emitted_by=emitted_by
        ))

# TODO: create other class for processor catalog store
@dataclass
class ReceiverControlBase(tunneling.TunneledEventSource,
                          generic_resource.ControlTask,
                          ABC):
    @staticmethod
    def backend__processor_catalog(context: BackendProcessContext
                                   ) -> MutableMapping[Any, EventProcessor]:
        return context.setdefault(EventProcessor, {})
    
    @property
    @abstractmethod
    def backend__receiver_output_feeder(self) -> Connection:
        pass

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


class ServerRequestHandler(BaseRequestHandler):
    RECV_HARD_LIMIT = 4096
    
    def __init__(self,
                 receiver_control: ReceiverControlBase,
                 #message_queue,
                 *args,
                 **kwargs) -> None:
        assert isinstance(receiver_control, ReceiverControlBase)
        self._receiver_control = receiver_control

        super().__init__(*args, **kwargs)

    def handle(self) -> None:
        msg, address = self.request.recvfrom(self.RECV_HARD_LIMIT)
        
        processor: EventProcessor = self._receiver_control.processor
        
        output_con = self._receiver_control.backend__receiver_output_feeder
        if output_con is not None:
            processor.event_output.thenPermanent(
                lambda update: output_con.send(update)
            )
            
        
        processor.parser_input.send(notifier.Update(
            key=None,
            value=IncomingEvent(
                data=msg,
                received_by=address
            )
        ))

class ThreadingServerReceiverControlBase(ReceiverControlBase):
    RequestHandler = ServerRequestHandler

    @dataclass
    class _ServerAttributes(tunneling.TunneledEventSource):
        server: BaseServer
        processor: EventProcessor
        thread: Optional[threading.Thread]
        
        frontend_con: Connection
        backend_con: Connection
        
        def backend__receiver_output(self) -> messenger.BindableSocket:
            return messenger.SimplePipeSocket(self.frontend_con)

    def allocate(self, context: BackendProcessContext) -> ResultVector:
        base = context.setdefault(ThreadingServerReceiverControlBase, {})
        processor_catalog = self.backend__processor_catalog(context)
        
        processor: EventProcessor = self.processor
        processor_catalog[self.backend__resource_id] = processor

        req_handler = functools.partial(self.RequestHandler, self)
        server = self.receiver_cls(self.listen_address, req_handler)
        
        frontend_con, backend_con = Pipe()
        
        self.attributes = self._ServerAttributes(
            server=server,
            processor=processor,
            thread=None,
            frontend_con=frontend_con,
            backend_con=backend_con
        )
        return True

    def start(self, context: BackendProcessContext) -> ResultVector:
        thread = threading.Thread(target=self.attributes.server.serve_forever)
        
        self.attributes.thread = thread
        thread.daemon = True
        thread.start()
        
        return True

    def stop(self, context: BackendProcessContext) -> ResultVector:
        self.attributes.server.shutdown()
        self.attributes.server.server_close()
        # TODO: is join() needed?
        #self.attributes.thread.join()
        self.attributes.thread = None
        return True

    def delete(self, context: BackendProcessContext) -> ResultVector:
        del self.attributes
        return True

    @property
    def backend__resource_id(self) -> Any:
        return self.receiver_id
    
    @property
    def attributes(self) -> _ServerAttributes:
        base: Mapping = self.backend__process.context[ThreadingServerReceiverControlBase]
        return base[self.backend__resource_id]
    
    @attributes.setter
    def attributes(self, attributes: _ServerAttributes) -> None:
        base = self.backend__process.context.setdefault(ThreadingServerReceiverControlBase, {})
        base[self.backend__resource_id] = attributes
    
    @attributes.deleter
    def attributes(self) -> None:
        base = self.backend__process.context[ThreadingServerReceiverControlBase]
        del base[self.backend__resource_id]
    
    @property
    def backend__receiver_output(self) -> messenger.BindableSocket:
        return self.attributes.backend__receiver_output()
    
    @property
    def backend__receiver_output_feeder(self) -> Connection:
        return self.attributes.backend_con


@dataclass
class ThreadingServerReceiver_Create(CreateCommand, ThreadingServerReceiverControlBase, ReceiverBootstrapControl):
    receiver_cls: Type[ThreadingMixIn]
    processor: EventProcessor
    notifier_property: notifier.KeyId

    listen_address: Tuple[str, int]
    receiver_id: Any = field(init=False)

    def __post_init__(self):
        super().__post_init__()

        self.receiver_id = '' # pre-initialize before using asdict()
        attrs = dataclasses.asdict(self)

        self.receiver_id = tuple([(id(obj), hash(obj)) for obj in attrs])


@dataclass
class ThreadingServerReceiver_Start(StartCommand, ThreadingServerReceiverControlBase, ReceiverDerivativeControl):
    receiver_id: Any

@dataclass
class ThreadingServerReceiver_Stop(StopCommand, ThreadingServerReceiverControlBase, ReceiverDerivativeControl):
    receiver_id: Any

@dataclass
class ThreadingServerReceiver_Delete(DeleteCommand, ThreadingServerReceiverControlBase, ReceiverDerivativeControl):
    receiver_id: Any




class EventExposerControlBase(generic_resource.ControlTask):

    def allocate(self, context: BackendProcessContext) -> ResultVector:
        base = context.setdefault(EventExposerControlBase, {})

        processor = self.backend__processor

        processor.event_output

        return True

    def start(self, context: BackendProcessContext) -> ResultVector:
        processor = self.backend__processor

        processor.event_output

        return True

    def stop(self, context: BackendProcessContext) -> ResultVector:
        self.attributes.server.shutdown()
        self.attributes.server.server_close()
        # TODO: is join() needed?
        # self.attributes.thread.join()
        self.attributes.thread = None
        return True

    def delete(self, context: BackendProcessContext) -> ResultVector:
        del self.attributes
        return True

    @property
    def backend__resource_id(self) -> Any:
        return self.receiver_id

    @property
    def backend__processor(self) -> EventProcessor:
        processor_catalog = ReceiverControlBase.backend__processor_catalog(
            self.backend__process.context)
        return processor_catalog[self.receiver_id]

# ...
@dataclass
class EventExposer_Create(CreateCommand, EventExposerControlBase, ReceiverDerivativeControl):
    receiver_id: Any
    property_id: Any
    
    #tunnel_id: CommandField(CommandType.REQUIRED, tunneling.)


@dataclass
class EventExposer_Start(StartCommand, EventExposerControlBase, ReceiverDerivativeControl):
    receiver_id: Any
    property_id: Any


@dataclass
class EventExposer_Stop(StopCommand, EventExposerControlBase, ReceiverDerivativeControl):
    receiver_id: Any
    property_id: Any


@dataclass
class EventExposer_Delete(DeleteCommand, EventExposerControlBase, ReceiverDerivativeControl):
    receiver_id: Any
    property_id: Any



# Not a clean solution... tied to a messenger implementation
class EventExposerControlBase(generic_resource.ControlTask):
    
    def allocate(self, context: BackendProcessContext) -> ResultVector:
        base = context.setdefault(EventExposerControlBase, {})
        
        processor = self.backend__processor
        
        processor.event_output
        
        return True

    def start(self, context: BackendProcessContext) -> ResultVector:
        processor = self.backend__processor

        processor.event_output

        return True

    def stop(self, context: BackendProcessContext) -> ResultVector:
        self.attributes.server.shutdown()
        self.attributes.server.server_close()
        # TODO: is join() needed?
        # self.attributes.thread.join()
        self.attributes.thread = None
        return True

    def delete(self, context: BackendProcessContext) -> ResultVector:
        del self.attributes
        return True

    @property
    def backend__resource_id(self) -> Any:
        return self.receiver_id

    @property
    def backend__processor(self) -> EventProcessor:
        processor_catalog = ReceiverControlBase.backend__processor_catalog(self.backend__process.context)
        return processor_catalog[self.receiver_id]


@dataclass
class EventExposer_Create(CreateCommand, EventExposerControlBase, ReceiverDerivativeControl):
    receiver_id: Any
    property_id: Any


@dataclass
class EventExposer_Start(StartCommand, EventExposerControlBase, ReceiverDerivativeControl):
    receiver_id: Any
    property_id: Any


@dataclass
class EventExposer_Stop(StopCommand, EventExposerControlBase, ReceiverDerivativeControl):
    receiver_id: Any
    property_id: Any


@dataclass
class EventExposer_Delete(DeleteCommand, EventExposerControlBase, ReceiverDerivativeControl):
    receiver_id: Any
    property_id: Any
