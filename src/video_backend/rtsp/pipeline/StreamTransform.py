
class StreamTransform:
    def __init__(self, **kwargs) -> None:
        for k,v in kwargs.items():
            self[k] = v