from enum import Enum
import functools
from functools import partial
import dataclasses
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from multiprocessing import Queue
from typing import Type, List, Mapping, Union, Sequence, Optional, Tuple, Any, MutableMapping, Callable
import threading
from socketserver import BaseServer, BaseRequestHandler, ThreadingMixIn

import backend_context
from backend_context import BackendProcess, TaskProcess, GeneratedProcessTask, ProcessBoundTask, BackendProcessContext, ExtendedBackendProcess
import control.generic_resource as generic_resource
from control.generic_resource import CreateCommand, Result, StartCommand, StopCommand, DeleteCommand, ResultVector
import control.signalling as signalling
from messaging.topic import ReplyControl
import notifier
import messenger


class TunneledEventSource:
    @property
    @abstractmethod
    def backend__receiver_output(self) -> messenger.BindableSocket:
        pass
    
    @property
    @abstractmethod
    def backend__update_channel(self) -> notifier.UpdateChannel:
        pass

class TunneledEventSourceDatabase:
    @classmethod
    @abstractmethod
    def backend__lookup(cls,
                        process: BackendProcess,
                        tunnel_id: Any) -> Optional[TunneledEventSource]:
        pass
    
    @classmethod
    @abstractmethod
    def backend__set_source(cls,
                            process: BackendProcess,
                            tunnel_id: Any,
                            source: TunneledEventSource) -> None:
        pass

class TunnelBootstrapControlProcess(ExtendedBackendProcess, TaskProcess):
    pass

class TunnelBootstrapControl(GeneratedProcessTask):
    def create_process(self) -> ExtendedBackendProcess:
        return TunnelBootstrapControlProcess()
    
    @property
    def target_resource_id(self) -> Any:
        return self.process_id


class TunnelDerivativeControl(ProcessBoundTask):
    def create_process(self) -> BackendProcess:
        raise RuntimeError
    
    @property
    def target_resource_id(self) -> Any:
        return self.process_id


def get_tunnel(database: TunneledEventSourceDatabase,
               process: backend_context.BackendProcess,
               tunnel_id) -> Optional[TunneledEventSource]:
    return database.backend__lookup(process, tunnel_id)

# ExtendedBackendProcess is required for operation
# TODO: document it!
class TunnelControlBase(generic_resource.ControlTask, TunneledEventSourceDatabase):
    
    @dataclass
    class TunnelAttributes:
        channel: notifier.UpdateChannel
        add_source: Callable[[messenger.ScheduledSource], None]
        source_lookup_cls: Type[TunneledEventSourceDatabase]
        current_event_source: Optional[TunneledEventSource]
        
        def fetch_event_source(self,
                               process: BackendProcess,
                               tunnel_id: Any) -> None:
            lookup_fn = self.source_lookup_cls.backend__lookup
            data = None
            if lookup_fn:
                data = lookup_fn(process, tunnel_id)
            
            self.current_event_source = data
        
        @property
        def backend__update_channel(self) -> notifier.UpdateChannel:
            return self.channel
    
    @property
    def backend__update_channel(self) -> notifier.UpdateChannel:
        return self.backend__attributes.channel
    
    def allocate(self, context: BackendProcessContext) -> ResultVector:
        assert isinstance(
            self.backend__process, ExtendedBackendProcess
        ), 'ExtendedBackendProcess is required for operation'
        
        base = context.setdefault(TunnelControlBase, {})
        attributes = base[self.tunnel_id] = self._backend__build_source(
            self.backend__process.messaging_scheduler,
            key=self.notifier_property
        )
        
        attributes.fetch_event_source(self.backend__process, self.tunnel_id)
        
        return True

    def start(self, context: BackendProcessContext) -> ResultVector:
        attributes = self.backend__attributes
        
        if not attributes.current_event_source:
            attributes.fetch_event_source(self.backend__process, self.tunnel_id)
            
        if not attributes.current_event_source:
            raise RuntimeError(f"No event source is available"
                               f" with tunnel id {self.tunnel_id}")
        
        attributes.add_source(attributes.current_event_source.backend__receiver_output)
        return True

    def stop(self, context: BackendProcessContext) -> ResultVector:
        raise NotImplementedError
        return True

    def delete(self, context: BackendProcessContext) -> ResultVector:
        raise NotImplementedError
        return True

    @property
    def backend__attributes(self) -> TunnelAttributes:
        context = self.backend__process.context
        
        return context.setdefault(TunnelControlBase, {})[self.tunnel_id]
    
    @staticmethod
    def backend__get_attributes(context: BackendProcessContext,
                                tunnel_id: Any) -> TunnelAttributes:
        return context.setdefault(TunnelControlBase, {})[tunnel_id]
    
    @classmethod
    def backend__lookup(cls,
                        process: BackendProcess,
                        tunnel_id: Any) -> Optional[TunneledEventSource]:
        database = process.context.setdefault(TunnelControlBase, {})
        
        if tunnel_id not in database:
            return None
        
        return database[tunnel_id]
    
    @classmethod
    def backend__set_source(cls,
                            process: BackendProcess,
                            tunnel_id: Any,
                            source: TunneledEventSource) -> None:
        database = process.context.setdefault(TunnelControlBase, {})

        if tunnel_id in database:
            database[tunnel_id].current_event_source = source
    
    def _backend__build_source(self,
                               messaging_scheduler: messenger.MessagingScheduler,
                               key: Optional[notifier.KeyId] = None,
                               emitted_by: Any = None,
                               base_channel: Optional[notifier.UpdateChannel] = None
                               ) -> TunnelAttributes:
        tunnel_channel = base_channel or notifier.UpdateChannel()
        
        return self.TunnelAttributes(
            channel=tunnel_channel,
            add_source=partial(
                messaging_scheduler.add_source,
                callback=partial(
                    self._backend__wrap_source_input,
                    tunnel_channel=tunnel_channel,
                    key=key,
                    emitted_by=emitted_by
                )
            ),
            source_lookup_cls=self.source_lookup_cls,
            current_event_source=None
        )
    
    @staticmethod
    def _backend__wrap_source_input(input: Any,
                                    *,
                                    tunnel_channel: notifier.UpdateChannel,
                                    key: Optional[notifier.KeyId],
                                    emitted_by: Any
                                    ) -> None:
        tunnel_channel.send(
            notifier.Update(
                key=key,
                value=input,
                emitted_by=emitted_by
            )
        )
    
    @property
    def backend__resource_id(self) -> Any:
        return self.tunnel_id
    
    # TODO: deleteme
    def run(self, control: ReplyControl, process) -> Result:
        res = super().run(control, process)
        self.backend__resource_id
        return res

@dataclass
class Tunnel_Create(CreateCommand, TunnelControlBase, TunnelBootstrapControl):
    notifier_property: notifier.KeyId
    source_lookup_cls: Type[TunneledEventSourceDatabase]

    tunnel_id: Any = field(init=False)

    def __post_init__(self):
        super().__post_init__()

        self.tunnel_id = '' # pre-initialize before using asdict()
        attrs = dataclasses.asdict(self)

        self.tunnel_id = tuple([(id(obj), hash(obj)) for obj in attrs])


@dataclass
class Tunnel_Start(StartCommand, TunnelControlBase, TunnelDerivativeControl):
    tunnel_id: Any

@dataclass
class Tunnel_Stop(StopCommand, TunnelControlBase, TunnelDerivativeControl):
    tunnel_id: Any

@dataclass
class Tunnel_Delete(DeleteCommand, TunnelControlBase, TunnelDerivativeControl):
    tunnel_id: Any



@dataclass
class ContextTunnel_Create(Tunnel_Create):
    message_topic: Any
    
    def _backend__build_source(self, *args, **kwargs) -> TunnelControlBase.TunnelAttributes:
        BASE_CHANNEL_KEY = 'base_channel'
        custom_kwargs = dict(kwargs)
        
        assert (custom_kwargs[BASE_CHANNEL_KEY] is None
                ), f"Conflicting option: a {BASE_CHANNEL_KEY} value is provided by other party"
        
        process = self.backend__process
        topic_context = process.backend_messenger.new_topic(self.message_topic)
        topic_context.registry_channel.subscribe(
            lambda update: process.backend_registry.append(update.value)
        )
        
        custom_kwargs[BASE_CHANNEL_KEY] = topic_context.send()
        return super()._backend__build_source(*args, **custom_kwargs)


@dataclass
class ContextTunnel_Start(Tunnel_Start):
    pass


@dataclass
class ContextTunnel_Stop(Tunnel_Stop):
    pass


@dataclass
class ContextTunnel_Delete(Tunnel_Delete):
    pass



# class MessageBrokerOperation


# TunneledEventSourceDatabase

# class MessageBrokerCommandBase(backend_context.BackendTask, signalling.Command):
#     tunnel_lookup_cls: Type[TunneledEventSourceDatabase]
#     tunnel_id: Any
    
#     @dataclass
#     class TunnelAttributes:
#         channel: notifier.UpdateChannel

# class MessageBroker_
