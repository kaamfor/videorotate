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
import video_backend.rtsp.filterchain as filterchain

import control.generic_resource as generic_resource

from gui.backend.stages.RTSPDecoder import RTSPDecoder


@dataclass
class RTSPTerminal(signalling.Stage, resource.Frontend):
    decoder: RTSPDecoder
    width: int = wx_form.NumberInput.field(default=1920, min_value=320, max_value=15360, display_name='Width')
    height: int = wx_form.NumberInput.field(default=1080, min_value=200, max_value=8640, display_name='Height')
    buffer_size: int = wx_form.NumberInput.field(default=10, min_value=1, max_value=1000, display_name='Image buffer size (count)')
    frame_interval_ms: int = wx_form.NumberInput.field(default=1000 // 15, min_value=1, max_value=5000, display_name='Frame interval (ms)')
    
    O_TERMINAL_LINK = 'terminal_link'
    
    @property
    def process_id(self) -> Any:
        return self.decoder.process_id
    
    @property
    def decoder_id(self) -> Any:
        return self.decoder.decoder_id

    def command_sequence(self, *args, start: bool, **kwargs) -> Optional[Iterable[signalling.Command]]:
        receiver = self.decoder.receiver
        decoder = self.decoder
        
        if start:
            self.generated['fps'] = 1000 // self.frame_interval_ms
            terminal_data = self.generated['terminal'] = rtsp_task.RGBDecodingTerminalData(
                f"root{receiver.slot_id}_decoder_avthread_outfilter",
                f"root{receiver.slot_id}_decoder_shmem",
                self.buffer_size,
                self.width,
                self.height,
                self.decoder.receiver.timeout_ms,
                self.frame_interval_ms
            )

            terminal = rtsp_task.RGBTerminal_Create(
                self.process_id,
                decoder.decoder_id,
                terminal_data
            )
            yield terminal

            yield rtsp_task.RGBTerminal_Start(self.process_id, self.decoder_id)
        elif self.process_id is not None and self.decoder_id is not None:
            yield rtsp_task.RGBTerminal_Stop(self.process_id, self.decoder_id)

            yield rtsp_task.RGBTerminal_Delete(self.process_id, self.decoder_id)

    @functools.cached_property
    def generated(self) -> MutableMapping[str, Any]:
        return {}

    def generated_parameters(self) -> Mapping[str, Any]:
        return types.MappingProxyType(self.generated)
    
    def map_result(self,
                   update: notifier.Update,
                   previous_map: Mapping[str, Any] | None
                   ) -> Mapping[str, Any]:
        mapping = previous_map or {}
        
        assert isinstance(update.value, generic_resource.Result)
        data = update.value.additional_data
        
        if isinstance(data, filterchain.RGBProcessLink):
            mapping[self.O_TERMINAL_LINK] = data
        
        return mapping
