"""
tcpdump packet capture of a real TCP handshake -- run this yourself in a
normal terminal (needs your sudo password; this sandboxed environment has
no passwordless sudo, so it can't run here).

Usage:
    sudo python3 tcpdump_handshake_demo.py
"""

import socket
import subprocess
import threading
import time


def server(port_holder, ready_event):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port_holder.append(srv.getsockname()[1])
    ready_event.set()
    conn, _ = srv.accept()
    conn.recv(1024)
    conn.close()
    srv.close()


if __name__ == "__main__":
    port_holder = []
    ready = threading.Event()
    t = threading.Thread(target=server, args=(port_holder, ready))
    t.start()
    ready.wait()
    port = port_holder[0]

    tcpdump = subprocess.Popen(
        ["tcpdump", "-i", "lo0", "-n", "-c", "6", f"port {port}"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    time.sleep(1)

    client = socket.create_connection(("127.0.0.1", port))
    client.sendall(b"hello")
    time.sleep(0.5)
    client.close()
    t.join()

    out, _ = tcpdump.communicate(timeout=5)
    print("=== Real tcpdump capture of the handshake + data + close ===")
    print(out)
    print("Look for: Flags [S] (SYN), [S.] (SYN-ACK), [.] (ACK), then data, then [F.] (FIN)")
