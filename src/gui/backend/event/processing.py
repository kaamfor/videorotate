import functools
from functools import partial
import enum
from dataclasses import dataclass
from typing import Optional, Dict, Tuple, Callable, Any, Mapping, Union, Sequence, Type, Iterable, List
import wx
import numpy as np
import cv2
from threading import Thread
import os
import operator

from wx import SizeEvent

from net.receiver import ChangeEvent, IncomingEvent


from messaging.topic import ReplyControl, SentMessage, MessageThreadRegistry

from socketserver import ThreadingTCPServer, TCPServer

import videorotate_constants

import control.signalling as signalling
import notifier

import net.receiver as receiver
from net.parser.JSONParser import JSONParser

import gui.controls.wx_form as wx_form
import gui.resource
from gui.backend.stages.ThreadedEventReceiver import ThreadedEventReceiver
from control.patch import StreamerPatchCommand
import socketserver

class SimpleTrigger(enum.Enum):
    RECORDING = True
    NOT_RECORDING = False


class ValueComparison(enum.Enum):
    EQUALS = ('=', operator.eq)
    DIFFERS = ('!=', operator.ne)

    def as_function(self) -> Callable[[Any, Any], bool]:
        return self.value[1]

    @classmethod
    def operators(cls) -> Iterable[str]:
        return map(operator.itemgetter(0), map(operator.attrgetter('value'), cls))

    @classmethod
    def get_function(cls, operator_str: str) -> Callable[[Any, Any], bool]:
        for operator in cls:
            if operator.value[0] == operator_str:
                return operator.value[1]
        raise LookupError

    @classmethod
    def get_enum(cls, operator_str: str) -> 'ValueComparison':
        for operator in cls:
            if operator.value[0] == operator_str:
                return operator
        raise LookupError


@dataclass
class TriggerCriterion:
    field: str
    reference_value: Any
    comparison: ValueComparison

    def __str__(self) -> str:
        return f"{self.field} {self.comparison.value[0]} {self.reference_value}"


@dataclass
class TriggerConditions:
    state_on_match: SimpleTrigger
    criterion_list: List[TriggerCriterion]
    
    tag_name: Optional[str]
    tag_value: Optional[str]

    def __iter__(self) -> Iterable[TriggerCriterion]:
        return iter(self.criterion_list)

    # def __str__(self) -> str:
    #     return self.state_on_match.name

@dataclass
class RecordingTriggerResult:
    state: SimpleTrigger
    tags: Mapping[str, Optional[str]]
    
    def __bool__(self):
        return self.state.value