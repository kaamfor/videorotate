from dataclasses import dataclass, field, fields
import functools
import types
from typing import Any, Mapping, Optional, Iterable, MutableMapping

import control.signalling as signalling
import notifier
import video_backend.rtsp.rtsp_task as rtsp_task
import gui.controls.wx_form as wx_form
import gui.resource as resource

import video_backend.rtsp.filterchain as filterchain
import video_backend.rtsp.rtsp_task as rtsp_task
import video_backend.rgb_task as rgb_task

from gui.backend.stages.RTSPTerminal import RTSPTerminal


@dataclass
class RGBReceiver(signalling.Stage, resource.Frontend):
    terminal_link: filterchain.RGBProcessLink = signalling.Stage.derived_field(RTSPTerminal, RTSPTerminal.O_TERMINAL_LINK)
    
    KEY_PROCESS_ID = 'process_id'
    PARAM_TERMINAL_LINK = 'terminal_link'
    @property
    def process_id(self) -> Any:
        return self.generated.get(self.KEY_PROCESS_ID, None)

    def command_sequence(self, *args, start: bool, **kwargs) -> Optional[Iterable[signalling.Command]]:
        if start:
            receiver = rgb_task.Receiver_Create(
                filterchain.RGBAdapter,
                {'link': self.terminal_link}
            )
            self.publish_process_id(receiver.process_id)
            yield receiver

            yield rgb_task.Receiver_Start(self.process_id)
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
