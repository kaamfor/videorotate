import wx
import cv2
import functools
from functools import partial
import operator
from typing import Any, Dict, Optional

from messaging.topic import ReplyControl, SentMessage, MessageThreadRegistry

from gui.frames.IWxFrameController import IWxFrameController
from gui.frames.wx_controller import wx_controller

from gui.frames.windows.JSONHandlerConfiguratorView import JSONHandlerConfiguratorView
from gui.controls.wx_form import SingleControlForm, IndentedDataDisplay

from socketserver import TCPServer, ThreadingTCPServer, BaseServer

import gui.controls.wx_form as wx_form
import control.signalling as signalling
import notifier

import gui.resource
import gui.backend.event.receiver as event_receiver

from videorotate_typedefs import Number, Alphanumeric

from gui.backend.stages.ThreadedEventReceiver import ThreadedEventReceiver

# hátravan: JSON fogadás, státusz üzenetek kirakása, IP+port változás-applikálás esetén új állapotgép

@wx_controller
class JSONHandlerConfiguratorController(IWxFrameController):
    TASK = 'JSONHandlerConfiguratorController'
    
    RECEIVER_STAGE = ThreadedEventReceiver
    class ViewClass(JSONHandlerConfiguratorView):
        def __init__(self, controller, parent):
            JSONHandlerConfiguratorView.__init__(self, parent)
            
            self._controller: JSONHandlerConfiguratorController = controller
            
            self.listenerStatusText.SetLabelText('')
            
            self.submitBtn.Bind(wx.EVT_BUTTON, self.send_data)
            self.applyBtn.Bind(wx.EVT_BUTTON, self.toggle_receiver)
            self.listenerStatusText.SetLabelText('Stopped')
            
            # create new triggerserver on change and apply
            self._receiver = None
        
        def send_data(self, evt):
            self._controller.on_form_completed.send(
                notifier.Update(
                    key=JSONHandlerConfiguratorController,
                    value=[
                        self.formHolder.get_values(),
                        list(self._rule_dashboard.tab_list)
                    ]
                )
            )
        
        def toggle_server(self, _: wx.CommandEvent):
            self._controller.test_server.toggle()
        
        def show_json_message(self, message: Dict):
            pass
        
        def initiate_listener_form(self, target_stage: signalling.Stage):
            form, channel = gui.resource.assemble_form(
                self.settingsPanel, [target_stage], False
            )
            self.formHolder.set_form(form)
        
        def set_server_control(self, receiver: event_receiver.JSONReceiverControl):
            self._receiver = receiver
            
            self._receiver.update_channel.subscribe(self.update_display)
        
        # TODO: subscribe to message instead of immediate check?
        def toggle_receiver(self, evt):
            if self._receiver is not None:
                if not self._receiver.started:
                    self._receiver.start()
                    self.listenerStatusText.SetLabelText('Started')
                else:
                    self._receiver.stop()
                    self.listenerStatusText.SetLabelText('Stopped')
        
        def update_display(self, update: notifier.MultiContextUpdate):
            self.append_test_data(update.extract_nested_value())

    @property
    def task_context(self) -> signalling.MessagingContext:
        return self._task_context

    @task_context.setter
    def task_context(self, context: signalling.MessagingContext):
        self._task_context = context
    
    # update.value is List[json_server_form_values, trigger_conditions_list]
    @functools.cached_property
    def on_form_completed(self) -> notifier.UpdateChannel:
        return notifier.UpdateChannel()
    
    @property
    def wx_frame(self) -> wx.Frame:
        return self._view

    @property
    def json_receiver(self) -> Optional[event_receiver.JSONReceiverControl]:
        return self._json_receiver
    
    @json_receiver.setter
    def json_receiver(self, receiver: event_receiver.JSONReceiverControl):
        assert isinstance(receiver, event_receiver.JSONReceiverControl)
        
        self._json_receiver = receiver
        self._view.set_server_control(receiver)

    def __init__(self):
        IWxFrameController.__init__(self)
        self._view = self.ViewClass(self, None)
        
        self._json_receiver = None
        
        self.__init_configurator()

    def __init_configurator(self):
        # self._view.Refresh()
        self._view.Layout()

    def recv_message(self, message: SentMessage) -> None:
        # TODO: other classes which are not MainWindowController?
        pass

    def show_window(self, show: bool = True):
        if show and self.json_receiver is None:
            recv_control = event_receiver.JSONReceiverControl(
                self.task_context,
                'akarmi'
            )
            self._view.initiate_listener_form(self.RECEIVER_STAGE)
            
            recv_control.initiate_receiver(
                event_receiver.JSONReceiverParameters(
                    self.RECEIVER_STAGE,
                    self._view.formHolder,
                    'akarmi'
                )
            )
            
            self.json_receiver = recv_control
        elif not show and self.json_receiver is not None:
            self.json_receiver.stop()
        
        self._view.Show(show)