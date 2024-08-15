from typing import Callable, Sequence, Any

_registered_bgr_transforms = {}
def register_bgr_transform(transform: Callable) -> None:
    assert callable(transform), "register callable only"
    
    name_lower = str(transform.__name__).lower()
    
    _registered_bgr_transforms[name_lower] = transform

def get_bgr_transform(name: str) -> Callable:
    name_lower = str(name).lower()
    
    if name_lower in _registered_bgr_transforms:
        return _registered_bgr_transforms[name_lower]
    return None

# def is_bgr_transform(name: str) -> bool:
#     return name in _registered_bgr_transforms.values()

# decorator
def bgr_transform(transform: Callable):
    register_bgr_transform(transform)
    
    def inner(*args, **kwargs):
        transform(*args, **kwargs)
    return inner


def list_bgr_transforms() -> Sequence[Any]:
    return _registered_bgr_transforms.keys()
