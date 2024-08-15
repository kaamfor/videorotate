from dataclasses import dataclass, field, fields
from abc import ABC, abstractmethod
import functools
from functools import partial
import operator
import enum
import types
from typing import Any, Iterable, Mapping, Optional, MutableMapping, Union, Type, Tuple, List

import socketserver
from backend_context import BackendProcess

import control.signalling as signalling
from messaging.topic import ReplyControl
import notifier
import net.receiver
import gui.controls.wx_form as wx_form
import gui.resource as resource

import event.tunneling as tunneling
import control.patch as patch
import messenger
import backend_context

class ServerType(enum.Enum):
    TCPReceiver = socketserver.ThreadingTCPServer
    UDPReceiver = socketserver.ThreadingUDPServer


@dataclass
class ThreadedEventReceiver(signalling.Stage, resource.Frontend):
    receiver_type: str = wx_form.TextOptionSelect.field(value=1, options=ServerType._member_names_)
    listen_ip: str = wx_form.TextInput.field(value='0.0.0.0')
    listen_port: int = wx_form.NumberInput.field(value=28287, min_value=1, max_value=65535)
    processor: net.receiver.EventProcessor
    notifier_property: notifier.KeyId

    process_id: Optional[Any] = None

    O_TUNNEL_ID = 'tunnel_id'

    # KEY_PROCESS_ID = 'process_id'
    # @property
    # def process_id(self) -> Any:
    #     return self.generated.get(self.KEY_PROCESS_ID, None)

    KEY_RECEIVER_ID = 'receiver_id'
    @property
    def receiver_id(self) -> Any:
        return self.generated.get(self.KEY_RECEIVER_ID, None)

    KEY_TUNNEL_ID = 'tunnel_id'
    @property
    def receiver_id(self) -> Any:
        return self.generated.get(self.KEY_TUNNEL_ID, None)


    @property
    def listen_address(self) -> Tuple[str, int]:
        return self.listen_ip, self.listen_port

    @property
    def receiver_cls(self) -> socketserver.ThreadingMixIn:
        return ServerType[self.receiver_type].value

    TUNNEL_SOURCE_LOOKUP_CLS = tunneling.TunnelControlBase
    TUNNEL_BASE_CLS = tunneling.TunnelControlBase
    THREADING_RECEIVER_BASE_CLS = net.receiver.ThreadingServerReceiverControlBase
    PATCH_BASE_CLS = patch.StreamerPatchCommand
    def command_sequence(self, *args, start: bool, **kwargs) -> Optional[Iterable[signalling.Command]]:

        if start:
            evt_receiver = net.receiver.ThreadingServerReceiver_Create(
                self.receiver_cls,
                self.processor,
                self.notifier_property,
                self.listen_address
            )
            if self.process_id is None:
                self.process_id = evt_receiver.process_id
            else:
                evt_receiver.process_id = self.process_id
                
            
            common_process = evt_receiver.process_id
            common_id = evt_receiver.receiver_id
            
            evt_receiver.receiver_id = self._build_receiver_id(common_id)
            
            tunnel = tunneling.Tunnel_Create(
                self.notifier_property,
                ThreadedEventReceiver.TUNNEL_SOURCE_LOOKUP_CLS
            )
            tunnel.process_id = common_process
            tunnel.tunnel_id = self._build_tunnel_id(common_id)
            
            yield tunnel
            
            receiver_patch = patch.StreamerPatchCommand(
                ThreadedEventReceiver._patch_selector,
                ThreadedEventReceiver._patcher,
                self._build_patch_id(common_id)
            )
            # TODO: test that what happen if this assignment not made
            receiver_patch.process_id = common_process
            
            yield receiver_patch
            
            yield evt_receiver
            #self.publish_process_id(evt_receiver.process_id)
            self.publish_receiver_id(evt_receiver.receiver_id)
            self.publish_tunnel_id(tunnel.tunnel_id)
            
            yield tunneling.Tunnel_Start(
                tunnel.process_id,
                tunnel.tunnel_id
            )
            
            yield net.receiver.ThreadingServerReceiver_Start(
                evt_receiver.process_id,
                evt_receiver.receiver_id
            )
        elif self.process_id is not None and self.receiver_id is not None:
            yield net.receiver.ThreadingServerReceiver_Stop(
                self.process_id,
                self.receiver_id
            )
            
            yield net.receiver.ThreadingServerReceiver_Delete(
                self.process_id,
                self.receiver_id
            )
    
    @functools.cached_property
    def generated(self) -> MutableMapping[str, Any]:
        return {}
    
    def generated_parameters(self) -> Mapping[str, Any]:
        return types.MappingProxyType(self.generated)
    
    def map_result(self,
                   update: notifier.Update,
                   previous_map: Mapping[str, Any] | None
                   ) -> Mapping[str, Any]:
        return previous_map or {}
    
    # def publish_process_id(self, process_id: Any) -> None:
    #     self.generated[self.KEY_PROCESS_ID] = process_id
    
    def publish_receiver_id(self, receiver_id: Any) -> None:
        self.generated[self.KEY_RECEIVER_ID] = receiver_id
    
    def publish_tunnel_id(self, tunnel_id: Any) -> None:
        self.generated[self.KEY_TUNNEL_ID] = tunnel_id
    
    
    PATCHED_COMMAND = net.receiver.ThreadingServerReceiver_Create
    
    @classmethod
    def _patch_selector(cls,
                        control: messenger.ReplyControl,
                        callback: messenger.PromiseControlCallback
                        ):
        check_handler = isinstance(
            callback,
            backend_context.TaskRunner
        )
        check_command = isinstance(
            control.reply_status.reply_msg,
            ThreadedEventReceiver.PATCHED_COMMAND
        )
        
        return check_handler and check_command
    
    @classmethod
    def _patcher(cls,
                 control: messenger.ReplyControl,
                 callback: messenger.PromiseControlCallback
                 ) -> Any:
        command = control.reply_status.reply_msg
        assert isinstance(command, ThreadedEventReceiver.PATCHED_COMMAND)
        
        result = callback(control)
        
        process = command.backend__process
        assert isinstance(process, backend_context.ExtendedBackendProcess)
        
        common_id = cls._get_common_id(command.receiver_id)
        
        tunnel_db = ThreadedEventReceiver.TUNNEL_SOURCE_LOOKUP_CLS
        assert isinstance(command.receiver_id, Tuple) and len(command.receiver_id) == 2
        tunnel_id = cls._build_tunnel_id(common_id)
        tunnel_db.backend__set_source(process, tunnel_id, command)
        tunnel_attribs = tunnel_db.backend__get_attributes(process.context, tunnel_id)
        
        channel: notifier.UpdateChannel = tunnel_attribs.channel
        
        
        patch_control = patch.StreamerPatchCommand.backend__get_control(
            process.context,
            cls._build_patch_id(common_id)
        )
        
        channel.thenPermanent(
            partial(
                process.backend_messenger.deferred_reply,
                patch_control
            )
        )
        
        return result
    
    @classmethod
    def _build_tunnel_id(cls, common_id: Any) -> Tuple:
        return (cls.TUNNEL_BASE_CLS, common_id)
    
    @classmethod
    def _build_receiver_id(cls, common_id: Any) -> Tuple:
        return (cls.THREADING_RECEIVER_BASE_CLS, common_id)
    
    @classmethod
    def _build_patch_id(cls, common_id: Any) -> Tuple:
        return (cls.PATCH_BASE_CLS, common_id)
    
    @classmethod
    def _get_common_id(cls, id: Tuple) -> Any:
        return id[1]




