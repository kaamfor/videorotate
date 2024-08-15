from functools import cached_property
from abc import ABC, abstractmethod
from typing import Optional
from multiprocessing import Queue
import wx

from messaging.topic import TopicMessaging, SentMessage
#from gui.wx_process import WxProcess

class IWxFrameController(ABC):
    
    @property
    def wx_process(self): # -> WxProcess:
        return self.__wx_process
    
    @wx_process.setter
    def wx_process(self, process): # process: WxProcess):
        self.__wx_process = process
    
    @property
    @abstractmethod
    def wx_frame(self) -> wx.Frame:
        pass
    
    @property
    def created_by(self):# -> Optional[IWxFrameController]:
        return self.__created_by
    
    @created_by.setter
    def created_by(self, created_by):
        assert created_by is None or isinstance(created_by, IWxFrameController)
        self.__created_by = created_by
    
    @property
    def messenger(self) -> Optional[TopicMessaging]:
        return self._messenger
    
    @messenger.setter
    def messenger(self, messenger: Optional[TopicMessaging]):
        assert isinstance(messenger, Optional[TopicMessaging])
        self._messenger = messenger
    
    @abstractmethod
    def recv_message(self, message: SentMessage) -> None:
        pass
    
    # @cached_property
    # def notifier(self) -> PropertyChangeNotifier:
    #     return PropertyChangeNotifier()
    
    # register or unregister controls
    # # @property
    # # def reply_control_queue(self) -> Queue:
    # #     return getattr(self, '_reply_control_queue', None)
    
    # # @reply_control_queue.setter
    # # def reply_control_queue(self, reply_control_queue: Queue):
    # #     #assert isinstance(reply_control_queue, Queue)
        
    # #     self._reply_control_queue = reply_control_queue
    
    @abstractmethod
    def show_window(self, show: bool = True):
        pass