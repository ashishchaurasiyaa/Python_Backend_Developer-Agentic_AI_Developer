"""
gRPC Lab 04 — Server Interceptor for Auth
=================================================
OBJECTIVE: implement a REAL grpc.ServerInterceptor that rejects calls
missing (or carrying the wrong) `authorization` metadata header with
UNAUTHENTICATED — BEFORE the servicer method ever runs. The servicer
below has ZERO auth logic of its own, so a passing test here can only
mean the interceptor is doing the work.

TASK:
  1. AuthInterceptor.intercept_service — TODO 1: return the deny handler
     when the token doesn't match; fall through to continuation() when
     it does
  2. Client — TODO 2: call WITHOUT the header, expect UNAUTHENTICATED
  3. Client — TODO 3: call WITH the correct header, expect success
  4. Run: python 04_interceptor_auth.py

Prereq:
  pip install grpcio grpcio-tools
"""

import os
import sys
from concurrent import futures

import grpc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import user_service_pb2 as pb2
import user_service_pb2_grpc as pb2_grpc

EXPECTED_TOKEN = "Bearer lab-secret-token"


class UserServicer(pb2_grpc.UserServiceServicer):
    """Deliberately has NO auth check of its own — if a call without
    the right header ever reaches here, the interceptor failed."""

    def __init__(self):
        self._users = {1: pb2.User(id=1, name="Ada Lovelace", email="ada@example.com")}

    def CreateUser(self, request, context):
        context.abort(grpc.StatusCode.UNIMPLEMENTED, "not used in this lab")

    def GetUser(self, request, context):
        user = self._users.get(request.id)
        if user is None:
            context.abort(grpc.StatusCode.NOT_FOUND, f"user {request.id} not found")
        return user

    def ListUsers(self, request, context):
        context.abort(grpc.StatusCode.UNIMPLEMENTED, "not used in this lab")
        yield  # pragma: no cover


class AuthInterceptor(grpc.ServerInterceptor):
    """Rejects any call whose `authorization` metadata doesn't match
    EXPECTED_TOKEN — before the real servicer method runs."""

    def __init__(self, expected_token: str):
        self._expected_token = expected_token

        def _deny(request, context):
            context.abort(grpc.StatusCode.UNAUTHENTICATED,
                           "missing or invalid authorization header")

        self._deny_handler = grpc.unary_unary_rpc_method_handler(_deny)

    def intercept_service(self, continuation, handler_call_details):
        metadata = dict(handler_call_details.invocation_metadata or ())
        token = metadata.get("authorization")

        # ─────────────────────────────────────────────────────
        # TODO 1: if token != self._expected_token, return
        #         self._deny_handler INSTEAD of calling continuation(...).
        #         Otherwise fall through to the real handler.
        #   Hint: if token != self._expected_token:
        #             return self._deny_handler
        #         return continuation(handler_call_details)
        # ─────────────────────────────────────────────────────
        return continuation(handler_call_details)


def start_server():
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=4),
        interceptors=[AuthInterceptor(EXPECTED_TOKEN)],
    )
    pb2_grpc.add_UserServiceServicer_to_server(UserServicer(), server)
    port = server.add_insecure_port("[::]:0")
    server.start()
    return server, port


def call_without_auth(stub):
    """Returns the grpc.StatusCode observed, or None if it unexpectedly
    succeeded."""
    # ─────────────────────────────────────────────────────
    # TODO 2: call stub.GetUser(pb2.GetUserRequest(id=1)) with NO
    #         metadata kwarg, inside try/except grpc.RpcError.
    #         On success (shouldn't happen): return None.
    #         On grpc.RpcError: return e.code().
    # ─────────────────────────────────────────────────────
    print("  ❌ TODO 2 abhi bharna hai")
    return "TODO_NOT_FILLED"


def call_with_auth(stub):
    """Returns the User on success, or None on failure."""
    # ─────────────────────────────────────────────────────
    # TODO 3: call stub.GetUser(pb2.GetUserRequest(id=1),
    #         metadata=(("authorization", EXPECTED_TOKEN),)) and return
    #         the result. Return None if it raises.
    #   Hint: try:
    #             return stub.GetUser(pb2.GetUserRequest(id=1),
    #                                  metadata=(("authorization", EXPECTED_TOKEN),))
    #         except grpc.RpcError:
    #             return None
    # ─────────────────────────────────────────────────────
    print("  ❌ TODO 3 abhi bharna hai")
    return None


def main() -> None:
    server, port = start_server()
    channel = grpc.insecure_channel(f"localhost:{port}")
    stub = pb2_grpc.UserServiceStub(channel)
    overall_pass = True

    try:
        print(f"\n[server] listening on :{port} (AuthInterceptor active)")

        print("\n[1] Call WITHOUT authorization header...")
        code = call_without_auth(stub)
        if code == grpc.StatusCode.UNAUTHENTICATED:
            print(f"  ✅ rejected with {code} as expected")
        else:
            overall_pass = False
            if code is None:
                print("  ❌ FAIL — call succeeded without auth! Interceptor "
                      "isn't rejecting (TODO 1).")
            elif code == "TODO_NOT_FILLED":
                print("  ❌ FAIL — TODO 2 abhi bharna hai.")
            else:
                print(f"  ❌ FAIL — got {code}, expected UNAUTHENTICATED.")

        print("\n[2] Call WITH correct authorization header...")
        user = call_with_auth(stub)
        if user is not None and user.id == 1 and user.name == "Ada Lovelace":
            print(f"  ✅ succeeded, got {user.name!r}")
        else:
            overall_pass = False
            print("  ❌ FAIL — call with correct header should have succeeded. "
                  "TODO 1 (interceptor logic) ya TODO 3 (client call) check karo.")

        print("\n" + "─" * 55)
        if overall_pass:
            print("✅ PASS — interceptor genuinely intercepts: rejects without "
                  "auth, allows with correct auth (servicer itself has no auth "
                  "check of its own)")
        else:
            print("❌ FAIL — upar detail dekho")

        print("""
SOCH (bolke jawab do):
  1. Interceptor `continuation(handler_call_details)` ko call NAHI
     karta jab reject karta hai — iska matlab servicer method kabhi
     invoke hi nahi hota. Yeh "in-method check" se kaise different hai
     security ke perspective se (defense in depth)?
  2. Metadata (headers) vs message fields — authorization TOKEN ko
     message field me bhejna (GetUserRequest.token) kyun galat design
     hai compared to metadata?
  3. Client interceptors bhi hote hain (grpc.UnaryUnaryClientInterceptor)
     — woh kis use case ke liye hain jo server interceptor nahi kar
     sakta? (Hint: outgoing metadata inject karna, jaise trace context)
  4. Production me token verify karne ke liye interceptor me DB/cache
     call karna theek hai? Latency impact kya hoga HAR request pe?
""")
    finally:
        server.stop(grace=None)
        channel.close()


if __name__ == "__main__":
    main()
