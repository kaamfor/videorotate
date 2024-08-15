import functools
from functools import partial
import itertools
from dataclasses import dataclass
from typing import Optional, Dict, Tuple, Callable, Any, Mapping, Union, Sequence, Type, MutableMapping
import wx
import numpy as np
import cv2
from threading import Thread
import os
import glob
import operator
import random

from wx import SizeEvent

from IFrameProcessAdapter import IFrameProcessAdapter, DrawingCallback

from gui.frames.InputSetupFrameController import InputSetupFrameController

from gui.frames.wx_controller import wx_controller
from gui.frames.windows.MainWindowView import MainWindowView

from gui.frames.IWxFrameController import IWxFrameController
from net.receiver import ChangeEvent, IncomingEvent


from gui.controls.VideoCapturePanelGrid import VideoCapturePanelGrid, VideoPanelPosition

from video_backend.rtsp.filterchain import DecoderSpec, RGBDecodingTerminalData, RGBProcessLink, ShmemRGBClient, RGBAdapter, RTSPStreamSpec
import video_backend.rgb_task as rgb_task

from video_backend.consumer import RGBSharedMemoryAdapter

from messaging.topic import ReplyControl, SentMessage, MessageThreadRegistry

from socketserver import ThreadingTCPServer, TCPServer

from video_backend.consumer import Consumer

import videorotate_constants

import control.signalling as signalling
import notifier

import video_backend.rtsp.rtsp_task as rtsp_task
import video_backend.rgb_task as rgb_task

import control.generic_resource as generic_resource
import net.receiver as receiver
from net.parser.JSONParser import JSONParser

from gui.backend.stages.RGBFilterChange import RGBFilterChange
from gui.backend.stages.RGBFilter import RGBFilter
from gui.backend.stages.RGBFilterTerminal import RGBFilterTerminal
from gui.backend.stages.RGBRecorder import RGBRecorder, RecordingStatusUpdate
from gui.backend.stages.ThreadedEventReceiver import ThreadedEventReceiver

from gui.frames.JSONHandlerConfiguratorController import JSONHandlerConfiguratorController

import gui.datamodel

import gui.backend.event.processing as event_processing
import gui.backend.event.receiver as event_receiver
import net.receiver
import backend_context

import event.tunneling
import control.patch as patch

import control.config


@dataclass
class VideoPanelResizeHandler:
    target_resource_id: Any
    panel: wx.Panel
    resize_filter_id: Any
    
    def __call__(self, evt: wx.SizeEvent) -> Any:
        parameters = {}
        parameters['width'], parameters['height'] = self.panel.GetClientSize()

        #change = RGBFilterChange()

        return rgb_task.FilterParameterChangeCommand(
            self.resize_filter_id,
            parameters,
            self.target_resource_id
        )
    
    def get_size(self) -> Tuple[int, int]:
        return self.panel.GetClientSize()

@wx_controller
class MainWindowController(IWxFrameController):
    TASK = 'task'

    class ViewClass(MainWindowView):
        @functools.cached_property
        def panel_resize_update(self) -> notifier.UpdateChannel:
            return notifier.UpdateChannel()
        
        def __init__(self, controller, parent):
            MainWindowView.__init__(self, parent)

            self.controller: MainWindowController = controller
            
            src_btn_id = self.AddRTSPCameraBtn.GetId()
            self.Bind(wx.EVT_TOOL, self.on_new_rtsp_source, id=src_btn_id)
            
            self._project_file: Optional[str] = None
            
            save_btn_id = self.saveProjectBtn.GetId()
            self.Bind(wx.EVT_TOOL, self.on_save_project, id=save_btn_id)
            load_btn_id = self.loadProjectBtn.GetId()
            self.Bind(wx.EVT_TOOL, self.on_load_project, id=load_btn_id)

        def on_load_project(self, evt):
            paths = self.loadProjectDialog()
            if isinstance(paths, Sequence) and len(paths):
                project_file = paths[0]
                
                new_recorders = control.config.load_config(project_file)
                
                self.controller.new_recorders(new_recorders)

            evt.Skip()
        
        def on_save_project(self, evt):
            paths = self.saveProjectDialog()
            if isinstance(paths, Sequence) and len(paths):
                target_file = paths[0]
                target_file_suffix = '.conf'
                if not target_file.endswith(target_file_suffix):
                    target_file += target_file_suffix
                
                # TODO is file writable?
                
                control.config.save_config(target_file, self.controller._recorders)

            evt.Skip()

        def _stream(self, recorder_name: str, shmem_img: rgb_task.RGBSharedMemoryImage) -> (RGBSharedMemoryAdapter, VideoCapturePanelGrid.SinglePanel):
            self.controller._pending_recorders[recorder_name] = False
            
            if videorotate_constants.DEBUG:
                import sys
                print('SHMEM in _stream fn', shmem_img)
                sys.stdout.flush()

            assert isinstance(shmem_img, rgb_task.RGBSharedMemoryImage)

            adapter = RGBSharedMemoryAdapter(shmem_img)
            adapter.backend__input__setup()

            panel = self.add_streaming_video(shmem_img)
            
            self.controller.update_progressbar()

            return adapter, panel
        
        
        def on_new_rtsp_source(self, evt):
            self.controller.open_rtsp_source_dialog()
            evt.Skip()

    def __init__(self):
        self._view = self.ViewClass(self, None)

        # self.startNewProject("[Új]")

        # add_video_panel().Bind(...)

        self._video_adapters: Dict[IFrameProcessAdapter] = {}
        
        self._panel_handler = {}

        self._recorders: MutableMapping[str, gui.datamodel.Recorder] = {}
        self._view.on_stream_select(self.start_streaming)

        #self.stream_preview_tasks: Dict[str, RTSPTask] = {}
        

        self._messenger_registry = MessageThreadRegistry()
        
        self._setup_controller = None
        
        # TODO: unify with videoPanelGrid
        self._pending_recorders = {}
        
        self._slot_id_generator = itertools.count()
        
        self._view.Bind(wx.EVT_CLOSE, self.on_exit)

    @property
    def task_context(self) -> signalling.MessagingContext:
        return self._task_context

    @property
    def wx_frame(self) -> wx.Frame:
        return self._view

    def recv_message(self, message: SentMessage) -> None:
        self.messenger.process_new_message(
            self._messenger_registry, message)

    def show_window(self, show: bool = True):
        self._setup()
        
        self._view.Show(show)
    
    def _setup(self):
        self._task_context = self.messenger.new_topic(self.TASK)
        self._task_context.registry_channel.subscribe(
            lambda update: self._messenger_registry.append(update.value)
        )
    
    def on_exit(self, evt):
        self._view.Destroy()
    
    def start_streaming(self, recorder_name: str):
        if recorder_name in self._pending_recorders:
            return
        
        self._pending_recorders[recorder_name] = True
        recorder = self._recorders[recorder_name]
        
        self.update_progressbar()
        
        recorder.recorder_parameters['slot_id'] = next(self._slot_id_generator)
        
        recorder.recorder_parameters['parent_id'] = None
        filter_params = recorder.recorder_parameters.setdefault('filter_parameters', {})
        filter_params['is_recording'] = False if recorder.event_driver is not None else None
        
        live_controller = signalling.LinearStageBuilder(self.task_context)
        live_controller.add_parameters(recorder.recorder_parameters)
                
        filter_state = live_controller.stage_state(RGBFilter)
        
        progress = live_controller.set_target(recorder.recorder_stage, start=True, target_go_immediate=False)
        
        # callback-hell begins
        filter_state.command_notify.thenPermanent(partial(self.set_filter_obj, recorder_name, self.task_context, progress))
        
        rem_control = event_receiver.RecorderRemoteControl(None, None, None, self.task_context)
        
        progress.completion_channel.thenPermanent(partial(self.create_recorder, recorder, rem_control))
        
        progress.go()

    def create_recorder(self,
                        recorder: gui.datamodel.Recorder,
                        rem_control: event_receiver.RecorderRemoteControl,
                        update: notifier.Update):
        terminal: RGBFilterTerminal = update.emitted_by
        
        process_id = terminal.process_id
        #filter_id = terminal.filter_id
        filter_id = None
        
        if recorder.event_driver is None or 'processor' not in recorder.event_driver.provider_parameters:
            return
        
        notifier_property = 'akarmi'
            
        #evt_receiver_params = dict(recorder.event_driver.provider_parameters)
        
        parameters = event_receiver.JSONReceiverParameters(
            recorder.event_driver.provider_stage,
            recorder.event_driver.provider_parameters,
            notifier_property,
            recorder.event_driver.provider_parameters['processor'].parser,
            recorder.event_driver.provider_parameters['processor'].distributor
        )
        
        recv_control = event_receiver.JSONReceiverControl(self.task_context, notifier_property)
        recv_control.initiate_receiver(parameters)
        
        recv_control.builder.add_parameters({
            'process_id': process_id,
            'filter_id': filter_id
        })
        
        ###### recv_control.update_channel.subscribe(partial(self.update, recorder, rem_control))
        
        # TODO: search for a type/subclass, not only an exact match (so ABCs could be used)
        tunnel_notify = recv_control.builder.stage_state(
            ThreadedEventReceiver).command_notify
        tunnel_notify.subscribe(
            partial(
                self._stage__build_recorder,
                recorder,
                rem_control,
                terminal
            )
        )

        recv_control.update_channel.subscribe(partial(self.metadata_received, terminal))

        recv_control.start()
    
    def metadata_received(self, terminal: RGBFilterTerminal, update: notifier.Update):
        status = update.extract_nested_value()
        
        if isinstance(status, RecordingStatusUpdate):
            if status:
                self.append_records([status.filepath])
            
            self.task_context.send(
                rgb_task.FilterParameterChangeCommand(
                    terminal.filter_id,
                    {
                        'is_recording': bool(status)
                    },
                    terminal.process_id # TODO: mixing concepts...!
                )
            )

    def display_existing_records(self, basedir: str):
        self.append_records(map(partial(os.path.join, basedir), glob.glob('*.mp4', root_dir=basedir)))
    
    def append_records(self, path_list: Sequence[str]):
        for filepath in path_list:
            # if self._view.RecordsListBox.HasClientData(filepath):
            #     continue
            
            i = self._view.RecordsListBox.Append(os.path.basename(filepath))
            self._view.RecordsListBox.SetClientData(i, filepath)

    def _stage__build_recorder(self,
                               recorder: gui.datamodel.Recorder,
                               rem_control: event_receiver.RecorderRemoteControl,
                               terminal: RGBFilterTerminal,
                               update: notifier.Update):
        
        assert isinstance(update, notifier.Update)
        tunnel = update.value
        if not isinstance(tunnel, event.tunneling.Tunnel_Create):
            return
        
        event_controller = signalling.LinearStageBuilder(self.task_context)
        event_controller.add_parameters(recorder.recorder_parameters)
        
        event_controller.add_parameters({
            'process_id': tunnel.process_id,
            # TODO
            #'filter_id': terminal.filter_id,
            'filter_id': None,
            'tunnel_id': tunnel.tunnel_id
        })
        
        # TODO
        event_controller.add_parameters({
            'recording_dir': recorder.recording_dir,
            'recording_basename': 'video',
            #'notifier_property': terminal.filter_id,
            'notifier_property': None,
            'start_immediately': False,
            
            'fps': 15
        })
        
        event_progress = event_controller.set_target(RGBRecorder, start=True)
        
        event_controller.stage_state(patch.StreamerPatchCommand).command_notify.subscribe(partial(self.metadata_received, terminal))

    
    def set_filter_obj(self, recorder_name: str, context: signalling.MessagingContext, progress: signalling.LinearBuilderProgress, update: notifier.Update):
        if not isinstance(update.value, rgb_task.Filter_Create):
            return
        
        resize_filter = update.value
        
        progress.completion_channel.subscribe(partial(self.start_stream, recorder_name, context, resize_filter))
    
    def start_stream(self, recorder_name: str, context: signalling.MessagingContext, resize_filter: rgb_task.Filter_Create, update: notifier.Update):
        
        from gui.backend.stages.RGBFilterTerminal import RGBFilterTerminal
        
        rgb_terminal_stage: RGBFilterTerminal = update.emitted_by
        shmem_img: rgb_task.RGBSharedMemoryImage = update.value[RGBFilterTerminal.O_TERMINAL_LINK]
        
        rgb_terminal_stage.shmem_image = shmem_img
        
        adapter, panel = self._view._stream(recorder_name, shmem_img)
        
        self.make_panel_resize_handler(recorder_name, context, resize_filter, adapter, panel, rgb_terminal_stage)
        
        # first resize to correct display
        self.handle_event(recorder_name, context, resize_filter, adapter, panel, rgb_terminal_stage, True, None)
    
    def make_panel_resize_handler(self,
                                  recorder_name: str,
                                  command_context: signalling.MessagingContext,
                                  command: Union[rgb_task.Filter_Create, rgb_task.FilterTerminal_Start],
                                  adapter: RGBSharedMemoryAdapter,
                                  panel: VideoCapturePanelGrid.SinglePanel,
                                  rgb_terminal_stage):
        from gui.backend.stages.RGBFilterTerminal import RGBFilterTerminal
        
        assert isinstance(command_context, signalling.MessagingContext)
        assert isinstance(command, Union[rgb_task.Filter_Create, rgb_task.FilterTerminal_Start])
        assert isinstance(panel, wx.Panel)
        assert isinstance(rgb_terminal_stage, RGBFilterTerminal)
        
        self._panel_handler[panel] = partial(self.handle_event, recorder_name, command_context,
                                             command, adapter, panel, rgb_terminal_stage, False)
        # TODO: handle unsubscribe!
        panel.Bind(wx.EVT_SIZE, self._panel_handler[panel])
        
        self._pending_recorders[recorder_name] = None

    # control is passed between functions cyclically
    def handle_event(self,
                     recorder_name: str,
                     command_context: signalling.MessagingContext,
                     command: Union[rgb_task.Filter_Create, rgb_task.FilterTerminal_Start],
                     adapter: RGBSharedMemoryAdapter,
                     panel: VideoCapturePanelGrid.SinglePanel,
                     rgb_terminal_stage,
                     force: bool,
                     evt) -> bool:

        from gui.backend.stages.RGBFilterTerminal import RGBFilterTerminal
        assert isinstance(rgb_terminal_stage, RGBFilterTerminal)
        
        
        sender = VideoPanelResizeHandler(
            command.target_resource_id,
            panel,
            command.filter_id
        )
        
        panel_size = sender.get_size()
        
        
        if getattr(panel, '__old_size', None) == panel_size:
            return False
        
        set_size_on = lambda obj: setattr(obj, '__old_size', panel_size)
        
        self._pending_recorders[recorder_name] = False
        
        panel.Unbind(wx.EVT_SIZE, handler=self._panel_handler[panel])
        
        def free_panel_on_stop(command, update: notifier.Update):
            if not isinstance(command, rgb_task.FilterTerminal_Stop):
                if isinstance(update, notifier.MultiContextUpdate):
                    update.context_channel.deregister_context()
                return
            
            assert isinstance(update.value, generic_resource.Result)
            if update.value.status == generic_resource.Status.OK:
                self._view.free_video_panel(panel)
                
                update.context_channel.deregister_context()
        
        for command in rgb_terminal_stage.command_sequence(start=False):
            #command_context.send(command)
            channel = command_context.send(
                notifier.Update(
                    key=type(command),
                    value=command,
                    emitted_by=rgb_terminal_stage
                )
            )
            channel.subscribe(partial(free_panel_on_stop, command))
        
        # TODO: channel? what to do?
        command_context.send(sender(evt))
        

        
        for command in rgb_terminal_stage.command_sequence(start=True):
            channel = command_context.send(
                notifier.Update(
                    key=type(command),
                    value=command,
                    emitted_by=rgb_terminal_stage
                )
            )
            
            if isinstance(command, rgb_task.FilterTerminal_Start):
                def catch(v: notifier.Update):
                    
                    assert isinstance(v, notifier.MultiContextUpdate)
                    
                    if isinstance(v.value, rgb_task.RGBSharedMemoryImage):
                        channel.unsubscribe(catch)
                        
                        adapter, panel = self._view._stream(recorder_name, v.value)
                        
                        # TODO: maybe related: make sure panel is created
                        self.make_panel_resize_handler(recorder_name,
                            command_context, command, adapter, panel, rgb_terminal_stage)
                        
                        set_size_on(panel)
                
                channel.subscribe(catch)
        
        return True

    #def display_setup_window(self):
    def open_rtsp_source_dialog(self):
        
        #operator.attrgetter('value') BinaryRuledTrigger(self._trigger_conditions or [])
        self._setup_controller: InputSetupFrameController = self.wx_process.process__new_controller(InputSetupFrameController, self)
            
        self._setup_controller.task_context = self.task_context
            
        self._setup_controller.on_form_completed.thenPermanent(self.process_input_setup)
        self._setup_controller.show_window()
        #self._setup_controller.on_save()


    def _property_streaming_videos(self, change):
        streaming_videos = change.prop_new_value

        if not isinstance(streaming_videos, list):
            return


    def process_input_setup(self, update: notifier.Update):
        assert isinstance(update, notifier.Update)
        assert isinstance(update.value, gui.datamodel.Recorder)
        recorder = update.value
        
        self.new_recorders({
            recorder.name: recorder
        })
        
        self._setup_controller.show_window(False)

    def new_recorders(self, recorders: Mapping[str, gui.datamodel.Recorder]):
        for name, recorder in recorders.items():
            if not os.path.exists(recorder.recording_dir):
                path_base = recorder.recording_dir
                path_compoments = []
                
                while not os.path.exists(path_base):
                    old_path_base = path_base
                    path_base, tail = os.path.split(path_base)
                    
                    if tail:
                        path_compoments.append(tail)
                    
                    if path_base == old_path_base:
                        break
                
                make_path = wx.MessageBox(
                    f"Creating recorder path with base dir {path_base} -> {'/'.join(path_compoments)}. Load project?:",
                    f"Loading project {name}",
                    wx.YES_NO,
                    parent=self._view
                )
                
                if make_path == wx.NO:
                    continue
                
                try:
                    for component in path_compoments:
                        path_base = os.path.join(path_base, component)
                        os.mkdir(path_base)
                        
                except Exception as e:
                    wx.LogMessage(f"Error: {e}")
            
            self.display_existing_records(recorder.recording_dir)
            
            self._recorders[name] = recorder
            self._view.InputStreamsListBox.Append(name)

    def update_progressbar(self) -> Sequence[str]:
        load_pending_recorders = [name for name,value in self._pending_recorders.items() if value == True]
        quantity = len(load_pending_recorders)
        
        if not quantity:
            self._view.set_activity(None)
        elif quantity < 2:
            self._view.set_activity(f"Loading: '{load_pending_recorders[0]}'")
        else:
            self._view.set_activity(f"Loading {quantity} streams")
        
        return load_pending_recorders

    def current_resizing_recorders(self) -> Sequence[str]:
        return [name for name, value in self._pending_recorders.items() if value == False]

