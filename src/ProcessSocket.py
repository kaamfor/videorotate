from multiprocessing import Pipe
from multiprocessing.connection import Connection
from socket import socket
from typing import Optional, Any, Union

import messenger

class ProcessSocket(messenger.SimplePipeSocket):
    @property
    def source(self) -> Connection:
        return self._source
    
    def __init__(self, source: Connection, connection: Connection) -> None:
        super().__init__(connection)
        self._source = source
    
    @classmethod
    def new_parameterless(cls):
        con1, con2 = Pipe()
        return cls(con1, con2)
    
    @classmethod
    def new_inverse(cls, other_socket):
        assert isinstance(other_socket, ProcessSocket)
        
        return cls(source=other_socket.connection, connection=other_socket.source)
