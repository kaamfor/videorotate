from dataclasses import dataclass, field, fields
import functools
from functools import partial
import operator
import types
from typing import Any, Mapping, Optional, Iterable, MutableMapping, Tuple, List

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
import event.tunneling as tunneling
import net.receiver
import gui.backend.event.processing as event_processing

import backend_context

import notifier
import messenger

import control.patch as patch


@dataclass
class RecordingStatusUpdate:
    started: bool
    finished: bool
    filepath: str
    
    def __bool__(self) -> bool:
        return self.started and not self.finished


class CustomRecorderRemoteBase(rgb_task.RecorderRemoteControlBase):
    def generate_filename(self, change: Any) -> str:
        setattr(self, '__current_change', change)
        filename_obj = super().generate_filename(change)
        delattr(self, '__current_change')
        
        return str(filename_obj)
    
    def assemble_filename(self, unique_part: str, absolute_path: bool = False) -> rgb_task.Filename:
        change = getattr(self, '__current_change', None)
        
        filename = super().assemble_filename(unique_part, absolute_path)
        
        fn_parts = filename.filename_parts
        fn_delims = filename.filename_part_delimiter
        if isinstance(change, event_processing.RecordingTriggerResult):
            for k,v in change.tags.items():
                if v is None:
                    v = ''
                else:
                    v = f"={v}"
                fn_parts.append(f"{k}{v}")
            
            delim_number = max(len(change.tags) - int(not len(fn_parts)), 0)
            if delim_number:
                fn_delims.extend(('.',) * delim_number)
        
        return filename


@dataclass
class RecorderRemote_Create(rgb_task.RecorderRemote_Create, CustomRecorderRemoteBase):
    pass

@dataclass
class RecorderRemote_Start(rgb_task.RecorderRemote_Start, CustomRecorderRemoteBase):
    pass

@dataclass
class RecorderRemote_Stop(rgb_task.RecorderRemote_Stop, CustomRecorderRemoteBase):
    pass

@dataclass
class RecorderRemote_Delete(rgb_task.RecorderRemote_Delete, CustomRecorderRemoteBase):
    pass


@dataclass
class RGBRecorder(signalling.Stage, resource.Frontend):
    # TODO: should depend on other stage?
    # input_filter: RGBFilter
    process_id: Any
    filter_id: Any
    tunnel_id: Any
    fps: int
    recording_dir: str
    recording_basename: str
    notifier_property: str
    start_immediately: bool

    TUNNEL_SOURCE_LOOKUP_CLS = tunneling.TunnelControlBase
    TUNNEL_BASE_CLS = tunneling.TunnelControlBase
    THREADING_RECEIVER_BASE_CLS = net.receiver.ThreadingServerReceiverControlBase
    PATCH_BASE_CLS = patch.StreamerPatchCommand

    def command_sequence(self, *args, start: bool, **kwargs) -> Optional[Iterable[signalling.Command]]:
        if start:
            recorder = rgb_task.Recorder_Create(
                process_id=self.process_id,
                input_filter_id=self.filter_id,
                fps=self.fps,
                recording_dir=self.recording_dir,
                recording_basename=self.recording_basename
            )
            recorder.process_id = self.process_id
            yield recorder

            receiver_patch = patch.StreamerPatchCommand(
                RGBRecorder._patch_selector,
                RGBRecorder._patcher,
                self._build_patch_id(self.tunnel_id)
            )
            # TODO: test that what happen if this assignment not made
            receiver_patch.process_id = self.process_id

            yield receiver_patch

            remote = RecorderRemote_Create(
                self.process_id,
                self.filter_id,
                self.notifier_property
            )
            remote.process_id = self.process_id
            remote.recorder_id = self._build_recorder_id(
                self._get_common_id(self.tunnel_id))
            yield remote

            yield rgb_task.Recorder_Start(
                self.process_id,
                self.filter_id,
                True
            )
            yield RecorderRemote_Start(
                self.process_id,
                self.filter_id,
                self.start_immediately
            )
        elif self.process_id is not None and self.filter_id is not None:
            yield rgb_task.Recorder_Stop(self.process_id, self.filter_id)

            yield rgb_task.Recorder_Delete(self.process_id, self.filter_id)

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

    PATCHED_COMMAND = rgb_task.RecorderRemote_Create

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
            RGBRecorder.PATCHED_COMMAND
        )

        return check_handler and check_command

    @classmethod
    def _patcher(cls,
                 control: messenger.ReplyControl,
                 callback: messenger.PromiseControlCallback
                 ) -> Any:
        command: cls.PATCHED_COMMAND = control.reply_status.reply_msg
        assert isinstance(command, RGBRecorder.PATCHED_COMMAND)

        result = callback(control)

        process = command.backend__process
        common_id = cls._get_common_id(command.recorder_id)

        assert isinstance(process, backend_context.ExtendedBackendProcess)
        tunnel_id = cls._build_tunnel_id(common_id)

        tunnel_source = RGBRecorder.TUNNEL_SOURCE_LOOKUP_CLS.backend__lookup(
            process, tunnel_id
        )

        if tunnel_source is None:
            return

        channel: notifier.UpdateChannel = tunnel_source.backend__update_channel

        channel.subscribe(command.backend__activation_channel.send)

        # send updates about record status
        patch_control = patch.StreamerPatchCommand.backend__get_control(
            process.context,
            cls._build_patch_id(common_id)
        )

        def send_notify(update: notifier.Update):
            change = update.extract_nested_value()

            process.backend_messenger.deferred_reply(
                patch_control,
                cls.create_notify(change, command.metadata.recording_status)
            )

        command.metadata.activation_channel.subscribe(send_notify)

        return result

    @classmethod
    def create_notify(cls, change: bool, metadata: rgb_task.CurrentRecording) -> RecordingStatusUpdate:
        return RecordingStatusUpdate(
            metadata.started,
            metadata.finished,
            metadata.filepath
        )

    @classmethod
    def _build_tunnel_id(cls, common_id: Any) -> Tuple:
        return (cls.TUNNEL_BASE_CLS, common_id)

    @classmethod
    def _build_recorder_id(cls, common_id: Any) -> Tuple:
        return (cls.THREADING_RECEIVER_BASE_CLS, common_id)

    @classmethod
    def _build_patch_id(cls, common_id: Any) -> Tuple:
        return (cls.PATCH_BASE_CLS, common_id)

    @classmethod
    def _get_common_id(cls, id: Tuple) -> Any:
        return id[1]
