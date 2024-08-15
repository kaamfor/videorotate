import functools
from functools import partial
from dataclasses import dataclass
import enum
from typing import Optional, Dict, Tuple, Callable, Any, Mapping, List, Type
import wx
import operator

import notifier
import control.signalling as signalling
import gui.controls.wx_form as wx_form
import gui.resource

# No connection with initial data of wxChoice
class EventHandlerType(enum.Enum):
    MONITOR = 'Monitor (No recording)'
    TRIGGER = 'Event trigger'
    CONTINUOUS = 'Continuous recording'


@dataclass
class EventDriver:
    provider_stage: Type[signalling.Stage]
    provider_parameters: Mapping


@dataclass
class Recorder:
    name: str
    recorder_stage: Type[signalling.Stage]
    recorder_parameters: Mapping
    recording_dir: str
    event_driver: Optional[EventDriver]
