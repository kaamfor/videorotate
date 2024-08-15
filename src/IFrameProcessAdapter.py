from typing import Callable, Tuple, Any, Optional
from functools import cached_property
from abc import ABC, abstractmethod

import numpy as np
import wx

# mediator? pattern
#
# interface

DrawingCallback = Callable[[np.ndarray], None]

# Not an ABC
class IFrameProcessAdapter:

    class TriggerStreaming(ABC):
        
        # @cached_property
        # def notifier(self) -> PropertyChangeNotifier:
        #     return PropertyChangeNotifier()
        
        @property
        def streaming_notifier_property(self) -> str:
            return 'streaming'
        
        @property
        @abstractmethod
        def started(self) -> bool:
            pass
        
        @property
        @abstractmethod
        def drawing_callback(self) -> DrawingCallback:
            pass
        
        @property
        def timer_owner(self) -> wx.Window:
            return self._timer_owner
        
        @property
        def pending_owner(self) -> Optional[wx.Window]:
            return getattr(self, '_pending_owner', None)
        
        # Allow change at runtime
        @drawing_callback.setter
        @abstractmethod
        def drawing_callback(self, callback: Callable):
            pass
        
        def set_new_owner(self, related_window: wx.Window):
            if self.started:
                self._pending_owner = related_window
            else:
                self._timer_owner = related_window
                self._pending_owner = None
        
        @abstractmethod
        def start_streaming(self):
            pass
        
        @abstractmethod
        def stop_streaming(self):
            pass

    # access when input is available
    @property
    def width(self) -> int:
        return 0
    
    # access when input is available
    @property
    def height(self) -> int:
        return 0

    # overridden by the input block implementor if needed
    def backend__input__setup(self):
        pass

    # overridden by the input block implementor if needed
    def backend__input__cleanup(self):
        pass

    # overridden by the input block implementor if needed
    def backend__input__grab_frame(self,
                                   ignore_cache: bool = False,
                                   invalidate_cache: bool = False,
                                   cache_new_frame_descriptor: bool = False
                                   ) -> Tuple[bool, np.ndarray, any]:
        raise NotImplementedError()

    # overridden by the input block implementor if needed
    def backend__input__is_ready(self, ignore_cache: bool) -> bool:
        return False
    
    # overridden by the input block implementor if needed
    def backend__input__set_callback(self, cb: Callable[[bool, np.ndarray, any], Any]):
        raise NotImplementedError()

    # overridden by the input block implementor if needed
    def backend__input__is_callback_available(self) -> bool:
        return False
