from dataclasses import dataclass, field, fields
from abc import ABC, abstractmethod
import functools
import types
from typing import Any, Iterable, Mapping, Optional, MutableMapping

import control.signalling as signalling
import notifier
import video_backend.rtsp.rtsp_task as rtsp_task
import gui.controls.wx_form as wx_form
import gui.resource as resource

import video_backend.rtsp.rtsp_task as rtsp_task

@dataclass
class RTSPReceiver(signalling.Stage, resource.Frontend):
    rtsp_link: str = wx_form.TextInput.field(value='', display_name='RTSP link')
    #slot_id: int = wx_form.NumberInput.field(default=1, min_value=1, max_value=10000, display_name='Slot ID')
    slot_id: int
    timeout_ms: int = wx_form.NumberInput.field(default=1000, min_value=100, max_value=360000, display_name='Timeout (ms)')

    KEY_PROCESS_ID = 'process_id'
    @property
    def process_id(self) -> Any:
        return self.generated.get(self.KEY_PROCESS_ID, None)

    def command_sequence(self, *args, start: bool, **kwargs) -> Optional[Iterable[signalling.Command]]:
        
        if start:
            source = self.generated['source'] = rtsp_task.RTSPStreamSpec(
                f"root{self.slot_id}_fork",
                f"rtsp{self.slot_id}_thread",
                self.slot_id,
                self.rtsp_link,
                self.timeout_ms
            )
            
            receiver = rtsp_task.Receiver_Create(source)
            self.publish_process_id(receiver.process_id)
            
            yield receiver
            
            yield rtsp_task.Receiver_Start(self.process_id)
        elif self.process_id is not None:
            yield rtsp_task.Receiver_Stop(self.process_id)
            
            yield rtsp_task.Receiver_Delete(self.process_id)
    
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
    
    def publish_process_id(self, process_id: Any) -> None:
        self.generated[self.KEY_PROCESS_ID] = process_id




