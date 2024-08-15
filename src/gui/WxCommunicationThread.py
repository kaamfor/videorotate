from enum import Enum
from functools import cached_property
from typing import Callable, Optional, Any
from threading import Thread, Event
from multiprocessing.connection import Connection
import sys
import wx
import wx.lib.newevent

import messenger

from gui.frames.IWxFrameController import IWxFrameController


from backend_context import ProcessShutdownSequence

from videorotate_utils import print_exception, log_context
import videorotate_constants

OnMessageReceivedCallback = Callable[[messenger.SentMessage], Any]

class WxCommunicationThread(Thread):
    TIMEOUT: float = 10.0

    @property
    def thread__on_message_received(self) -> OnMessageReceivedCallback:
        return self._thread__on_message_received
    
    @thread__on_message_received.setter
    def thread__on_message_received(self, cb: OnMessageReceivedCallback):
        #assert isinstance(cb, OnMessageReceivedCallback)
        
        self._thread__on_message_received = cb
    
    @property
    def backend_socket(self) -> messenger.BindableSocket:
        return self._backend_socket
    
    @backend_socket.setter
    def backend_socket(self, backend_socket: messenger.BindableSocket):
        assert isinstance(backend_socket, messenger.BindableSocket)
        
        self._backend_socket = backend_socket
    
    @property
    def wx_configurator_socket(self) -> messenger.BindableSocket:
        return self._wx_configurator_socket
    
    @wx_configurator_socket.setter
    def wx_configurator_socket(self, wx_configurator_socket: messenger.BindableSocket):
        assert isinstance(wx_configurator_socket,
                          messenger.BindableSocket)
        
        self._wx_configurator_socket = wx_configurator_socket

    def stop(self):
        pass

    def setup(self):
        pass

    def _backend__setup(self):
        assert self.backend_socket is not None
        assert self.wx_configurator_socket is not None
        assert self.thread__on_message_received is not None
        
    @print_exception
    def run(self) -> None:
        print('Wx Communication thread started')
        sys.stdout.flush()
        
        self._backend__setup()
        
        detector = messenger.message_receive_detector([
            self.backend_socket,
            self.wx_configurator_socket
        ], self.TIMEOUT)
        
        stop_loop = False
        for socket_list in detector:
            for socket in socket_list:
                
                message = socket.recv_message_blocking(self.TIMEOUT)
                
                if videorotate_constants.DEBUG:
                    print(f"CommThread: received message")
                    sys.stdout.flush()
                
                if socket == self.backend_socket:
                    self.thread__on_message_received(message)
                
                elif isinstance(message, ProcessShutdownSequence):
                    stop_loop = True
                    break
            
            if stop_loop:
                break
        
        print('Wx Communication thread stopped')
        sys.stdout.flush()
