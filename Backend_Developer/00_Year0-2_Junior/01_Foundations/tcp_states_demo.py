"""
TCP -- verified practical: watch real TCP state transitions
(LISTEN -> ESTABLISHED -> TIME_WAIT) using the file's own server/client
pattern, cross-checked against real OS tools (lsof for LISTEN/ESTABLISHED,
netstat for TIME_WAIT -- lsof's -iTCP:port filter was found NOT to
reliably show TIME_WAIT entries on macOS once the listening socket
itself has also closed; netstat -an does).
"""

import socket
import subprocess
import threading
import time


def lsof_state(port: int) -> str:
    try:
        return subprocess.check_output(
            ["lsof", "-nP", "-iTCP:" + str(port)], text=True, stderr=subprocess.DEVNULL
        )
    except subprocess.CalledProcessError:
        return "(nothing found via lsof)"


def netstat_state(port: int) -> str:
    out = subprocess.check_output(["netstat", "-an", "-p", "tcp"], text=True)
    matches = [line for line in out.splitlines() if f".{port} " in line or f".{port}\t" in line or str(port) in line]
    return "\n".join(matches) if matches else "(nothing found via netstat)"


def server(port_holder, ready_event, close_after):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(5)
    port_holder.append(srv.getsockname()[1])
    ready_event.set()

    conn, addr = srv.accept()
    print(f"  [SERVER] accepted connection from {addr}")
    time.sleep(close_after)
    conn.close()
    srv.close()


if __name__ == "__main__":
    port_holder = []
    ready = threading.Event()
    t = threading.Thread(target=server, args=(port_holder, ready, 0.3))
    t.start()
    ready.wait()
    port = port_holder[0]

    print(f"=== Step 1: server LISTENing on 127.0.0.1:{port} ===")
    print(lsof_state(port))

    print("=== Step 2: client connects -- 3-way handshake happens here ===")
    client = socket.create_connection(("127.0.0.1", port))
    time.sleep(0.1)
    print(lsof_state(port))
    print("  (ESTABLISHED shown on BOTH sides -- client's ephemeral port and")
    print("   the server's listening port, cross-connected)\n")

    client.close()  # client closes first -> client side enters TIME_WAIT
    t.join()
    time.sleep(0.1)

    print("=== Step 3: after close() -- TIME_WAIT (whichever side closed first) ===")
    print(netstat_state(port))
    print("  (real TIME_WAIT entry, not simulated -- this is the exact state")
    print("   the theory section warns piles up under high short-connection")
    print("   churn, exhausting ephemeral ports if you don't pool connections)")
