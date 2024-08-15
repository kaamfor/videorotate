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

from gui.backend.stages.RGBReceiver import RGBReceiver


@dataclass
class RGBFilterChange(signalling.Stage, resource.Frontend):
    target_resource_id: Any
    # or receiver: RGBReceiver ?
    filter_id: Any
    updated_filter_parameters: Mapping[str, Any]

    def command_sequence(self, *args, start: bool, **kwargs) -> Optional[Iterable[signalling.Command]]:
        yield rgb_task.FilterParameterChangeCommand(
            self.filter_id,
            self.updated_filter_parameters,
            self.target_resource_id
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
    


