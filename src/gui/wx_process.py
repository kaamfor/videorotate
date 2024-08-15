from functools import partial
from dataclasses import dataclass
from typing import Callable, Any, Union
from multiprocessing import Process
from threading import Thread
import sys
import wx
import wx.lib.inspection

from messaging.topic import TopicMessaging, SentMessage

from gui.frames.wx_controller import get_wx_controller
from gui.WxCommunicationThread import WxCommunicationThread

#from gui.frames.IWxFrameController import IWxFrameController

from backend_context import ProcessShutdownSequence
from ProcessSocket import ProcessSocket

from videorotate_utils import print_exception
import videorotate_constants
import orchestrator

class WxProcess(Process):
    
    @property
    def frontend_messenger(self) -> TopicMessaging:
        return getattr(self, '_frontend_messenger', None)
    
    @frontend_messenger.setter
    def frontend_messenger(self, frontend_messenger: TopicMessaging):
        assert isinstance(frontend_messenger, TopicMessaging)
        
        self._frontend_messenger = frontend_messenger
    
    @property
    def backend_messenger(self) -> TopicMessaging:
        return getattr(self, '_backend_messenger', None)
    
    @backend_messenger.setter
    def backend_messenger(self, backend_messenger: TopicMessaging):
        assert isinstance(backend_messenger, TopicMessaging)
        
        self._backend_messenger = backend_messenger
    
    
    @property
    def first_window_controller(self) -> str:
        return getattr(self, '_first_window_controller', None)
    
    @first_window_controller.setter
    def first_window_controller(self, first_window_controller):
        assert isinstance(first_window_controller, str)
        
        self._first_window_controller = first_window_controller
    
    @property
    def notifier_topic(self) -> str:
        return getattr(self, '_notifier_topic', None)
    
    @notifier_topic.setter
    def notifier_topic(self, notifier_topic: str):
        assert isinstance(notifier_topic, str)
        
        self._notifier_topic = notifier_topic

    def process__new_controller(self,
                       new_controller,#: Union[str, IWxFrameController],
                       source_controller):# -> IWxFrameController:
        #assert isinstance(source_controller, IWxFrameController)
        
        #if isinstance(new_controller, IWxFrameController):
        new_controller = new_controller.__name__
        #    new_controller = new_controller.__name__
        
        controller_i = self._process__new_window_controller(new_controller)
        controller = self._process__get_controller(new_controller, controller_i)
        controller.wx_process = self
        controller.messenger = self.backend_messenger
        
        controller.created_by = source_controller
        return controller

    @print_exception
    def run(self) -> None:
        print('GUI process started')
        sys.stdout.flush()
        
        # global ROOT_PATH
        # ROOT_PATH = root_path
        
        assert self.frontend_messenger is not None
        assert self.backend_messenger is not None
        assert self._first_window_controller is not None
        assert self.notifier_topic is not None
        
        self._app = wx.App(False)
        self._controllers = {}

        controller_i = self._process__new_window_controller(self._first_window_controller)
        
        controller = self._process__get_controller(self._first_window_controller, controller_i)
        controller.wx_process = self
        controller.messenger = self.backend_messenger
        controller.created_by = None
        controller.show_window()
        
        com_thread_config_socket = ProcessSocket.new_parameterless()
        
        com_thread = WxCommunicationThread()
        com_thread.backend_socket = self.backend_messenger.socket
        com_thread.wx_configurator_socket = com_thread_config_socket
        com_thread.thread__on_message_received = partial(wx.CallAfter, self._handle_message_in_controller, controller)
        
        if videorotate_constants.GUI_DEBUG:
            wx.lib.inspection.InspectionTool().Show()
        
        com_thread.setup()
        
        com_thread.start()
        
        self._app.MainLoop()
        
        print('GUI process: App MainLoop halted')
        sys.stdout.flush()
        
        
        status = ProcessShutdownSequence(
            process_id=None,
            expected=True,
            clean_shutdown=True
        )
        
        com_thread_config_socket.source.send(status)
        
        com_thread.join()
        
        self.backend_messenger.send_message(orchestrator.ProcessOrchestrator.TASK, status)
        
        print('GUI process stopped')
        sys.stdout.flush()

    def _handle_message_in_controller(self,
                                     controller,#: IWxFrameController,
                                     message: SentMessage):
        controller.recv_message(message)

    def _process__new_window_controller(self,
                                       controller_name: str) -> int:
        assert isinstance(controller_name, str)

        controller = get_wx_controller(controller_name)

        if controller is None:
            raise RuntimeError(f"Wx frame controller {controller_name} not found")

        if controller_name not in self._controllers:
            self._controllers[controller_name] = []

        controller_list: list = self._controllers[controller_name]

        index = len(controller_list)
        controller_list.insert(index, controller())

        return index

    def _process__get_controller(self,
                                controller_name: str,
                                controller_index: int):# -> IWxFrameController:
        return self._controllers[controller_name][controller_index]
