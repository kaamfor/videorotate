from dataclasses import dataclass, field, fields
import functools
import types
from typing import Any, Mapping, Optional, Iterable, MutableMapping

import control.signalling as signalling
import video_backend.rtsp.rtsp_task as rtsp_task
import gui.controls.wx_form as wx_form
import gui.resource as resource

import notifier
import video_backend.rtsp.rtsp_task as rtsp_task

from gui.backend.stages.RTSPReceiver import RTSPReceiver


@dataclass
class RTSPFilter(signalling.Stage, resource.Frontend):
    receiver: RTSPReceiver
    input_filter_id: Any
    
    KEY_FILTER_ID = 'filter_id'
    @property
    def filter_id(self) -> Any:
        return self.generated.get(self.KEY_FILTER_ID, None)

    def command_sequence(self, *args, start: bool, **kwargs) -> Optional[Iterable[signalling.Command]]:
        process_id = self.receiver.process_id
        # if start:
        #     decoder = self.generated['decoder'] = rtsp_task.DecoderSpec(
        #         f"root{self.receiver.slot_id}_decoder_fork",
        #         f"root{self.receiver.slot_id}_decoder",
        #         f"root{self.receiver.slot_id}_decoder_avthread"
        #     )

        #     receiver = rtsp_task.Decoder_Create(
        #         process_id,
        #         decoder,
        #         self.input_filter
        #     )
        #     self.filter_id = receiver.decoder_id
        #     yield receiver

        #     yield rtsp_task.Decoder_Start(process_id, self.filter_id)
        # elif process_id is not None and self.filter_id is not None:
        #     yield rtsp_task.Decoder_Stop(process_id, self.filter_id)

        #     yield rtsp_task.Decoder_Delete(process_id, self.filter_id)

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
    
    def publish_filter_id(self, filter_id: Any) -> None:
        self.generated[self.KEY_FILTER_ID] = filter_id
