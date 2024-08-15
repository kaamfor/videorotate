from dataclasses import dataclass
from socket import socket
from enum import Enum
from collections import UserList, deque
from functools import cache, cached_property
import operator
from abc import ABC, abstractmethod
from random import randint
from typing import Optional, Union, List, Tuple, Dict, Mapping, Sequence, Callable, Any, Iterator, Type


import multiprocessing.connection

import videorotate_constants

SocketConnection = Union[multiprocessing.connection.Connection, socket, int]

@dataclass
class ReplyStatus:
    reply_msg: Any
    feedback_pending: bool

    def wait_for_reply(self, timeout: float = None):
        # Naive implementation - uses Queue.get()
        # Overridden from send_command

        if not self.feedback_pending:
            return self.reply_msg


@dataclass
class ReplyControlBase:
    reply_status: ReplyStatus  # CommandStatus
    id: Any


@dataclass
class ReplyControl(ReplyControlBase):
    reply_callback: 'PromiseControlCallback' = lambda command_control: None
    reply_to_message: bool = False
    keep_control: bool = False


PromiseControlCallback = Callable[[ReplyControl], Any]
PromiseValueCallback = Callable[[Any], None]

# TODO: rename LongPromise and other parts & refactor
class Promise(ABC):
    @abstractmethod
    def thenPermanent(self, callback: PromiseValueCallback):
        pass

ListenerCallback = Callable[[ReplyControl], Any]

class Socket(ABC):
    @abstractmethod
    def send_message(self, message: Any):
        pass

    @abstractmethod
    def recv_message_blocking(self, timeout: Optional[float]) -> Any:
        pass


# To wait for multiple socket in a single multiprocessing.connection.wait call
class BindableSocket(Socket, ABC):
    # return a value that multiprocessing.connection.wait accepts (as a list element)
    @property
    @abstractmethod
    def connection(self) -> SocketConnection:
        pass

class SimplePipeSocket(BindableSocket):
    def __init__(self, con: multiprocessing.connection.Connection):
        assert isinstance(con, multiprocessing.connection.Connection)
        
        self._con = con
    
    @property
    def connection(self) -> multiprocessing.connection.Connection:
        return self._con
    
    def send_message(self, message: Any):
        return self._con.send(message)
    
    def recv_message_blocking(self, timeout: Optional[float] = None) -> Any:
        if timeout is not None:
            is_available = self._con.poll(timeout)

            if not is_available:
                return None

        return self._con.recv()

@dataclass
class SentMessage:
    msg: Any
    source_control_id: Optional[int] = None
    target_control_id: Optional[int] = None


# Track Messages
class MessageRegistry(UserList):

    def __init__(self, registry_entries: Sequence = None):
        if registry_entries:
            super().__init__(registry_entries)
        else:
            super().__init__()

    # def symmetric_difference_item_update(self, item):
    #     try:
    #         self.data.remove(item)
    #     except ValueError:
    #         self.data.append(item)

    @property
    def entry_ids(self) -> Dict[int, ReplyControl]:
        ret = {entry.id: entry for entry in self.data}

        if videorotate_constants.DEBUG:
            import sys
            print('ENTRYIDS', ret)
            sys.stdout.flush()
        return ret

    # @cache
    def get_control_by_id(self, id: int) -> Union[ReplyControl, None]:
        search_entry = (
            entry for eid, entry in self.entry_ids.items() if eid == id)

        return next(search_entry, None)

    def __repr__(self) -> str:
        return self.__class__.__name__ + str(self.data)


# return generator
def message_receive_detector(
        socket_list: Sequence[BindableSocket],
        timeout: Optional[float] = None) -> Iterator[BindableSocket]:
    socket_lookup = {
        socket_obj.connection: socket_obj for socket_obj in socket_list}
    socket_con_list = list(socket_lookup)

    while True:
        yield list(map(lambda sock: socket_lookup[sock], multiprocessing.connection.wait(socket_con_list, timeout)))


ScheduledSource = Union[Socket, BindableSocket]

class MessagingScheduler:
    MESSENGER_FALLBACK_TIMEOUT: float = 0.1

    @dataclass
    class _ScheduledAttrs:
        callback: Callable[[Any], None]
        timeout: Optional[int]

    def __init__(self) -> None:
        self._sources = {}
        self._sources_unchanged = True

        self._run_waiting_loop = True

    def add_source(self,
                   socket: ScheduledSource,
                   callback: Callable[[Any], None],
                   timeout: Optional[int] = None):
        assert isinstance(socket, Socket)
        self._sources[socket] = self._ScheduledAttrs(
            callback,
            timeout
        )
        self._sources_unchanged = False

    def set_source_timeout(self,
                           socket: ScheduledSource,
                           timeout: Optional[int] = None):
        self._sources[socket].timeout = timeout
        self._sources_unchanged = False

    def serve_requests(self) -> Iterator[None]:
        bindable_socket = lambda sock: isinstance(sock, BindableSocket)

        while self._run_waiting_loop:
            # Initialization

            # Separate sockets whether polling or waiting needed
            bindable = set(
                sock for sock in self._sources if bindable_socket(sock))
            non_bindable = self._sources.keys() - bindable

            # do not poll if all sockets support it
            poll_it = len(non_bindable) > 0
            
            poll_timeout = self.MESSENGER_FALLBACK_TIMEOUT if poll_it else None

            if poll_timeout is None:
                # find minimum timeout of bindable sockets
                for name in bindable:
                    if isinstance(self._sources[name].timeout, (int, float)):
                        poll_timeout = self._sources[name].timeout

            detector = message_receive_detector(
                bindable,
                poll_timeout
            )

            self._sources_unchanged = True
            while self._run_waiting_loop and self._sources_unchanged:
                for sock in next(detector):
                    cb = self._sources[sock].callback
                    timeout = self._sources[sock].timeout if not poll_it else 0.0
                    cb(sock.recv_message_blocking(timeout))

                for sock in non_bindable:
                    self._sources[sock].callback(sock.recv_message_blocking(poll_timeout))
                
                yield

    def dispose(self) -> None:
        self._run_waiting_loop = False


# TODO: make implementation-independent parts a way here
class Messenger(ABC):
    @property
    @abstractmethod
    def socket(self) -> Socket:
        pass

@dataclass
class MessagePatcher:
    selector: Callable[[ReplyControl, PromiseControlCallback], bool]
    patcher: Callable[[ReplyControl, PromiseControlCallback], Any]

# TODO: move impl.-independent parts into this class - depends on refactoring the Messenger class
class PatchableMessenger(Messenger, ABC):
    @abstractmethod
    def patch(self, patch: MessagePatcher):
        pass