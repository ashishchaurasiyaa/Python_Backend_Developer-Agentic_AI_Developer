"""
CLOSE_WAIT -- verified practical: force a real CLOSE_WAIT by having the
client close its side while the server deliberately does NOT close (the
exact bug scenario the notes warn about).
"""

import socket
import subprocess
import threading
import time


def lsof_state(port):
    try:
        return subprocess.check_output(
            ["lsof", "-nP", "-iTCP:" + str(port)], text=True, stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError:
        return "(nothing found via lsof)"


def server(port_holder, ready_event, hold_event):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port_holder.append(srv.getsockname()[1])
    ready_event.set()

    conn, addr = srv.accept()
    print(f"  [SERVER] accepted connection from {addr}")

    data = conn.recv(1024)
    print(f"  [SERVER] recv() returned {data!r} (empty = client sent FIN)")
    print("  [SERVER] deliberately NOT calling close() -- this is the bug scenario")

    hold_event.wait()
    conn.close()
    srv.close()


if __name__ == "__main__":
    port_holder = []
    ready = threading.Event()
    hold = threading.Event()
    t = threading.Thread(target=server, args=(port_holder, ready, hold))
    t.start()
    ready.wait()
    port = port_holder[0]

    client = socket.create_connection(("127.0.0.1", port))
    time.sleep(0.1)
    client.shutdown(socket.SHUT_WR)
    time.sleep(0.3)

    print("=== After client's FIN, server-side socket state ===")
    print(lsof_state(port))
    print("  (this IS CLOSE_WAIT -- remote closed, but the SERVER application hasn't")
    print("   called close() yet -- exactly the notes' item 29/30 scenario)")

    hold.set()
    t.join()
    client.close()
