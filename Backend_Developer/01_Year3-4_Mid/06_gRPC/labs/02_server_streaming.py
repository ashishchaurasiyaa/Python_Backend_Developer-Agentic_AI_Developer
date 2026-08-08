"""
gRPC Lab 02 — Server Streaming (ListUsers)
=================================================
OBJECTIVE: implement a REAL server-streaming RPC — the server `yield`s
User messages one at a time, and the client processes them AS THEY
ARRIVE (not as one big batched list). This is what separates gRPC
streaming from "return a list over unary RPC".

TASK:
  1. Servicer.ListUsers — TODO 1: yield each stored user ONE AT A TIME,
     with a short sleep between each yield
  2. Client             — TODO 2: iterate the stream, recording an
     arrival timestamp for every item as it comes in
  3. Run: python 02_server_streaming.py

Prereq:
  pip install grpcio grpcio-tools
"""

import os
import sys
import threading
import time
from concurrent import futures

import grpc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import user_service_pb2 as pb2
import user_service_pb2_grpc as pb2_grpc

N_USERS = 5
STREAM_DELAY = 0.15   # seconds between each streamed item — long enough to measure


class UserServicer(pb2_grpc.UserServiceServicer):
    def __init__(self):
        self._users = {}
        self._next_id = 1
        self._lock = threading.Lock()

    def CreateUser(self, request, context):
        with self._lock:
            user = pb2.User(id=self._next_id, name=request.name, email=request.email)
            self._users[user.id] = user
            self._next_id += 1
            return user

    def GetUser(self, request, context):
        user = self._users.get(request.id)
        if user is None:
            context.abort(grpc.StatusCode.NOT_FOUND, f"user {request.id} not found")
        return user

    def ListUsers(self, request, context):
        users_sorted = sorted(self._users.values(), key=lambda u: u.id)

        # ─────────────────────────────────────────────────────
        # TODO 1: yield each user in `users_sorted` ONE AT A TIME,
        #         sleeping STREAM_DELAY seconds before each yield.
        #         That sleep is the proof this is a genuine stream —
        #         a fake "batch" response couldn't have gaps between
        #         items.
        #   Hint: for user in users_sorted:
        #             time.sleep(STREAM_DELAY)
        #             yield user
        # ─────────────────────────────────────────────────────
        context.abort(grpc.StatusCode.UNIMPLEMENTED, "TODO 1 not filled in")
        yield  # pragma: no cover — keeps this a generator; unreachable until TODO 1 is done


def start_server():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    pb2_grpc.add_UserServiceServicer_to_server(UserServicer(), server)
    port = server.add_insecure_port("[::]:0")
    server.start()
    return server, port


def seed_users(stub, n):
    for i in range(n):
        stub.CreateUser(pb2.CreateUserRequest(name=f"User{i}", email=f"user{i}@example.com"))


def collect_stream(stub):
    """Iterate the server stream, recording an arrival timestamp for
    every item AS IT ARRIVES (not after collecting everything)."""
    received = []
    arrival_times = []

    # ─────────────────────────────────────────────────────
    # TODO 2: iterate `stub.ListUsers(pb2.ListUsersRequest(page_size=0))`
    #         with a for loop. For every `user` you get, append
    #         time.monotonic() to arrival_times and `user` to received
    #         IMMEDIATELY inside the loop body (that's what proves
    #         per-item processing, not batch processing).
    #   Hint: for user in stub.ListUsers(pb2.ListUsersRequest(page_size=0)):
    #             arrival_times.append(time.monotonic())
    #             received.append(user)
    # ─────────────────────────────────────────────────────

    return received, arrival_times


def main() -> None:
    server, port = start_server()
    channel = grpc.insecure_channel(f"localhost:{port}")
    stub = pb2_grpc.UserServiceStub(channel)

    try:
        print(f"\n[server] listening on :{port}")

        print(f"\n[1] Seeding {N_USERS} users...")
        seed_users(stub, N_USERS)

        print("\n[2] Streaming ListUsers...")
        received, arrival_times = collect_stream(stub)
        for u in received:
            print(f"  ← got {u.id} {u.name!r}")

        print("\n" + "─" * 55)

        if len(received) != N_USERS:
            print(f"❌ FAIL — got {len(received)}/{N_USERS} users.")
            print("   TODO 2 (client iteration) ya TODO 1 (server yield) check karo.")
            return

        ids = [u.id for u in received]
        if ids != sorted(ids):
            print(f"❌ FAIL — order galat hai: {ids} (expected sorted by id)")
            return

        if len(arrival_times) != N_USERS:
            print(f"❌ FAIL — sirf {len(arrival_times)} arrival timestamps record hue "
                  f"(expected {N_USERS}). TODO 2 me har item ke saath timestamp record karo.")
            return

        gaps = [arrival_times[i + 1] - arrival_times[i] for i in range(len(arrival_times) - 1)]
        min_gap = min(gaps) if gaps else 0
        genuinely_streamed = len(gaps) == N_USERS - 1 and min_gap > STREAM_DELAY * 0.4

        if genuinely_streamed:
            total = arrival_times[-1] - arrival_times[0]
            print(f"✅ PASS — {N_USERS} users, in order, streamed over {total:.2f}s "
                  f"(min gap between items {min_gap:.2f}s) — proves real streaming, "
                  "not one blocking batch")
        else:
            print(f"❌ FAIL — items arrived too close together (min gap {min_gap:.3f}s, "
                  f"expected > {STREAM_DELAY * 0.4:.2f}s). Check TODO 1's sleep is "
                  "actually between yields, and TODO 2 timestamps each item as it arrives.")

        print(f"""
SOCH (bolke jawab do):
  1. Server streaming me client `for user in stub.ListUsers(...)` likhta
     hai — yeh HTTP/2 ke kaunse feature (multiplexed streams) pe rely
     karta hai jo HTTP/1.1 me possible nahi tha?
  2. Agar client sirf 2 items ke baad `break` kar de, server ko pata
     kaise chalta hai ki ruk jaye? (Hint: context.cancelled())
  3. Server streaming vs "unary RPC jo repeated field return kare" —
     bade result sets (lakhon rows) ke liye memory/latency trade-off
     kya hai?
""")
    finally:
        server.stop(grace=None)
        channel.close()


if __name__ == "__main__":
    main()
