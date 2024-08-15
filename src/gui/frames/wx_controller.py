from typing import Callable

#from gui.frames.IWxFrameController import IWxFrameController

_registered_wx_controllers = {}
def register_wx_controller(controller_cls) -> None: #: IWxFrameController) -> None:
    ################assert isinstance(controller_cls, IWxFrameController)
    
    name_lower = str(controller_cls.__name__).lower()
    
    _registered_wx_controllers[name_lower] = controller_cls
    print(_registered_wx_controllers)

def get_wx_controller(name: str): # -> IWxFrameController:
    name_lower = str(name).lower()
    
    if name_lower in _registered_wx_controllers:
        return _registered_wx_controllers[name_lower]
    return None

# decorator
def wx_controller(controller):
    register_wx_controller(controller)
    
    return controller

# decorator
def on_notify_change(property_id):
    def inner(method: Callable):
        method.notify_property_id = property_id
        return method
    return inner