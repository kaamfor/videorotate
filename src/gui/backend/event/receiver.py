import functools
from functools import partial
from dataclasses import dataclass, InitVar
from typing import Optional, Dict, Tuple, Callable, Any, Mapping, Union, Sequence, Type, List
import wx
import numpy as np
import cv2
from threading import Thread
import os
import operator

from wx import SizeEvent

from IFrameProcessAdapter import IFrameProcessAdapter, DrawingCallback

import net.receiver
import socketserver



from messaging.topic import ReplyControl, SentMessage, MessageThreadRegistry

from socketserver import ThreadingTCPServer, TCPServer

from video_backend.consumer import Consumer

import videorotate_constants

import control.signalling as signalling
import notifier

import video_backend.rtsp.rtsp_task as rtsp_task
import video_backend.rgb_task as rgb_task

import control.generic_resource as generic_resource
from net.parser.JSONParser import JSONParser

from gui.backend.stages.RGBFilterChange import RGBFilterChange
from gui.backend.stages.RGBFilter import RGBFilter

import gui.controls.wx_form as wx_form
import gui.resource
from gui.backend.stages.ThreadedEventReceiver import ThreadedEventReceiver
from control.patch import StreamerPatchCommand
import backend_context

import gui.backend.event.processing as event_processing

class CameraDataParser(JSONParser):
    def __call__(self, msg: net.receiver.IncomingEvent) -> Optional[net.receiver.ChangeEvent]:
        output = super().__call__(msg)

        keys = dict(output.value).keys()
        output.value = {k: v for k, v in dict(
            output.value).items() if k in keys}

        return output


@dataclass
class BinaryRuledTrigger(net.receiver.EventDistributor):
    rules: Sequence[event_processing.TriggerConditions]

    def __call__(self, event: Optional[net.receiver.ChangeEvent]) -> Optional[event_processing.RecordingTriggerResult]:
        if event is None:
            return None
        if not isinstance(event.value, Mapping):
            return event_processing.SimpleTrigger.NOT_RECORDING

        current_state = None
        tags = {}
        
        for rule in self.rules:
            condition_map = map(
                partial(self.run_comparison, value=event.value), rule.criterion_list)
            if all(condition_map):
                current_state = rule.state_on_match
                
                if rule.tag_name:
                    tags[rule.tag_name] = rule.tag_value
        
        if current_state is not None:
            return event_processing.RecordingTriggerResult(current_state, tags)
        
        return None

    def run_comparison(self, criterion: event_processing.TriggerCriterion, value: Mapping):
        fn = criterion.comparison.as_function()
        
        return criterion.field in value and fn(criterion.reference_value, value.get(criterion.field))


class FlattenedJSONParser(JSONParser):
    def __call__(self, msg: net.receiver.IncomingEvent) -> Optional[net.receiver.ChangeEvent]:
        output = super().__call__(msg)

        output.value = self.flatten_by_keys(output.value)
        return output

    def flatten_by_keys(self, data: Mapping, parent_name: str = '') -> Dict:
        assert isinstance(data, Mapping)

        output_data = {}
        for key, value in data.items():
            new_key = f"{parent_name}{key}"
            new_value = value
            if isinstance(value, Mapping):
                output_data.update(self.flatten_by_keys(value, f"{new_key}."))
            else:
                output_data[new_key] = new_value

        return output_data

@dataclass
class RecorderRemoteControl:
    start_command: Optional[signalling.Command]
    stop_command: Optional[signalling.Command]
    delete_command: Optional[signalling.Command]
    
    message_context: InitVar[signalling.MessagingContext]
    def start(self):
        if not self._started:
            self._started = True
            self._run_command(self.start_command)

    def stop(self):
        if self._started:
            self._started = False
            self._run_command(self.stop_command)
    
    def delete(self):
        self._run_command(self.delete_command)
        self.start_command = None
        self.stop_command = None
        self.delete_command = None
    
    def _run_command(self, command):
        if command is not None:
            self._message_context.send(command)
    
    def _set_status(self, update: notifier.Update):
        change = update.extract_nested_value()
        if isinstance(change, (generic_resource.Result, generic_resource.DelayedResult)):
            if change.status:
                self._prev_status = self._started
            else:
                self._started = self._prev_status
    
    def __post_init__(self, message_context: signalling.MessagingContext):
        self._message_context = message_context
        
        self._started = False
        self._prev_status = False

@dataclass
class JSONReceiverParameters:
    target_stage: signalling.Stage
    parameters: Union[Mapping[str, Any], wx_form.Form]
    notifier_property: notifier.KeyId
    parser: Union[Type[net.receiver.EventParser], net.receiver.EventParser] = FlattenedJSONParser
    trigger: Union[Type[net.receiver.EventDistributor], net.receiver.EventDistributor] = operator.attrgetter('value')
    
    def source_parameters(self) -> Mapping[str, Any]:
        if isinstance(self.parameters, Mapping):
            return self.parameters
        
        return self.parameters.get_values()

class JSONReceiverControl:
    
    @functools.cached_property
    def update_channel(self) -> notifier.UpdateChannel:
        return notifier.UpdateChannel()
    
    @property
    def builder_progress(self) -> signalling.LinearBuilderProgress:
        return self._receiver_stages
    
    @property
    def builder(self) -> signalling.LinearStageBuilder:
        return self._receiver_builder

    @functools.cached_property
    def completion_channel(self) -> notifier.UpdateChannel:
        return notifier.UpdateChannel()

    @property
    def started(self) -> bool:
        return self._start_initiated and self.__startup_completed

    @property
    def target_stage(self) -> Optional[signalling.Stage]:
        return getattr(self, '_target_stage', None)

    # TODO: make process-independent (-> ResourceBound)
    def __init__(self,
                 message_context: signalling.MessagingContext,
                 property_id: Optional[Any] = None) -> None:
        self._message_context = message_context

        self._channel = None

        self._receiver_builder = None
        self._parameters_used = False
        
        self._start_initiated = False
        self.__startup_completed = False
        self._stages: List[signalling.Stage] = []

        self.property_id = property_id

    def start(self, parameters: Optional[JSONReceiverParameters] = None) -> None:
        if self._start_initiated or self.__startup_completed:
            return
        self._start_initiated = True
        self.__startup_completed = False
        
        if not self._parameters_used:
            self._build(parameters)
            return
        
        # TODO: check if process-id generation not problematic
        for stage in self._stages:
            for command in stage.command_sequence(start=True):
                self._message_context.send(command)
        
        self.__startup_completed = True

    def stop(self) -> bool:
        if not self._start_initiated:
            return False
        if not self.__startup_completed:
            self.update_channel.subscribe(self._scheduled_stop)
            return False
        
        for stage in reversed(self._stages):
            for command in stage.command_sequence(start=False):
                self._message_context.send(command)
        
        self._start_initiated = False
        self.__startup_completed = False
        return True

    def _scheduled_stop(self, update):
        if not self._start_initiated:
            self.update_channel.unsubscribe(self._scheduled_stop)
            return
        
        if not self.__startup_completed:
            return
        
        if self.stop():
            self.update_channel.unsubscribe(self._scheduled_stop)

    def _build(self, parameters: Optional[JSONReceiverParameters] = None):
        if self._receiver_builder is None:
            if parameters is None:
                raise RuntimeError
            self.initiate_receiver(parameters)
        
        self._parameters_used = True
        
        
        self._receiver_builder.add_parameters(self._source_parameters_callback())
        del self._source_parameters_callback
        
        self._receiver_stages = progress = self._receiver_builder.set_target(
            self._target_stage, start=True)
        
        self._receiver_builder.stage_state(self._target_stage).command_notify.subscribe(
            partial(self.obtain_stream_channel, progress)
        )
        self._receiver_stages.completion_channel.thenPermanent(self._startup_completed)
    
    def initiate_receiver(self, parameters: JSONReceiverParameters):
        if self._receiver_builder is not None or self._parameters_used:
            return
        
        self._receiver_builder = signalling.LinearStageBuilder(
            self._message_context)

        stage_parameters = {
            'processor': net.receiver.EventProcessor(
                self.property_id,
                parameters.parser,
                parameters.trigger
            ),
            'notifier_property': parameters.notifier_property
        }

        self._receiver_builder.add_parameters(stage_parameters)
        self._source_parameters_callback = parameters.source_parameters
        self._target_stage = parameters.target_stage
        

    def obtain_stream_channel(self, progress: signalling.LinearBuilderProgress, update: notifier.Update):
        if not isinstance(update.value, StreamerPatchCommand):
            return

        # patch channel is ready
        for command_state in progress.processed_commands:
            if isinstance(command_state.progress.command, StreamerPatchCommand):
                #command_state.channel.subscribe(self.update_channel.send)
                command_state.channel.subscribe(self.update_filter)

                return
    
    
    def update_filter(self, update: notifier.Update):
        self.update_channel.send(update)
    
    def _startup_completed(self, evt):
        for command in self._receiver_stages.processed_commands:
            if command.stage not in self._stages:
                self._stages.append(command.stage)
        
        self.__startup_completed = True
