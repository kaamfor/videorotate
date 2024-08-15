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
class RGBFilter(signalling.Stage, resource.Frontend):
    receiver: RGBReceiver
    
    filter_parameters: Mapping[str, Any]
    
    #filter: str = wx_form.TextInput.field(value='')
    filter: str = 'preview'
    #filter_module: str = wx_form.TextInput.field(value='')
    #filter_module: str = wx_form.TextOptionSelect.field(value=0, options=rgb_task.Filter_Create.available_filters())
    filter_module: str = 'preview'
    #parent_id: Any = wx_form.TextInput.field(value='')
    parent_id: Any = None
    

    KEY_FILTER_ID = 'filter_id'

    @property
    def filter_id(self) -> Any:
        return self.generated.get(self.KEY_FILTER_ID, None)

    @property
    def process_id(self) -> Any:
        return self.receiver.process_id

    def command_sequence(self, *args, start: bool, **kwargs) -> Optional[Iterable[signalling.Command]]:
        if start:
            filter_id = ''.join([str(self.parent_id), '-', self.filter])
            self.publish_filter_id(filter_id)
            
            rgb_filter = rgb_task.Filter_Create(
                process_id=self.process_id,
                filter_id=filter_id,
                parent_id=self.parent_id,
                filter=self.filter,
                module_name=self.filter_module,
                filter_run_parameters=self.filter_parameters
            )
            yield rgb_filter

            yield rgb_task.Filter_Start(rgb_filter.process_id, rgb_filter.filter_id)
        elif self.process_id is not None and self.filter_id is not None:
            yield rgb_task.Filter_Stop(self.process_id, self.filter_id)

            yield rgb_task.Filter_Delete(self.process_id, self.filter_id)
    
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


