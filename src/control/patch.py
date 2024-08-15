from dataclasses import dataclass
from socket import socket
from enum import Enum
from collections import UserList, deque
from functools import cache, cached_property, partial
from abc import ABC, abstractmethod
from random import randint
from typing import Optional, Union, List, Tuple, Dict, Mapping, Sequence, Callable, Any, Iterator, Type


import multiprocessing.connection
import control.signalling as signalling
import notifier
from notifier import Update

import videorotate_constants

import messenger

import backend_context
import control.signalling

CommandField = signalling.Command.field
CommandType = signalling.Command.ParameterType


class PatchControlProcess(backend_context.ExtendedBackendProcess, backend_context.TaskProcess):
    pass

@dataclass
class PatchCommand(backend_context.MessagePatcher, signalling.StreamingCommand):
    def command(self) -> signalling.Tag:
        return signalling.Tag('process', 'patch')
    
    def task_completed(self, reply, reply_history: List[Any]) -> bool:
        return reply
    
    def context_ended(self, reply, reply_history: List[Any]) -> bool:
        return False
    
    def create_process(self) -> backend_context.ExtendedBackendProcess:
        return PatchControlProcess()
    


# TODO: find a better place (and a better name)
# task_completed vs context ended spearation
@dataclass
class StreamerPatchCommand(PatchCommand):
    patch_id: Any = CommandField(CommandType.INHERITED)

    def run(self,
            control: messenger.ReplyControl,
            process: backend_context.BackendProcess) -> Any:
        res = super().run(control, process)

        context = process.context
        control_db = context.setdefault(StreamerPatchCommand, {})
        control_db[self.patch_id] = control

        control.keep_control = True
        return res
    
    @classmethod
    def backend__get_control(cls,
                             context: backend_context.BackendProcessContext,
                             patch_id: Any
                             ) -> messenger.ReplyControl:
        control_db = context.setdefault(StreamerPatchCommand, {})
        return control_db[patch_id]
