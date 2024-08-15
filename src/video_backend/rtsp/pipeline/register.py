
_registered_static_transforms = {}
def register_static_transform(transform_cls: type) -> None:
    assert transform_cls.__class__ == type, "register class types only"
    
    name_lower = str(transform_cls.__name__).lower()
    _registered_static_transforms[name_lower] = transform_cls

def get_static_transform(name: str) -> type:
    name_lower = str(name).lower()
    
    if name_lower in _registered_static_transforms:
        return _registered_static_transforms[name_lower]
    return None

def is_static_transform(cls) -> bool:
    return cls in _registered_static_transforms.values()

# decorator
def static_transform(transform_cls: type):
    register_static_transform(transform_cls)
    
    def inner(*args, **kwargs):
        transform_cls(*args, **kwargs)
    return inner