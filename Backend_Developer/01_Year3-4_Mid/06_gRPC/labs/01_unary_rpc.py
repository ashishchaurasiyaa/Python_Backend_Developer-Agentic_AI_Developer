"""
gRPC Lab 01 — Unary RPCs (CreateUser / GetUser)
=================================================
OBJECTIVE: end-to-end unary call using REAL generated protobuf/grpc stubs
(user_service_pb2.py / user_service_pb2_grpc.py, compiled from
user_service.proto) — not the hand-rolled fake GrpcServer/RpcContext
classes in ../practical/*.py.

TASK:
  1. Servicer.CreateUser — TODO 1: build + store a pb2.User, return it
  2. Servicer.GetUser    — TODO 2: look it up, abort NOT_FOUND if missing
  3. Client              — TODO 3: call CreateUser via the stub
  4. Client              — TODO 4: call GetUser via the stub
  5. Run: python 01_unary_rpc.py

Prereq:
  pip install grpcio grpcio-tools
  (stubs are already generated and committed; regen command is in README.md
   if you ever edit user_service.proto)
"""

import os
import sys
import threading
from concurrent import futures

import grpc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import user_service_pb2 as pb2
import user_service_pb2_grpc as pb2_grpc


class UserServicer(pb2_grpc.UserServiceServicer):
    """In-memory User store. Guarded by a lock — grpc's ThreadPoolExecutor
    can invoke servicer methods from multiple worker threads concurrently."""

    def __init__(self):
        self._users = {}
        self._next_id = 1
        self._lock = threading.Lock()

    def CreateUser(self, request, context):
        with self._lock:
            # ─────────────────────────────────────────────────────
            # TODO 1: build a pb2.User with id=self._next_id, and
            #         request.name / request.email, store it in
            #         self._users keyed by id, bump self._next_id,
            #         and set `user` to it.
            #   Hint: user = pb2.User(id=self._next_id, name=request.name,
            #                         email=request.email)
            user = None
            # ─────────────────────────────────────────────────────

            if user is None:
                context.abort(grpc.StatusCode.UNIMPLEMENTED, "TODO 1 not filled in")
            self._users[user.id] = user
            self._next_id += 1
            return user

    def GetUser(self, request, context):
        # ─────────────────────────────────────────────────────
        # TODO 2: look up request.id in self._users. If it's not
        #         there, reject the call with NOT_FOUND — that's the
        #         gRPC-native way to signal "doesn't exist", distinct
        #         from returning an empty/default User.
        #   Hint: user = self._users.get(request.id)
        #         if user is None:
        #             context.abort(grpc.StatusCode.NOT_FOUND,
        #                            f"user {request.id} not found")
        user = "TODO_NOT_FILLED"
        # ─────────────────────────────────────────────────────

        if user == "TODO_NOT_FILLED":
            context.abort(grpc.StatusCode.UNIMPLEMENTED, "TODO 2 not filled in")
        return user


def start_server():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    pb2_grpc.add_UserServiceServicer_to_server(UserServicer(), server)
    port = server.add_insecure_port("[::]:0")   # 0 = let the OS pick a free port
    server.start()
    return server, port


def main() -> None:
    server, port = start_server()
    channel = grpc.insecure_channel(f"localhost:{port}")
    stub = pb2_grpc.UserServiceStub(channel)

    try:
        print(f"\n[server] listening on :{port}")

        print("\n[1] CreateUser...")
        created = None
        # ─────────────────────────────────────────────────────
        # TODO 3: call stub.CreateUser(...) with a CreateUserRequest
        #         (name="Ada Lovelace", email="ada@example.com") and
        #         store the response in `created`.
        #   Hint: created = stub.CreateUser(
        #             pb2.CreateUserRequest(name="Ada Lovelace",
        #                                    email="ada@example.com"))
        # ─────────────────────────────────────────────────────

        if created is None:
            print("❌ TODO 3 abhi bharna hai")
            return
        print(f"  → created {created}".replace("\n", " "))

        print("\n[2] GetUser...")
        fetched = None
        # ─────────────────────────────────────────────────────
        # TODO 4: call stub.GetUser(...) with GetUserRequest(id=created.id)
        #         and store the response in `fetched`.
        #   Hint: fetched = stub.GetUser(pb2.GetUserRequest(id=created.id))
        # ─────────────────────────────────────────────────────

        if fetched is None:
            print("❌ TODO 4 abhi bharna hai")
            return
        print(f"  ← fetched {fetched}".replace("\n", " "))

        print("\n" + "─" * 55)
        if (fetched.id == created.id
                and fetched.name == created.name
                and fetched.email == created.email):
            print("✅ PASS — round-tripped user matches exactly "
                  f"(id={fetched.id}, name={fetched.name!r}, email={fetched.email!r})")
        else:
            print("❌ FAIL — fetched user does not match created user")
            print(f"   created={created}\n   fetched={fetched}")

        print("""
SOCH (bolke jawab do):
  1. proto3 me field unset chhodo to default value kya hota hai
     (int32 => 0, string => "")? REST/JSON me null explicit hota hai —
     yeh farak client code me kya bug paida kar sakta hai?
  2. `context.abort()` grpc runtime ko kya karne ko bolta hai — aur
     client side pe yeh kis exception/status ke roop me dikhta hai?
  3. .proto me field numbers (=1, =2...) kyun important hain? Agar tum
     ek field rename karo par number wahi rakho, kya wire-compatible
     rehta hai purane clients ke liye?
""")
    finally:
        server.stop(grace=None)
        channel.close()


if __name__ == "__main__":
    main()
