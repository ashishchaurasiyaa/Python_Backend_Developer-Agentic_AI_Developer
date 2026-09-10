"""
TIME_WAIT pile-up -- verified practical: rapid open/close connections
(no pooling) and count how many end up in TIME_WAIT, using real sockets.

Note: TIME_WAIT lands on whichever side sends the closing FIN FIRST (the
"active closer") -- usually the client here since it calls close() right
after send(), but the server's own close() can occasionally race ahead
for a given connection, putting the SERVER side into TIME_WAIT instead.
This script reports both, so the counts are transparent rather than
silently assuming "it's always the client."
"""

import socket
import subprocess
import threading
import time

N_CONNECTIONS = 20


def run_server(server_sock, stop_event):
    while not stop_event.is_set():
        try:
            server_sock.settimeout(0.5)
            conn, _ = server_sock.accept()
            conn.recv(16)
            conn.close()
        except socket.timeout:
            continue


def time_wait_lines(port):
    out = subprocess.run(["netstat", "-an"], capture_output=True, text=True).stdout
    needle = f".{port} "  # anchored so e.g. port 307 doesn't match foreign port 62307
    return [line for line in out.splitlines() if "TIME_WAIT" in line and needle in line]


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(5)
    port = server.getsockname()[1]
    print(f"Server on 127.0.0.1:{port} -- simulating a service with NO connection pooling\n")

    stop_event = threading.Event()
    t = threading.Thread(target=run_server, args=(server, stop_event))
    t.start()

    print(f"Client opening + closing {N_CONNECTIONS} short-lived connections rapidly (no reuse)...")
    for _ in range(N_CONNECTIONS):
        c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        c.connect(("127.0.0.1", port))
        c.send(b"hi")
        c.close()  # client is USUALLY the active closer here

    time.sleep(0.5)
    lines = time_wait_lines(port)
    # netstat -an columns: Proto Recv-Q Send-Q Local-Address Foreign-Address State
    client_side = [l for l in lines if l.split()[4].endswith(f".{port}")]  # server port is the FOREIGN address
    server_side = [l for l in lines if l.split()[3].endswith(f".{port}")]  # server port is the LOCAL address

    print(f"\nTotal TIME_WAIT sockets tied to this port: {len(lines)} (out of {N_CONNECTIONS} connections)")
    print(f"  Client-side TIME_WAIT (client closed first): {len(client_side)}")
    print(f"  Server-side TIME_WAIT (server raced ahead and closed first): {len(server_side)}")
    print("\nEach TIME_WAIT socket holds its port reserved for ~60s (macOS/Linux default) before reuse.")
    print("At production scale (thousands of short-lived connections/sec with no pooling),")
    print("this is exactly how you exhaust ephemeral ports -> 'Cannot assign requested address'.")

    stop_event.set()
    t.join()
    server.close()


if __name__ == "__main__":
    main()
