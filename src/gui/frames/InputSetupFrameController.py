import functools
from functools import partial
from dataclasses import dataclass
import enum
from typing import Optional, Dict, Tuple, Callable, Any, Mapping, List, Type
import wx
import operator

from wx import SizeEvent

from IFrameProcessAdapter import IFrameProcessAdapter, DrawingCallback

from gui.frames.wx_controller import wx_controller
from gui.frames.windows.InputSetupFrameView import InputSetupFrameView

from gui.frames.IWxFrameController import IWxFrameController


from gui.controls.VideoCapturePanelGrid import VideoCapturePanelGrid, VideoPanelPosition

import notifier
from messaging.topic import ReplyControl, SentMessage, MessageThreadRegistry

from socketserver import ThreadingTCPServer, TCPServer

import net.receiver
from net.parser.JSONParser import JSONParser

import control.signalling as signalling
import gui.controls.wx_form as wx_form
import gui.resource

import videorotate_constants

from gui.frames.JSONHandlerConfiguratorController import JSONHandlerConfiguratorController

import gui.backend.event.receiver as event_receiver
import gui.backend.event.processing as event_processing

from gui.backend.stages.RGBFilterTerminal import RGBFilterTerminal
from gui.backend.stages.ThreadedEventReceiver import ThreadedEventReceiver

import gui.datamodel

FrameAdapterFactory = Callable[[], IFrameProcessAdapter]


@wx_controller
class InputSetupFrameController(IWxFrameController):
    TASK = 'task'
    EVT_PROPERTY = 'akarmi'

    class ViewClass(InputSetupFrameView):
        def __init__(self, controller, parent):
            InputSetupFrameView.__init__(self, parent)

            self._controller = controller
            #self.triggerConfigBtn.Show(False) # default: Manual
            self.configuredFlagTextLabel.Show(False) # default: Manual
            self.Layout()
            
            self.triggerConfigBtn.Bind(wx.EVT_BUTTON, self.show_configurator) # default: Manual
            
            self.driverChoice.Bind(wx.EVT_CHOICE, self.on_driver_selected)
            
            self.submitBtn.Bind(wx.EVT_BUTTON, self._controller.send_data)
            
        
        def get_form_data(self) -> gui.datamodel.Recorder:
            event_driver = None
            cur_selection = self.recordingTypeChoice.GetStringSelection()
            
            driver_type = gui.datamodel.EventHandlerType(cur_selection)
            if self._controller.driver_setup_done and driver_type == gui.datamodel.EventHandlerType.TRIGGER:
                event_driver = gui.datamodel.EventDriver(
                    ThreadedEventReceiver,
                    {}
                )
            
            recorder_parameters = dict(self._setup_form.get_values())
            
            recorder_parameters.update({
                'filter_parameters': {
                    'width': recorder_parameters['width'],
                    'height': recorder_parameters['height'],
                },
                'filter': 'preview',
                'filter_module': 'preview',
                'parent_id': None
            })
            
            
            return gui.datamodel.Recorder(
                name=self.streamNameTextCtrl.GetValue(),
                recorder_stage=RGBFilterTerminal,
                recorder_parameters=recorder_parameters,
                recording_dir=self.recorderOutputDirCtrl.GetPath(),
                event_driver=event_driver
            )
        
        def _build_form(self):
            self._setup_form, submit_channel = gui.resource.assemble_form(
                self,
                signalling.LinearStageBuilder(
                    self._controller.task_context
                ).generate_order([RGBFilterTerminal]),
                False
            )

            self.sourceSetupFormHolder.set_form(self._setup_form)
        
        def on_driver_selected(self, evt: wx.CommandEvent):
            # show button when selection is not on 'Manual', the first item
            self.triggerConfigBtn.Show(bool(evt.GetInt()))
            self.Layout()
            evt.Skip()
        
        def show_configurator(self, evt: wx.CommandEvent):
            self.show_json_configurator()
            evt.Skip()
        
        def show_json_configurator(self, show: bool = True):
            self._controller.show_json_handler_configurator(show)
            self.Refresh()
        
        def set_json_configured(self):
            self.configuredFlagTextLabel.Show(True)

    def __init__(self):
        self._view = self.ViewClass(self, None)
        # self._messenger_registry = MessageThreadRegistry()
        
        self._json_listener_settings = None
        self._json_trigger_settings = None
        
        self._json_handler_configurator = None
        
        self.driver_setup_done = False

    # update.value is gui.datamodel.Recorder
    @functools.cached_property
    def on_form_completed(self) -> notifier.UpdateChannel:
        return notifier.UpdateChannel()
    
    @property
    def task_context(self) -> signalling.MessagingContext:
        return self._task_context
    
    @task_context.setter
    def task_context(self, context: signalling.MessagingContext):
        self._task_context = context

    @property
    def wx_frame(self) -> wx.Frame:
        return self._view

    def recv_message(self, message: SentMessage) -> None:
        # self.messenger.process_new_message(
        #     self._messenger_registry, message)
        pass

    def show_window(self, show: bool = True):
        self._view._build_form()
        
        self._view.Show(show)
        
        
        #self.show_json_handler_configurator()
    
    
    def show_json_handler_configurator(self, show: bool = True):
        if self._json_handler_configurator is None:
            self._json_handler_configurator: JSONHandlerConfiguratorController = self.wx_process.process__new_controller(JSONHandlerConfiguratorController, self)
        
            self._json_handler_configurator.task_context = self.task_context
            self._json_handler_configurator.on_form_completed.subscribe(self._handle_json_configurator_complete)
        
        self._json_handler_configurator.show_window(show)
        #self._handler_controller.on_save()
    
    def _handle_json_configurator_complete(self, update: notifier.Update):
        assert isinstance(update, notifier.Update)
        
        self._json_listener_settings, self._json_trigger_settings = update.value
        assert isinstance(self._json_listener_settings, Mapping)
        assert isinstance(self._json_trigger_settings, List)
        
        self._view.set_json_configured()
        self.show_json_handler_configurator(False)
        self._json_handler_configurator = None
        
        self.driver_setup_done = True
    
    
    def send_data(self, evt):
        collected_data = self._view.get_form_data()
        
        if (self._json_listener_settings is not None
            and self._json_trigger_settings is not None
            and collected_data.event_driver is not None):
            
            driver_params: Dict = collected_data.event_driver.provider_parameters
            driver_params.update(self._json_listener_settings)
            driver_params.update({
                'processor': net.receiver.EventProcessor(
                    self.EVT_PROPERTY,
                    JSONParser,
                    event_receiver.BinaryRuledTrigger(self._json_trigger_settings)
                ),
                'notifier_property': self.EVT_PROPERTY
            })
        
        self.on_form_completed.send(
            notifier.Update(
                key=InputSetupFrameController,
                value=collected_data
            )
        )


    
    

