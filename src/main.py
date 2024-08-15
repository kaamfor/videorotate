import builtins
import multiprocessing
from functools import partial

from messaging.topic import TopicMessaging, MessageThreadRegistry
from ProcessSocket import ProcessSocket

from multiprocessing import Pipe

from gui.wx_process import WxProcess
from orchestrator import ProcessOrchestrator
from gui.frames.MainWindowController import MainWindowController

builtins.print(
    f"started,,, {multiprocessing.current_process().name} {__name__} {globals().get('wx_process', None)} {globals().get('process_message', None)}")

import pathlib
ROOT_PATH = pathlib.Path(__file__).parent.absolute()

if __name__ == '__main__':
    builtins.print(
        f"Main process name: {multiprocessing.current_process().name}")

    #wx_process = WxProcess(daemon=True, args=(ROOT_PATH,))
    wx_process = WxProcess(daemon=True)
    wx_process.notifier_topic = 'gui'

    wx_pipe1,wx_pipe2 = Pipe()
    wx_socket1 = ProcessSocket(wx_pipe1, wx_pipe2)
    wx_socket2 = ProcessSocket(wx_pipe2, wx_pipe1)

    wx_process_registry = MessageThreadRegistry()
    wx_process.frontend_messenger = TopicMessaging(wx_socket1)
    wx_process.backend_messenger = TopicMessaging(wx_socket2)

    wx_process.first_window_controller = MainWindowController.__name__


    wx_process.start()

    orchestrator = ProcessOrchestrator()

    messenger = wx_process.frontend_messenger
    messenger.add_listener(orchestrator.TASK, lambda control: orchestrator.recv_new_task_message(messenger, control))

    process_message = True
    def on_shutdown():
        global process_message
        process_message = False
        
        import sys
        print('Global_on_shutdown')
        sys.stdout.flush()
        
        #wx_process.join()
        exit(0)
    
    orchestrator.on_wx_process_shutdown(on_shutdown)
    
    orchestrator._process_messenger_dict[messenger] = wx_process_registry
    
    messenger_trigger = partial(messenger.process_new_message, wx_process_registry)
    orchestrator.add_source(messenger.socket, messenger_trigger)
    
    orchestrator.serve_requests_forever()

