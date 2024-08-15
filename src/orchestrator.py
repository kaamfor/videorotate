from dataclasses import dataclass
import itertools
from functools import partial
from multiprocessing import Process, current_process
import multiprocessing.connection
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Callable, NoReturn, Any, Union

import messenger
from messaging.topic import TopicMessaging, MessageThreadRegistry, ReplyControl, SentMessage
from ProcessSocket import ProcessSocket
from videorotate_utils import print_exception, log_context

from backend_context import BackendTask, ProcessBoundTask, BackendProcess, ProcessShutdownSequence
import control.signalling as signalling

import videorotate_constants



class ProcessOrchestrator(messenger.MessagingScheduler):
    TASK = 'task'
    JOIN_TIMEOUT_SEC = 60
    
    def __init__(self) -> None:
        super().__init__()
        
        self._process_messenger_dict: Dict[TopicMessaging, MessageThreadRegistry] = {}
        
        self._process_list: Dict[Any, BackendProcess] = {}

        self._on_wx_process_shutdown = None

    def serve_requests_forever(self) -> None:
        handler = self.serve_requests()
        while True:
            next(handler)

    def recv_new_task_message(self, messenger: TopicMessaging, source_control: ReplyControl):
        if videorotate_constants.DEBUG:
            import sys
            print('Process'*50, source_control)
            sys.stdout.flush()
        
        shutdown_sent = isinstance(source_control.reply_status.reply_msg, ProcessShutdownSequence)
        if shutdown_sent:
            if isinstance(self._on_wx_process_shutdown, Callable):
                self._on_wx_process_shutdown()
            
            self.dispose()
            return
        
        process, first_process = self._get_process(source_control)
        
        return self._recv_task_message(messenger, process, source_control, first_process)
    
    # set callback
    def on_wx_process_shutdown(self, callback: Callable[[], None]) -> None:
        self._on_wx_process_shutdown = callback
    
    # (Cat-mouse problem)
    # process received message: 1.
    def _recv_task_message(self,
                           messenger: TopicMessaging,
                           process: BackendProcess,
                           source_control: ReplyControl,
                           first_process: bool):
        message = source_control.reply_status.reply_msg
        
        # reply: backend sends message back to source
        # process received message: 2.,4.,6.,..
        def reply_to_source(reply_control: ReplyControl):
            msg = reply_control.reply_status.reply_msg
            
            if videorotate_constants.DEBUG:
                import sys
                print("""
reply_to_source
Message:""", msg, """
""")
                sys.stdout.flush()
            
            shutdown_sequence = False
            
            if first_process:
                shutdown_sent = isinstance(reply_control.reply_status.reply_msg, ProcessShutdownSequence)
                
                if shutdown_sent and process.exitcode is not None:
                    process.join(self.JOIN_TIMEOUT_SEC)
                    
                    if isinstance(message, ProcessBoundTask):
                        msg = ProcessShutdownSequence(message.process_id)
                        reply_control.reply_to_message = True
                    else:
                        reply_control.reply_to_message = False
                    
                    reply_control.keep_control = False
                    source_control.keep_control = False
                    shutdown_sequence = True
            
            messenger.deferred_reply(source_control, msg)
            
            if shutdown_sequence:
                return
            
            # Using in recv_from_source
            process.reply_control = reply_control
            
            reply_control.keep_control = True
            reply_control.reply_callback = reply_to_source
        
        # sending new: OG source sends a new message to target (same thread)
        # process received message: 3.,5.,7.,..
        def recv_from_source(source_control: ReplyControl):
            msg = source_control.reply_status.reply_msg
            
            if videorotate_constants.DEBUG:
                import sys
                print('recv_from_source')
                sys.stdout.flush()
            
            process.frontend_messenger.deferred_reply(process.reply_control, msg)
            
            source_control.keep_control = True
        
        control = process.frontend_messenger.send_message(self.TASK, message, reply_to_source)
        
        if videorotate_constants.DEBUG:
            import sys
            print('add_control_to_reg', process.frontend_messenger, control)
            sys.stdout.flush()
        
        self._process_messenger_dict[process.frontend_messenger].append(control)
        
        if videorotate_constants.DEBUG:
            import sys
            print('control - Toroljuk-e? Mikor?')
            sys.stdout.flush()
        source_control.keep_control = True
        source_control.reply_callback = recv_from_source
    
    
    def _get_process(self, source_control: ReplyControl) -> BackendProcess:
        message = source_control.reply_status.reply_msg
        
        is_task = isinstance(message, BackendTask)
        bound_message = isinstance(message, signalling.ResourceBound)
        
        if videorotate_constants.DEBUG:
            import sys
            print('ENNYI_TARROL', message, self._process_list, is_task, bound_message)
            sys.stdout.flush()
        if bound_message:
            if message.target_resource_id in self._process_list:
                return self._process_list[message.target_resource_id], False
            elif not is_task:
                raise LookupError(f"Cannot deliver message to resource"
                                  f" {message.target_resource_id}: resource not found")
        elif not is_task:
            raise LookupError(f"Cannot deliver message with type {type(message)}")
        
        process = message.create_process()
        process.daemon = True
        
        frontend_socket = ProcessSocket.new_parameterless()
        backend_socket = ProcessSocket.new_inverse(frontend_socket)
        
        process.backend_messenger = TopicMessaging(backend_socket)
        #
        process.frontend_messenger = TopicMessaging(frontend_socket)
        
        frontend_registry = MessageThreadRegistry()
        frontend_trigger = partial(process.frontend_messenger.process_new_message, frontend_registry)
        self._process_messenger_dict[process.frontend_messenger] = frontend_registry
        self.add_source(process.frontend_messenger.socket, frontend_trigger)
        
        if videorotate_constants.DEBUG:
            import sys
            print('Beegetett timeout', bound_message)
            sys.stdout.flush()
        process.messenger_timeout_sec = self.MESSENGER_FALLBACK_TIMEOUT
        #process.ignore_empty_messages = True
        
        process.start()
        
        if bound_message:
            self._process_list[message.target_resource_id] = process
        
        return process, True

if __name__ == '__main__':
    import sys
    from multiprocessing import Pipe
    
    orch = ProcessOrchestrator()
    
    from backend_context import BackendProcessContext
    
    class TestTask(ProcessBoundTask):
        def run(self, control: ReplyControl, context: BackendProcessContext):
            print("Hello world from backend")
            print("No return")
            sys.stdout.flush()
            
            control.reply_to_message = True
            control.keep_control = True
            return 'OK'
        
        def create_process(self) -> BackendProcess:
            return BackendProcess()
    
    task = TestTask()
    print('Test Task:', task, task.process_id)
    
    pipe1,pipe2 = Pipe()
    socket1 = ProcessSocket(pipe1, pipe2)
    socket2 = ProcessSocket(pipe2, pipe1)

    backend_registry = MessageThreadRegistry()
    frontend_messenger = TopicMessaging(socket1)
    backend_messenger = TopicMessaging(socket2)
    
    frontend_messenger.add_listener(orch.TASK, lambda control: orch.recv_new_task_message(frontend_messenger, control))
    
    # Simulate messaging
    def handle(control: ReplyControl):
        print('Reply:',control.reply_status.reply_msg)
        sys.stdout.flush()
        
        control.reply_to_message = True
        control.keep_control = True
        return 'Yes!'
    
    control = backend_messenger.send_message(orch.TASK, task, handle)
    backend_registry.append(control)
    
    frontend_registry = MessageThreadRegistry()
    
    print("""
Control""", control, """
""")
    sys.stdout.flush()
    
    while True:
        frontend_messenger.recv_and_process_message(frontend_registry, 1.0)
        for mess_, reg in orch.process_messenger_dict.items():
            mess_.recv_and_process_message(reg, 1.0)
        
        backend_messenger.recv_and_process_message(backend_registry, 1.0)