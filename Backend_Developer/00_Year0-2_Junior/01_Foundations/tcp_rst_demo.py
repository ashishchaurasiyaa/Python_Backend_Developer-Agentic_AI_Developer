"""
RST -- verified practical: force a real 'Connection reset by peer' using
SO_LINGER(onoff=1, linger=0), which makes the TCP stack send RST instead
of a graceful FIN when the socket is closed.
"""

import socket
import struct
import time

if __name__ == "__main__":
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    host, port = server.getsockname()

    client = socket.create_connection((host, port))
    conn, _ = server.accept()

    print("Server closing with SO_LINGER(onoff=1, linger=0) -- forces RST instead of FIN")
    conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    conn.close()
    server.close()

    time.sleep(0.2)
    try:
        client.sendall(b"are you still there?")
        response = client.recv(1024)
        print("Unexpectedly got a response:", response)
    except (ConnectionResetError, BrokenPipeError) as e:
        print(f"\nClient got exactly the error backend devs see in production:")
        print(f"  {type(e).__name__}: {e}")
        print("This is TCP's RST flag in action -- the notes' 'Connection reset by peer' (item 25).")

    client.close()
