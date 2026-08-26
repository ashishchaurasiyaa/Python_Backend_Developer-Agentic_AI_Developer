"""
Task Cancellation — asyncio.Task.cancel()

Cancellation ka use: timeout, user abort, resource limit hit.
CancelledError ek BaseException hai — except Exception se catch nahi hoti!
"""

import asyncio

# ─── Basic cancellation ───────────────────────────────────────────────────

async def long_running_job(job_id: int) -> str:
    print(f"  Job {job_id} started")
    try:
        await asyncio.sleep(10)  # simulate long work
        return f"Job {job_id} done"
    except asyncio.CancelledError:
        print(f"  Job {job_id} was CANCELLED — cleanup karo")
        # Cleanup: close file handles, DB connections, etc.
        raise  # Always re-raise CancelledError!

async def demo_cancel():
    print("=== Task Cancellation ===")
    task = asyncio.create_task(long_running_job(1))

    await asyncio.sleep(1)  # 1 sec ke baad cancel karo

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        print(f"  Confirmed: task cancelled. task.cancelled() = {task.cancelled()}")

asyncio.run(demo_cancel())

# ─── Multiple tasks, cancel all on first failure ──────────────────────────

async def worker(name: str, should_fail: bool) -> str:
    try:
        await asyncio.sleep(2)
        if should_fail:
            raise RuntimeError(f"{name} failed!")
        return f"{name} success"
    except asyncio.CancelledError:
        print(f"  {name}: cancelled due to sibling failure")
        raise

async def demo_cancel_on_failure():
    print("\n=== Ek task fail hone pe baaki sab cancel ===")
    tasks = [
        asyncio.create_task(worker("task-A", should_fail=False)),
        asyncio.create_task(worker("task-B", should_fail=True)),   # ye fail hoga
        asyncio.create_task(worker("task-C", should_fail=False)),
    ]

    # gather() without return_exceptions cancels ALL on first exception
    try:
        results = await asyncio.gather(*tasks)
    except RuntimeError as e:
        print(f"  One task failed: {e}")
        # Cancel remaining tasks
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        print("  All tasks cleaned up")

asyncio.run(demo_cancel_on_failure())

# ─── task.done() / task.cancelled() / task.result() ─────────────────────

async def demo_task_state():
    print("\n=== Task State Methods ===")
    task = asyncio.create_task(asyncio.sleep(0.1))
    print(f"  Before await  — done: {task.done()}")
    await task
    print(f"  After await   — done: {task.done()}, cancelled: {task.cancelled()}")

asyncio.run(demo_task_state())

# SOCH:
# Q1: CancelledError ko except karke re-raise kyon zaroori hai?
#     (Bina re-raise ke cancellation propagate nahi hoti — task "complete" dikhti hai)
# Q2: task.cancel() call karne ke baad immediately cancelled hoti hai?
#     (Nahi — next await point pe CancelledError raise hoti hai)
