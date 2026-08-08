"""
gRPC Lab 03 — Deadlines & Retry-with-Backoff
=================================================
OBJECTIVE (two parts):
  (a) client sets a deadline shorter than a deliberately slow server
      method → prove grpc.RpcError with DEADLINE_EXCEEDED is actually
      raised.
  (b) implement a retry-with-backoff wrapper around a call that fails
      with UNAVAILABLE the first 2 attempts (simulated via a server-side
      counter) then succeeds → prove the 3rd attempt succeeds and the
      attempt count matches.

TASK:
  1. Client — TODO 1: call with a short `timeout=`, catch grpc.RpcError,
     return whether the code is DEADLINE_EXCEEDED
  2. Client — TODO 2: implement the retry body inside call_with_retry()
  3. Run: python 03_deadlines_retries.py

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

SLOW_USER_ID = 1
RETRY_USER_ID = 2
SLOW_DELAY = 1.0          # server sleeps this long for SLOW_USER_ID
CLIENT_DEADLINE = 0.2     # client timeout — much shorter than SLOW_DELAY
FAIL_FIRST_N = 2          # RETRY_USER_ID fails this many times before succeeding


class UserServicer(pb2_grpc.UserServiceServicer):
    """Two special user ids for the two sub-experiments:
      - SLOW_USER_ID:  GetUser sleeps SLOW_DELAY before responding
      - RETRY_USER_ID: GetUser fails with UNAVAILABLE the first
                        FAIL_FIRST_N calls, then succeeds
    """

    def __init__(self):
        self._users = {
            SLOW_USER_ID: pb2.User(id=SLOW_USER_ID, name="Slow Sam", email="sam@example.com"),
            RETRY_USER_ID: pb2.User(id=RETRY_USER_ID, name="Retry Rae", email="rae@example.com"),
        }
        self._attempts = {}
        self._lock = threading.Lock()

    def CreateUser(self, request, context):
        context.abort(grpc.StatusCode.UNIMPLEMENTED, "not used in this lab")

    def GetUser(self, request, context):
        if request.id == SLOW_USER_ID:
            time.sleep(SLOW_DELAY)
            return self._users[request.id]

        if request.id == RETRY_USER_ID:
            with self._lock:
                self._attempts[request.id] = self._attempts.get(request.id, 0) + 1
                attempt_no = self._attempts[request.id]
            if attempt_no <= FAIL_FIRST_N:
                context.abort(grpc.StatusCode.UNAVAILABLE,
                               f"simulated flaky dependency (attempt {attempt_no})")
            return self._users[request.id]

        context.abort(grpc.StatusCode.NOT_FOUND, f"user {request.id} not found")

    def ListUsers(self, request, context):
        context.abort(grpc.StatusCode.UNIMPLEMENTED, "not used in this lab")
        yield  # pragma: no cover


def start_server():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    pb2_grpc.add_UserServiceServicer_to_server(UserServicer(), server)
    port = server.add_insecure_port("[::]:0")
    server.start()
    return server, port


def call_expect_deadline_exceeded(stub):
    """Call GetUser(SLOW_USER_ID) with a deadline shorter than the
    server's sleep. Returns the grpc.StatusCode actually observed, or
    None if the call unexpectedly succeeded."""

    # ─────────────────────────────────────────────────────
    # TODO 1: call stub.GetUser(pb2.GetUserRequest(id=SLOW_USER_ID),
    #         timeout=CLIENT_DEADLINE) inside a try/except grpc.RpcError.
    #         On success (shouldn't happen): return None.
    #         On grpc.RpcError: return e.code().
    #   Hint: try:
    #             stub.GetUser(pb2.GetUserRequest(id=SLOW_USER_ID),
    #                          timeout=CLIENT_DEADLINE)
    #             return None
    #         except grpc.RpcError as e:
    #             return e.code()
    # ─────────────────────────────────────────────────────
    print("  ❌ TODO 1 abhi bharna hai")
    return "TODO_NOT_FILLED"


def call_with_retry(stub, user_id, max_attempts=5, backoff_base=0.05):
    """Retry wrapper: retries on UNAVAILABLE with linear backoff.
    Returns (result_or_None, attempts_made)."""
    attempts_made = 0

    for attempt in range(1, max_attempts + 1):
        attempts_made = attempt

        # ─────────────────────────────────────────────────────
        # TODO 2: try stub.GetUser(pb2.GetUserRequest(id=user_id)).
        #   - on success: `return result, attempts_made`
        #   - on grpc.RpcError with code UNAVAILABLE: sleep
        #     backoff_base * attempt, then let the for-loop continue
        #     (retry)
        #   - on any other grpc.RpcError: re-raise
        #   Hint: try:
        #             result = stub.GetUser(pb2.GetUserRequest(id=user_id))
        #             return result, attempts_made
        #         except grpc.RpcError as e:
        #             if e.code() == grpc.StatusCode.UNAVAILABLE:
        #                 time.sleep(backoff_base * attempt)
        #                 continue
        #             raise
        # ─────────────────────────────────────────────────────
        pass
        # ─────────────────────────────────────────────────────

    return None, attempts_made


def main() -> None:
    server, port = start_server()
    channel = grpc.insecure_channel(f"localhost:{port}")
    stub = pb2_grpc.UserServiceStub(channel)
    overall_pass = True

    try:
        print(f"\n[server] listening on :{port}")

        print(f"\n[1] Deadline test — client timeout={CLIENT_DEADLINE}s, "
              f"server sleeps {SLOW_DELAY}s")
        code = call_expect_deadline_exceeded(stub)
        if code == grpc.StatusCode.DEADLINE_EXCEEDED:
            print(f"  ✅ got {code} as expected")
        else:
            overall_pass = False
            if code is None:
                print("  ❌ FAIL — call succeeded, deadline never enforced. "
                      "Check TODO 1's `timeout=` kwarg.")
            elif code == "TODO_NOT_FILLED":
                print("  ❌ FAIL — TODO 1 abhi bharna hai.")
            else:
                print(f"  ❌ FAIL — got {code}, expected DEADLINE_EXCEEDED.")

        print(f"\n[2] Retry test — server fails first {FAIL_FIRST_N} attempts, "
              "then succeeds")
        result, attempts = call_with_retry(stub, RETRY_USER_ID, max_attempts=5)
        expected_attempts = FAIL_FIRST_N + 1
        if result is not None and attempts == expected_attempts and result.id == RETRY_USER_ID:
            print(f"  ✅ succeeded on attempt {attempts} (expected {expected_attempts}), "
                  f"got {result.name!r}")
        else:
            overall_pass = False
            if result is None:
                print(f"  ❌ FAIL — never succeeded after {attempts} attempts. "
                      "TODO 2 abhi bharna hai (ya UNAVAILABLE ko re-raise kar rahe ho).")
            else:
                print(f"  ❌ FAIL — succeeded on attempt {attempts}, expected "
                      f"{expected_attempts}. Retry loop attempt-counting check karo.")

        print("\n" + "─" * 55)
        if overall_pass:
            print("✅ PASS — deadline enforced AND retry-with-backoff worked")
        else:
            print("❌ FAIL — ek ya dono sub-tests fail hue, upar detail dekho")

        print(f"""
SOCH (bolke jawab do):
  1. Deadline client-side hoti hai ya server ko bhi pata chalta hai?
     (Hint: deadline metadata me propagate hoti hai — server bhi
     `context.time_remaining()` se dekh sakta hai aur kaam early abort
     kar sakta hai — "deadline propagation".)
  2. UNAVAILABLE pe retry karna theek hai, par NOT_FOUND ya
     INVALID_ARGUMENT pe retry karna kyun galat hai? Kaunse status codes
     generally "retryable" mane jaate hain?
  3. Exponential backoff + jitter kyun use karte hain sirf fixed delay
     ke bajaye — "retry storm" / "thundering herd" se kaise bachata hai?
  4. gRPC ka built-in `service_config` retry policy client-code me
     retry likhne se better kyun ho sakta hai?
""")
    finally:
        server.stop(grace=None)
        channel.close()


if __name__ == "__main__":
    main()
