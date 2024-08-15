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

Topic = str
Thread = str
ThreadHistory = List[Tuple[Thread, Any]]

# 1. send command and
# - do not create reply channel
# - create a queue and
#       1. return a CommandStatus object immediately
#           -> poll through <object>.wait_for_reply(..), or
#           -> <TopicMessaging>.recv_message_blocking(..)
#       2. call listener handler with a CommandControl object when reply is available
#
# 2. add listener for topic
#
# thread = topic + actual calling instance

# create new thread when
# - old listener is still 'hanging around'(???), or
# - multiple replies are done


@dataclass
class ReplyStatus(messenger.ReplyStatus):
    topic: Topic
    thread: Thread


@dataclass
class ReplyControlBase(messenger.ReplyControlBase):
    reply_status: ReplyStatus  # CommandStatus

    thread_history: ThreadHistory


@dataclass
class ReplyControl(messenger.ReplyControl, ReplyControlBase):
    reply_callback: Callable[['ReplyControl'], Any] = lambda command_control: None


ListenerCallback = Callable[[ReplyControl], Any]

@dataclass
class SentMessage(messenger.SentMessage):
    topic: Optional[Topic] = None
    thread: Optional[Thread] = None

# Track Messages
class MessageThreadRegistry(messenger.MessageRegistry):

    # @cache
    def thread_entries(self, topic: str, thread: str) -> Dict[int, ReplyControl]:
        return {i: entry for i, entry in self.topic_entries(topic).items() if entry.reply_status.thread == thread}

    # @cache
    def topic_entries(self, topic: str) -> Dict[int, ReplyControl]:
        return {i: entry for i, entry in enumerate(self.data) if entry.reply_status.topic == topic}


@dataclass
class MessagePatcher:
    selector: Callable[[ReplyControl, ListenerCallback], bool]
    patcher: Callable[[ReplyControl, ListenerCallback], Any]


class PatchableMessenger(messenger.Messenger, ABC):
    @abstractmethod
    def patch(self, patch: MessagePatcher):
        pass

class ContextChannel(notifier.MultiContextChannel):
    def __init__(self) -> None:
        super().__init__()
        self._context = None
    
    def deregister_context(self):
        if self._context:
            self._context.keep_control = False
    
    def switch_context(self, control: ReplyControl):
        control.keep_control = True
        self._context = control

@dataclass
class ContextUpdateBase(notifier.MultiContextUpdateBase):
    context_channel: ContextChannel

@dataclass
class ContextUpdate(notifier.MultiContextUpdate, ContextUpdateBase):
    pass

class TopicMessagingContext(signalling.MessagingContext):
    @property
    def messenger(self) -> 'TopicMessaging':
        return self._messenger
    
    @property
    def topic(self) -> Topic:
        return self._topic
    
    @cached_property
    def registry_channel(self) -> notifier.UpdateChannel:
        return notifier.UpdateChannel()
    
    def __init__(self,
                 messenger: 'TopicMessaging',
                 topic: Topic,
                 initiate_this_side_only: bool = True) -> None:
        super().__init__()
        
        self._messenger = messenger
        self._topic = topic
        self._initiate_this_side_only = initiate_this_side_only
        
        self._received_by_messenger = None
        
        # TODO: memory leaking!!
        self._context_channels = {}
        self._untracked_context_channels = []
    
    # document Update vs ResourceBound difference
    def send(self,
             message: Optional[Union[notifier.Update, signalling.ResourceBound]] = None
             ) -> notifier.UpdateChannel:
        channel = ContextChannel()
        
        if isinstance(message, signalling.ResourceBound):
            resource_id = message.target_resource_id
            
            if resource_id in self._context_channels:
                channel = self._context_channels[resource_id]
                
                channel.send(
                    notifier.Update(
                        key=message.target_resource_id,
                        value=message
                    )
                )
                return channel
            else:
                raise LookupError(f"Message context for resource {resource_id}"
                                  f" not found")
        
        is_resource_bound = message is not None and isinstance(message.value, signalling.ResourceBound)
        add_channel_later = message is None
        
        if is_resource_bound:
            self._context_channels[message.value.target_resource_id] = channel
        
        if not self._initiate_this_side_only:
            self.messenger.add_listener(self.topic, partial(self._messenger_receiver, channel))
        
        channel.subscribe(partial(self._messenger_sender, channel))
        
        if add_channel_later:
            self._untracked_context_channels.append(channel)
        
        if message is not None:
            channel.send(message)
        
        if videorotate_constants.DEBUG:
            import sys
            print('TopicMessagingContext.send', message)
            sys.stdout.flush()
        
        return channel
    
    
    def _messenger_receiver(self, channel: ContextChannel, control: ReplyControl):
        update = ContextUpdate(
            key=control.reply_status.thread,
            value=control.reply_status.reply_msg,
            emitted_by=control.reply_status.topic,
            context_channel=channel
        )
        self._received_by_messenger = update
        
        channel.switch_context(control)
        channel.send(update)
        if videorotate_constants.DEBUG:
            import sys
            print('TopicMessagingContext._receiver',
                  control.reply_status.reply_msg,
                  control.reply_to_message,
                  control.keep_control)
            sys.stdout.flush()
        
        self._received_by_messenger = None
    
    def _messenger_sender(self,
                          channel: notifier.UpdateChannel,
                          update: notifier.Update):
        if update is self._received_by_messenger:
            # prevent loop
            return
        
        if (channel in self._untracked_context_channels
                and isinstance(update.value, signalling.ResourceBound)):
            self._context_channels[update.value.target_resource_id] = channel
            
            self._untracked_context_channels.remove(channel)
        
        control = self.messenger.send_message(
            self.topic,
            update.value,
            partial(self._messenger_receiver, channel)
        )
        self.registry_channel.send(
            notifier.Update(
                key=self.topic,
                value=control,
                emitted_by=self.messenger
            )
        )
        if videorotate_constants.DEBUG:
            import sys
            print('TopicMessagingContext._sender', update.value)
            sys.stdout.flush()

class TopicMessaging(PatchableMessenger):

    def __init__(self, socket: messenger.Socket) -> None:
        super().__init__()

        self.socket = socket

        self._topic_listeners = {}
        
        self._patches: List[MessagePatcher] = []

    @property
    def socket(self) -> messenger.Socket:
        return self._socket

    @socket.setter
    def socket(self, socket: messenger.Socket):
        assert isinstance(socket, messenger.Socket)

        self._socket = socket

    def add_listener(self,
                     topic: Optional[str],
                     handler: ListenerCallback) -> None:
        assert isinstance(topic, Optional[str])
        assert callable(handler)

        topic_handlers = self._topic_listeners.setdefault(topic, [])
        topic_handlers.append(handler)
    
    def del_listener(self,
                     topic: Optional[str],
                     handler: ListenerCallback) -> None:
        
        topic_handlers = self._topic_listeners.setdefault(topic, [])
        topic_handlers.remove(handler)

    def new_topic(self, topic: Topic) -> TopicMessagingContext:
        return TopicMessagingContext(self, topic, True)

    def send_message(self,
                     topic: Optional[str],
                     message: any,
                     reply_callback: Optional[ListenerCallback] = None
                     ) -> Optional[ReplyControl]:
        send_msg = SentMessage(msg=message,
                               topic=topic,
                               source_control_id=None)

        control = None
        if reply_callback:
            assert callable(reply_callback)

            control = self._create_control(send_msg)
            control.reply_callback = reply_callback
            control.reply_status.feedback_pending = control.reply_to_message

            send_msg.source_control_id = control.id

        self._socket.send_message(send_msg)

        from multiprocessing import current_process

        if videorotate_constants.DEBUG:
            if control:
                print("""
=== SEND MESSAGE ===""", current_process().name, """

""", control.reply_status.topic,
                  control.reply_status.thread, control.reply_callback,
                  """
""", send_msg, """

=== END ===
""")
            else:
                print("""
=== SEND MESSAGE ===""", current_process().name, """

""", send_msg, """

=== END ===
""")
            import sys
            sys.stdout.flush()

        return control

    # TODO
    # Ezt a fgv-t meg jobban szetszedni, ha elkeszultunk vele
    # -> lehessen atadni a vezerlest, hogy hatekonyabb legyen az ellenorzes
    # Megoldani a KeyboardInterrupt ugyet!!

    # In-argument list is modified during execution
    # Return list, where len(<list>)
    # = 0 - no thread or topic match at all
    # = 1 - found exact thread listener (returns CommandStatus) or _1_ topic match (returns CommandControl)
    # = n - got topic matches, where type of object is
    #       -> CommandControl: does not send reply after listener call
    #       -> CommandStatus: _will_ send reply after listener call (with listener's reply)
    #
    # Changed:
    # return pop'd entries
    #
    # XOR working: handle received message by
    # Na, akkor így: ha van a fogadó oldalon Control objektum, csak az kezelje le
    # Egyébként létrehozunk egy kontrol objeltumat
    #
    # Hohó! Topic is csak akkor kell, mikor először választunk ki kontrollert
    # Thread helyett Controller id!
    # Osztódás: probléma-e? Egy thread csak egy visszatérési értékkel tud visszatérni
    def recv_and_process_message(self,
                                registry: MessageThreadRegistry,
                                timeout: Optional[float] = None) -> Optional[List[ReplyControl]]:
        sent_msg = self._socket.recv_message_blocking(timeout)

        return self.process_new_message(registry, sent_msg)

    def process_new_message(self,
                               registry: MessageThreadRegistry,
                               sent_msg: SentMessage) -> Optional[List[ReplyControl]]:

        if sent_msg is None:
            return None
        assert isinstance(sent_msg, SentMessage)

        # Search matching control
        if sent_msg.target_control_id is not None:
            control = registry.get_control_by_id(sent_msg.target_control_id)

            if videorotate_constants.DEBUG:
                import sys
                if control is None:
                    print('Control @ msg', sent_msg, """
Control is none""", sent_msg.target_control_id, """

""", sent_msg, """

""", sent_msg.target_control_id)
                else:
                    print('Control @ msg', sent_msg, """

""", sent_msg.target_control_id)
                sys.stdout.flush()

            self._handle_message(control, sent_msg)

            if not control.keep_control:
                registry.remove(control)
            return [control]

        # ..or initiate new thread / create new control
        def thread_generator(
            topic): return self.generate_thread(registry, topic)

        affected_controls = self._reply_to_new_thread(
            sent_msg, thread_generator)

        skip_unneccessary = (
            entry for entry in affected_controls if entry.keep_control)
        registry.extend(skip_unneccessary)

        return affected_controls

    def deferred_reply(self, control: ReplyControl, send_msg):
        # TODO: is this needed?
        #assert not control.reply_status.feedback_pending

        last_msg_thread, last_msg = control.thread_history[-1]
        
        if videorotate_constants.DEBUG:
            print('last message', control.id, last_msg)
            print('send this:', control.id, send_msg)
            import sys
            sys.stdout.flush()

        assert isinstance(last_msg, SentMessage)

        # TODO: make control id swapping less obscure (like create dedicated field for it)
        is_last_received = last_msg.target_control_id == control.id
        source_id = last_msg.target_control_id if is_last_received else last_msg.source_control_id
        target_id = last_msg.source_control_id if is_last_received else last_msg.target_control_id
        
        send_out = SentMessage(msg=send_msg,
                               #source_control_id=last_msg.target_control_id,
                               #target_control_id=last_msg.source_control_id,
                               source_control_id=source_id,
                               target_control_id=target_id,
                               topic=control.reply_status.topic,
                               thread=control.reply_status.thread)

        control.reply_status.feedback_pending = control.reply_to_message
        control.keep_control = control.reply_to_message

        if videorotate_constants.DEBUG:
            import sys
            print('send this:', send_out)
            sys.stdout.flush()
        self._socket.send_message(send_out)

    def _handle_message(self,
                        control: ReplyControl,
                        msg: SentMessage) -> List[ReplyControl]:

        if videorotate_constants.DEBUG:
            from multiprocessing import current_process
            import sys
            print("""
=== Handle message ===""", current_process().name, """

""", #control, """
"""
""", control.reply_status.topic,
              control.reply_status.thread, control.reply_callback, """

""", msg, """
""")
            sys.stdout.flush()

        assert not control.reply_status.feedback_pending

        control.reply_status.reply_msg = msg.msg

        if control.reply_callback is None:
            control.keep_control = False
            return

        if control.reply_status.thread is None:
            control.reply_status.thread = msg.thread

        # apply patch if needed
        any_patch_applied = False
        result = None
        for patch in self._patches:
            if patch.selector(control, control.reply_callback):
                result = patch.patcher(control, control.reply_callback)
                any_patch_applied = True
                break

        if not any_patch_applied:
            result = control.reply_callback(control)

        control.thread_history.append((control.reply_status.thread, msg))

        if control.reply_to_message:
            msg.source_control_id, msg.target_control_id = msg.target_control_id, msg.source_control_id

            msg.msg = result
            
            if videorotate_constants.DEBUG:
                print("""
=== Reply to message ===""", current_process().name, """

""", result, """
""", control, """

""")
                sys.stdout.flush()

            self._socket.send_message(msg)

        if videorotate_constants.DEBUG:
            print(control, """
""", control.reply_status.topic,
              control.reply_status.thread, control.reply_callback, """

""", msg, """

=== END Handle message ===
""", current_process().name)
            sys.stdout.flush()

    def _reply_to_new_thread(self,
                             msg: SentMessage,
                             thread_generator: Callable[[Topic], Thread]) -> List[ReplyControl]:
        
        if videorotate_constants.DEBUG:
            from multiprocessing import current_process
            print('=== RECEIVED NEW MESSAGE ===', current_process().name)
            import sys
            sys.stdout.flush()

        control_list = []
        if msg.topic is not None:
            control_list = self._call_listeners_on_new_message(
                msg, self._topic_listeners.get(msg.topic, {}), thread_generator
            )
        control_list.extend(self._call_listeners_on_new_message(
            msg, self._topic_listeners.get(None, {}), thread_generator
        )
        )
        if videorotate_constants.DEBUG:
            from multiprocessing import current_process
            print('=== RECEIVED NEW MESSAGE END ===', current_process().name, msg.msg)
            import sys
            sys.stdout.flush()
        return control_list

    def _call_listeners_on_new_message(self,
                                       msg: SentMessage,
                                       listener_list: List,
                                       thread_generator: Callable[[Topic], Thread]) -> List:
        new_controls = []
        for listener in listener_list:
            if videorotate_constants.DEBUG:
                import sys
                print('MSG_listener', msg, listener)
                sys.stdout.flush()

            control = self._create_control(msg, thread_generator)
            control.reply_callback = listener
            msg.thread = control.reply_status.thread

            msg.target_control_id = control.id

            self._handle_message(control, msg)
            
            ####################################################################################################################################
            # if videorotate_constants.DEBUG:
            #     import sys
            #     print('MSG_listener2', control)
            #     sys.stdout.flush()

            new_controls.append(control)
        return new_controls

    def _create_control(self,
                        msg: SentMessage,
                        thread_generator: Callable[[Topic], Thread] = None
                        ) -> ReplyControl:
        new_thread = None
        if thread_generator:
            new_thread = thread_generator(msg.topic)

        reply_status = ReplyStatus(topic=msg.topic,
                                   thread=new_thread,
                                   reply_msg=msg.msg,
                                   feedback_pending=False)

        new_control = ReplyControl(
            reply_status=reply_status,
            thread_history=[(new_thread, msg)],
            id=None
        )
        new_control.id = id(new_control)
        return new_control

    def generate_thread(self, registry: MessageThreadRegistry, topic: Topic) -> Thread:
        thread = None

        while not thread or len(registry.thread_entries(topic, thread)):
            # Generate unique thread name
            thread = str(randint(0, 10000))

        return thread
    
    def patch(self, patch: MessagePatcher):
        self._patches.append(patch)



if __name__ == "__main__":
    from multiprocessing import Pipe
    from multiprocessing.connection import Connection
    from sys import stdout

    class MySocket(messenger.Socket):
        def __init__(self, source: Connection, target: Connection) -> None:
            self.source, self.target = source, target

        def send_message(self, message: Any):
            self.target.send(message)

        def recv_message_blocking(self, timeout: Optional[float] = None) -> Any:
            if timeout is not None:
                is_available = self.target.poll(timeout)

                if not is_available:
                    return None

            return self.target.recv()

    registry = MessageThreadRegistry()

    p1, p2 = Pipe()
    s1, s2 = MySocket(p1, p2), MySocket(p2, p1)

    mes1, mes2 = TopicMessaging(s1), TopicMessaging(s2)

    # Not the best demostration
    # ==========================

    topic = 'test1'
    print('==== Test1:', topic, '- add listener then send message ====')
    stdout.flush()
    mes2.add_listener(topic, lambda control: print('mes2a receives:', control))

    print(mes1.send_message(topic, {'This', 'is', 'a', 'test', 'topic'}))
    stdout.flush()

    print('Registry:', registry)
    stdout.flush()
    print(mes2.recv_and_process_message(registry, 1))
    print('Registry:', registry)
    stdout.flush()

    print()
    print()

    topic = 'test2'
    print('==== Test2:', topic, '- add listener then send message with replier ====')
    stdout.flush()
    mes2.add_listener(topic, lambda control: print(
        'mes2b receives ', control.reply_status.reply_msg))

    print(mes1.send_message(topic, [
          'This', 'is', 'a', 'test', 'topic'], lambda control: print('mes1 receives:', control)))
    stdout.flush()

    print('Registry:', registry)
    print(mes2.recv_and_process_message(registry, 1))
    print('Registry:', registry)
    stdout.flush()

    print()
    print()

    registry2 = MessageThreadRegistry()

    topic = 'test2'
    print('==== Test3:', topic, '- add listener: print and return value ====')
    stdout.flush()

    def control(control: ReplyControl):
        print('Got reply')
        print(control.thread_history, id(control))

        control.reply_to_message = len(control.thread_history) / 22 != 2
        control.keep_control = True
        print('Ok')
        stdout.flush()
        # return len(control.thread_history) % 22

        print(control.reply_status.reply_msg)
        return control.reply_status.reply_msg+1

    mes2.add_listener(topic, control)

    # mes3_c = mes1.send_message(topic, ['This', 'is', 'a', 'test', 'topic'], control)
    mes3_c = mes1.send_message(topic, 0, control)
    registry2.append(mes3_c)
    print(mes3_c)
    stdout.flush()

    print('Registry:', registry)
    stdout.flush()
    print(mes2.recv_and_process_message(registry, 1))
    print('Registry:', registry)
    stdout.flush()

    print('Registry:', registry)
    stdout.flush()
    print(mes1.recv_and_process_message(registry2, 1))
    print('Registry:', registry)
    stdout.flush()

    while True:
        print('mes2', mes2.recv_and_process_message(registry, 1))
        stdout.flush()
        print('mes1', mes1.recv_and_process_message(registry2, 1))
        stdout.flush()

    exit()

    messaging.add_oneshot_listener

    sent_object = "Test (Text) Message"
    print(' ==== Send object through pipe w/o existing queues ==== ')
    print('Test object:')
    print(sent_object)
    # Not the best example
    messaging.send_message('tip', sent_object)

    print()
    print('...send object...')
    print()
    got_object = messaging.process__recv_message_blocking()
    print('Got object:')
    print(got_object)

    def send_msg(title, sender_method, receiver_method, queue_assign_method, thread=None):

        sent_object = "Test (Text) Message"
        print(f' ==== {title} ==== ')
        print(' ==== Receive object via queue (set no explicit thread) ==== ')
        print('Test object:')
        print(sent_object)

        # add all-listener queue
        queue_ = queue_assign_method(thread)

        sender_method(sent_object, thread)

        print('...send object...')
        got_object = receiver_method()
        print('Got object:')
        print(got_object)
        print('Receive object via queue:')
        print(queue_.pop())
        print('Receive other object via queue w/ timeout (it is empty so raises None):')
        # try:
        #     queue_.get(timeout=1)
        # except queue.Empty:
        #     print('Timed out, queue is empty, OK')
        # else:
        #     raise 'Something is wrong'

    print()
    print()
    send_msg('Backend->Frontend NO explicit thread',
             messaging.process__send_message,
             messaging.messenger__recv_message_blocking,
             messaging.messenger__assign_queue)
    print()
    print()
    send_msg('Frontend->Backend NO explicit thread',
             messaging.messenger__send_message,
             messaging.process__recv_message_blocking,
             messaging.process__assign_queue)
    print()
    print()
    send_msg('Backend->Frontend with thread',
             messaging.process__send_message,
             messaging.messenger__recv_message_blocking,
             messaging.messenger__assign_queue)
    print()
    print()
    send_msg('Frontend->Backend with thread',
             messaging.messenger__send_message,
             messaging.process__recv_message_blocking,
             messaging.process__assign_queue)
