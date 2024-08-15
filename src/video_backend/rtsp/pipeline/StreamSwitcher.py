from valkka.core import FrameFilter, ForkFrameFilterN, SwitchFrameFilter

from .StreamTransform import StreamTransform
from .register import register_static_transform

class StreamSwitcher(StreamTransform):
    
    def __init__(self) -> None:
        super().__init__()
        
        self._stream_list = []
        self._switch = 0
    
    def switch_to(self, number: int):
        self._switch = number
    
    def add_to_fork(self, fork: ForkFrameFilterN) -> FrameFilter:
        jockey = SwitchFrameFilter()
        
        fork.connect(self.display_name, )

register_static_transform(StreamSwitcher)