from threading import Lock
from websockets.sync.server import ServerConnection

class ThreadSafeSocket:
    """
    A thread-safe socket object that protects the writing end of the
    connection to prevent interleaved writes.
    
    These are separated as reading and writing is something we want
    to happen all the time on a duplex connection, and so they
    must be handled separately.
    """
    websocket: ServerConnection
    write_lock: Lock
    
    def __init__(self, sock: ServerConnection):
        """
        Creates a new thread safe socket object.

        Args:
            sock (socket.socket): The socket object that
            we wish to wrap.
        """
        self.raw_socket = sock
        self.write_lock = Lock()
        self.closed = False
        
    def sendall(self, data: bytes):
        """
        Sends all the bytes across the socket.

        Args:
            data (bytes): The data to send over the socket.
        """
        with self.write_lock:
            self.raw_socket.send(data, text=True)
            
    def recv(self, data: int) -> bytes:
        """
        Receives a certain number of bytes over the
        thread safe socket.

        Args:
            data (int): The length of bytes we want to read.

        Returns:
            bytes: The byte buffer we received.
        """
        out = self.raw_socket.recv()
        if type(out) == bytes:
            return out
        # print(out)
        
        return out.encode('utf-8')
    
    def close(self):
        self.raw_socket.close()