import functools
from functools import partial
import collections
import builtins
import inspect
from dataclasses import is_dataclass, fields, dataclass
from typing import Union, Callable, Dict, Any, Mapping, Sequence, Literal, MutableMapping
import operator

import os.path


def abs_path(relative_path: str):
    # ROOT_PATH from main.py
    return os.path.join(ROOT_PATH, relative_path)

## TODO: erase the decorators from the stacktrace

def print_exception(func):
    # global print
    # import builtins
    # from multiprocessing import current_process
    # print = lambda *args, **kwargs: builtins.print(current_process().name, *args, **kwargs)
    
    @functools.wraps(func)
    def inner(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception as e:
            print(e)
            raise e
    
    return inner

def log_context(prefix_str: str):
    global print
    
    print = functools.partial(builtins.print, prefix_str)


## WARNING: Do NOT use for class method, use it for instance methods
def run_once_strict(func):
    @functools.wraps(func)
    def inner(*args, **kwargs):
        
        if not inner.is_ran:
            func(*args, **kwargs)
            inner.is_ran = True
        else:
            raise RuntimeError('Function did run before')
    
    inner.is_ran = False
    return inner

# def print_prefix_context():
#     def print(*objs, **kwargs):
#             builtins.print(
#                 f"<{multiprocessing.current_process().name}>", *objs, **kwargs)

# no check on whether input classes are the same type (when object2 is an object)
# return: new object when object2 is None, else nothing
def copy_dataclass(object1: object, object2: Union[object, None]):
    assert is_dataclass(object1)
    obj_fields = fields(object1)
    
    if object2 is None:
        assert is_dataclass(object2)
        return object1.__class__(**obj_fields)
    
    # else assign values one-by-one
    for field in fields(object1):
        setattr(object2, field.name, getattr(object1, field.name))

# Apply annotate-correct parameters
def safe_apply(call: Callable, kwargs: Mapping[str, Any]):
    return call(**get_parameter_mapping(call, kwargs))

# Get annotate-correct-parameters
def get_parameter_mapping(call: Callable, kwargs: Mapping[str, Any]) -> Mapping[str, Any]:
    fn_parameters = inspect.signature(call).parameters
    has_vararg = any([p.kind == p.VAR_KEYWORD for p in fn_parameters.values()])

    def check_typehint(name, parameter: inspect.Parameter) -> bool:
        return (parameter.annotation == parameter.empty
                or parameter.annotation == type(kwargs[name]))

    calling_params = {name: kwargs[name] for name, par in fn_parameters.items()
                      if name in kwargs and check_typehint(name, par)}

    if has_vararg:
        incorrent_params = (
            kwargs.keys() & fn_parameters.keys()) - calling_params
        return kwargs - incorrent_params

    return calling_params

# returns item or function if has asterisk in pointer
# in case when only one value factory given, it is applied universally for all missing values
def contextual_pointer(root_dict: MutableMapping,
                       pointer_list: Sequence[Union[str, Literal['*']]],
                       *value_factories: Sequence[Callable[[], Any]],
                       force_callable: bool = False
                       ) -> Union[Any, Callable]:
    ASTERISK = '*'
    asterisk_num = len(list(filter(partial(operator.eq, ASTERISK), pointer_list)))
    
    # factory-related
    # f_len = 1 -> universal factory
    # f_len > 1 BUT len < asterisk_num -> ERROR
    # f_len > 1 and len > asterisk_num -> ok
    f_len = len(value_factories)

    if not f_len or 1 < f_len < len(pointer_list):
        raise RuntimeError(f"Not enough value factory, expected 1"
                           f" or at least {len(pointer_list)}, got {f_len}")
    
    def fn(*extra_parameters):
        source = root_dict
        extras_list = iter(extra_parameters)
        
        for i, ptr in enumerate(pointer_list):
            if ptr == ASTERISK:
                try:
                    ptr = next(extras_list)
                except StopIteration:
                    raise RuntimeError(f"Not enough parameters for substitution,"
                                       f" expected {asterisk_num}, got {len(extra_parameters)}")

            # check if factory needed
            if ptr not in source:
                factory = value_factories[0]
                if f_len > 1:
                    factory = value_factories[i]
                
                source[ptr] = factory()
            
            source = source[ptr]
        
        return source
    
    if asterisk_num or force_callable:
        return fn
    return fn()

@dataclass
class Callback:
    target: Callable
    args: Sequence
    kwargs: Mapping
    
    def __call__(self, *args: Any, **kwds: Any) -> Any:
        args = list(self.args).extend(args)
        kwargs = dict(self.kwargs).update(kwds)
        
        self.target(*args, **kwargs)

## Broken implementation - Must be nested OverlayDict to work correctly
# class OverlayDict(collections.UserDict):
#     def __init__(self, data = None):
#         super().__init__(data)
        
#         self._roots = ()
    
#     def set_roots(self, *data_sources: Sequence[Mapping]):
#         self._roots = data_sources
    
#     def __getitem__(self, key: Any) -> Any:
#         try:
#             return super().__getitem__(key)
#         except KeyError:
#             for source in self._roots:
#                 if key in source:
#                     return source[key]
        
#         raise KeyError
    
#     def __contains__(self, key: object) -> bool:
#         if super().__contains__(key):
#             return True
        
#         for source in self._roots:
#             if key in source:
#                 return True
        
#         return False
    