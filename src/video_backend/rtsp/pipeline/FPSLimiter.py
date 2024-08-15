
from valkka.core import TimeIntervalFrameFilter

from .StreamTransform import StreamTransform
from .register import static_transform

from .Middleware import Middleware

@static_transform
class FPSLimiter(StreamTransform):
    
    def get_middleware(self):
        return Middleware(
                    lambda child, name, connection_name:
                        TimeIntervalFrameFilter(
                            name,
                            1000 // 5,
                            child
                        ))