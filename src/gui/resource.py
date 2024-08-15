from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import functools
from functools import partial
from enum import Enum
import dataclasses
from dataclasses import dataclass, is_dataclass, fields
from typing import Callable, Optional, Any, Union, Mapping, Type, Sequence, Tuple
from multiprocessing import Process, current_process

import wx

import statemachine as sm
from statemachine.states import States

# from backend_context import BackendProcess
import control.signalling as signalling

from videorotate_utils import print_exception, log_context
from messaging.topic import TopicMessaging, MessageThreadRegistry, ReplyControl, SentMessage



from backend_context import BackendTask, BackendProcessContext
import notifier

import gui.controls.wx_form as wx_form
import videorotate_utils

def assemble_form(widget_parent: wx.Window,
                  frontend_list: Sequence[Union['Frontend', Type['Frontend']]],
                  add_submit_button: bool = True
                  ) -> Tuple[wx_form.Form, notifier.UpdateChannel]:
    form = wx_form.KeyValueForm(widget_parent)
    submit_channel = notifier.UpdateChannel()
    
    for frontend in frontend_list:
        is_frontend = isinstance(frontend, Frontend)
        is_frontend_type = isinstance(frontend, type) and issubclass(frontend, Frontend)
        assert is_dataclass(frontend) and (is_frontend or is_frontend_type)

        for field in fields(frontend):
            name = field.name
            
            if name in form.schematic:
                continue
            
            value = getattr(frontend, name) if is_frontend else field.default

            builder = wx_form.FieldBuildableControl.get_builder(field)
            custom_data = wx_form.FieldBuildableControl.get_field_data(field)
            
            if not builder:
                continue
            
            if value is not dataclasses.MISSING:
                field_input = builder(parent=widget_parent, value=value)
            else:
                field_input = builder(parent=widget_parent)
            
            sizer, label, input = form.add_keypair(name, field_input, custom_data.get('display_name', None))

    def submit_callback(update: notifier.Update):
        submit_channel.send(
            notifier.Update(
                wx_form.Form,
                form.get_values(),
                form
            )
        )

    if add_submit_button:
        submit_btn = form.add_submit_button()

        submit_btn.event_channel.thenPermanent(submit_callback)
        submit_btn.bind_event_channel(wx.EVT_BUTTON)

    return form, submit_channel

class Frontend(ABC):
    # @property
    # @abstractmethod
    # def command_list(self) -> Mapping[signalling.Tag, Callable]:
    #     pass

    # sends KVFormOutput objects
    @property
    def submit_channel(self) -> notifier.UpdateChannel:
        if not hasattr(self, '_submit_channel'):
            self._submit_channel = notifier.UpdateChannel()
        
        return self._submit_channel

    # @property
    # @abstractmethod
    # def parameter_mapping(self) -> Mapping[str, Any]:
    #     pass

    def build_configurator(self, widget_parent: wx.Window) -> wx_form.Form:
        form, channel = assemble_form(widget_parent, [self])
        
        channel.thenPermanent(self.submit_channel.send)
        return form
    
    # TODO: make a function that is able to get the underlying control field's data
    # @classmethod
    # def get_control_field(cls, field_name: str) -> dataclasses.Field:
    #     for field in fields(cls):
    #         if field.name == field_name:
    #             return field

    #     raise LookupError


