from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import functools
from functools import partial
from enum import Enum
from typing import Callable, Optional, Any, Union, Iterator, Protocol
from multiprocessing import Process, current_process

import statemachine as sm

from videorotate_utils import print_exception, log_context
from messaging.topic import TopicMessaging, MessageThreadRegistry, ReplyControl, SentMessage



import messenger
import notifier


# # Készíteni egy command dekorátort, ami az üzenetkezelést végzi.
# #
# #  - A command függvények alapból SentMessage objektumot várnak!
# #  <- ezt nem muszáj végülis....
# #
# # Visszatérési érték egy Future, ezt azonnal megkapjuk...
# # A Future paramétert paraméterezhetnénk...
# # átnézni: PEP-0483 és typing modul

# # class decorator
# # TODO: customizable function-lookup (how deep we should go)
# def process_mock()

# def backend_process(cls):
#     assert isinstance(cls, BackendProcess)

#     def proxy_call(method: Callable, *args, **kwargs):
#         #####################messenger = cls.backend__messenger.send_message()
#         method(*args, **kwargs)

#     cls_methods = set([e for e in dir(cls) if not e.startswith('__')])
#     parent_methods = set([e for e in super(dir(cls)) if not e.startswith('__')])

#     relevant_methods = cls_methods.intersection(parent_methods)
#     for method_name in relevant_methods:
#         method_obj = getattr(cls, method_name)

#         new_method_obj = partial(proxy_call, method_obj)

#         setattr(cls, method_name, new_method_obj)

#     return cls

# class FutureReturn:
#     pass

ObserverCallback = Callable[[Any], Any]


@dataclass
class ProcessShutdownSequence:
    process_id: Optional[Any]
    expected: bool
    clean_shutdown: bool


class BackendProcessContext(dict):
    pass

class BackendProcess(Process):

    @property
    def backend__context(self) -> BackendProcessContext:
        return self.context

    # override at main messenger side
    @property
    def backend_messenger(self) -> TopicMessaging:
        return self._backend_messenger

    @backend_messenger.setter
    def backend_messenger(self, backend_messenger: TopicMessaging):
        self._backend_messenger = backend_messenger

    # override at main messenger side
    @property
    def messenger_timeout_sec(self) -> Optional[float]:
        return self._messenger_timeout_sec

    @messenger_timeout_sec.setter
    def messenger_timeout_sec(self, messenger_timeout_sec: Optional[float]):
        self._messenger_timeout_sec = messenger_timeout_sec

    def frontend__process_started(self) -> bool:
        return self.is_alive() or self.exitcode is not None

    # Need to call this externally, before calling Start()
    def frontend__setup(self):
        pass

    def backend__dispose(self):
        self.run_loop = False

    def backend__setup(self):
        self.context = BackendProcessContext()

        self.backend_registry = MessageThreadRegistry()

        self._setup_control = None
        
        self.backend_messenger.add_listener(
            None,
            self.backend__administrative_messages
        )

    def backend__exit(self):
        pass

    @print_exception
    def run(self):
        log_context(str(current_process().name))
        import sys
        print('Subprocess started')
        sys.stdout.flush()

        assert isinstance(self.backend_messenger, TopicMessaging)

        self.backend__setup()

        got_exception = None
        self.run_loop = True
        try:
            while self.run_loop:
                self.backend__process_loop()
        except Exception as e:
            got_exception = e

        # Send message about process shutdown
        setup_msg = self._setup_control.reply_status.reply_msg
        reply = ProcessShutdownSequence(
            process_id=None,
            expected=not self.run_loop,
            clean_shutdown=got_exception is None
        )

        if isinstance(setup_msg, ProcessBoundTask):
            reply.process_id = setup_msg.process_id

        self.backend_messenger.deferred_reply(
            self._setup_control, reply
        )

        self.backend__exit()

        if got_exception is not None:
            raise got_exception

        print('Subprocess ended')
        sys.stdout.flush()

    def backend__process_loop(self):
        self.backend__message_receiving()
    
    def backend__message_receiving(self):
        self.backend_messenger.recv_and_process_message(self.backend_registry,
                                                        self.messenger_timeout_sec)

    def backend__administrative_messages(self, control: ReplyControl):
        assert isinstance(control, ReplyControl)

        if self._setup_control is None:
            self._setup_control = control

        do_shutdown = (control.reply_status.topic is None
                       and control.reply_status.reply_msg is None)
        if do_shutdown:
            self.run_loop = False

@dataclass
class TaskRunner:
    process: 'TaskProcess'
    
    def __call__(self, control: ReplyControl) -> Any:
        assert isinstance(control, ReplyControl)

        msg = control.reply_status.reply_msg

        # handling only 'runnable' BackendTasks
        if not isinstance(msg, BackendTask):
            return

        def e(*args, **kwargs):
            self.process.backend_messenger.deferred_reply(*args, **kwargs)

        msg.deferred_reply = e

        result = msg.run(control, self.process)
        return result

class TaskProcess(BackendProcess):
    TASK_HANDLER = TaskRunner
    
    @property
    def task_channel_topic(self) -> notifier.KeyId:
        return self._task_key
    
    @task_channel_topic.setter
    def task_channel_topic(self, task_key: notifier.KeyId) -> None:
        assert isinstance(task_key, notifier.KeyId)
        
        self._task_key = task_key
    
    @functools.cached_property
    def task_channel(self) -> notifier.UpdateChannel:
        return notifier.UpdateChannel()

    def backend__setup(self):
        super().backend__setup()
        self.backend_messenger.add_listener(
            None,
            self.TASK_HANDLER(self)
        )


class ExtendedBackendProcess(BackendProcess):
    @BackendProcess.messenger_timeout_sec.setter
    def messenger_timeout_sec(self, timeout: Optional[float]):
        self._messenger_timeout_sec = timeout
        
        try:
            self.messaging_scheduler.set_source_timeout(
                self.backend_messenger.socket,
                timeout
            )
        except AttributeError:
            return
    
    @functools.cached_property
    def messaging_scheduler(self) -> messenger.MessagingScheduler:
        scheduler = messenger.MessagingScheduler()
        
        messenger_trigger = partial(
            self.backend_messenger.process_new_message,
            self.backend_registry
        )
        scheduler.add_source(self.backend_messenger.socket, messenger_trigger, self.messenger_timeout_sec)
        return scheduler
    
    @functools.cached_property
    def _scheduler_handler(self) -> Iterator[None]:
        return self.messaging_scheduler.serve_requests()
    
    def backend__message_receiving(self):
        next(self._scheduler_handler)


class BackendTask(ABC):
    @abstractmethod
    def run(self, control: ReplyControl, process: BackendProcess):
        pass

    @abstractmethod
    def create_process(self) -> BackendProcess:
        pass

    # overridden when background process receives
    def deferred_reply(self, control: ReplyControl, msg: SentMessage):
        raise NotImplementedError

    # guaranteed to exist
    def __post_init__(self):
        pass


@dataclass
class ProcessBoundTask(BackendTask):
    # can manually be adjusted; if a process with this id exists, the task will be ran in it
    process_id: Any


@dataclass
class GeneratedProcessTask(ProcessBoundTask):
    process_id: Any = field(init=False)

    def __post_init__(self):
        super().__post_init__()
        self.process_id = id(self)

@dataclass
class MessagePatcher(GeneratedProcessTask, messenger.MessagePatcher):
    def run(self, control: ReplyControl, process: BackendProcess) -> Any:
        process.backend_messenger.patch(self)
        
        control.reply_to_message = True
        
        return True
    
    @property
    def target_resource_id(self) -> Any:
        return self.process_id

@dataclass
class CallbackBasedTask(BackendTask, ABC):
    @property
    @abstractmethod
    def task_callback(self) -> Callable:
        pass

# TODO: disable listener


@dataclass
class PropertyObserverTask(CallbackBasedTask, ABC):

    @property
    @abstractmethod
    def property_id(self) -> Any:
        pass

    @property
    @abstractmethod
    def notifier(self) -> notifier.Distributor:
        pass

    @property
    @abstractmethod
    def task_callback(self) -> ObserverCallback:
        pass

    def run(self, control: ReplyControl, process: BackendProcess):
        self.notifier.subscribe(self.property_id,
                                False).thenPermanent(self.task_callback)
        return super().run(control, process)

