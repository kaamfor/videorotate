from dataclasses import dataclass, field, fields
import functools
import types
from typing import Any, Mapping, Optional, Iterable, MutableMapping

import control.signalling as signalling
import notifier
import video_backend.rtsp.rtsp_task as rtsp_task
import gui.controls.wx_form as wx_form
import gui.resource as resource

import control.generic_resource as generic_resource

import video_backend.rtsp.filterchain as filterchain
import video_backend.rtsp.rtsp_task as rtsp_task
import video_backend.rgb_task as rgb_task
import video_backend.consumer as consumer

from gui.backend.stages.RGBFilter import RGBFilter


@dataclass
class RGBFilterTerminal(signalling.Stage, resource.Frontend):
    filter: RGBFilter
    shmem_image: Optional[consumer.RGBSharedMemoryImage] = None
    
    O_TERMINAL_LINK = 'terminal_link'
    
    @property
    def filter_id(self) -> Any:
        return self.filter.filter_id

    @property
    def process_id(self) -> Any:
        return self.filter.receiver.process_id

    def command_sequence(self, *args, start: bool, **kwargs) -> Optional[Iterable[signalling.Command]]:
        if start:
            rgb_terminal = rgb_task.FilterTerminal_Create(
                process_id=self.process_id,
                filter_id=self.filter_id
            )
            yield rgb_terminal
            
            yield rgb_task.FilterTerminal_Start(
                self.process_id,
                self.filter_id
            )
        elif self.process_id is not None and self.filter_id is not None:
            yield rgb_task.FilterTerminal_Stop(self.process_id, self.filter_id, self.shmem_image)

            yield rgb_task.FilterTerminal_Delete(self.process_id, self.filter_id, self.shmem_image)
    
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
        
        import sys
        print('RGBFilterTerminal_update', update)
        sys.stdout.flush()
        
        if isinstance(update.value, rgb_task.RGBSharedMemoryImage):
            mapping[self.O_TERMINAL_LINK] = update.value
        
        mapping[self.O_TERMINAL_LINK]
        return mapping

