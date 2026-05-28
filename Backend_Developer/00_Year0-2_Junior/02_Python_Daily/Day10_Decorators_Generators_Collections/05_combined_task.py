# Task Manager:
# Task(title, priority, status) — namedtuple ya dataclass
# TaskManager:
#   add_task(task)
#   complete_task(title)
#   get_by_priority() → heapq use karo
#   pending_tasks() → generator
#   __len__, __iter__, __contains__


from dataclasses import dataclass
import heapq

@dataclass
class Task:
    title: str
    priority: int
    status: str = "pending"

class TaskManager:
    def __init__(self):
        self._tasks = []

    def add_task(self, task):
        self._tasks.append(task)
        print(f"Added: '{task.title}' (P{task.priority})")

    def complete_task(self, title):
        for task in self._tasks:
            if task.title == title:
                task.status = "completed"
                print(f"Completed: '{task.title}'")
                return
        print(f"Task '{title}' not found")

    def get_by_priority(self):
        heap = [(t.priority, t.title, t)
                for t in self._tasks
                if t.status == "pending"]
        heapq.heapify(heap)
        result = []
        while heap:
            _, _, task = heapq.heappop(heap)
            result.append(task)
        return result

    def pending_tasks(self):
        for task in self._tasks:
            if task.status == "pending":
                yield task

    def __len__(self):
        return len(self._tasks)

    def __iter__(self):
        return iter(self._tasks)

    def __contains__(self, title):
        return any(t.title == title for t in self._tasks)

    def __repr__(self):
        return f"TaskManager({len(self._tasks)} tasks)"


tm = TaskManager()
tm.add_task(Task("Task 1", 1))
tm.add_task(Task("Task 2", 2))
tm.add_task(Task("Task 3", 3))
tm.add_task(Task("Task 4", 4))
tm.add_task(Task("Task 5", 5))

print(tm)
print(tm.get_by_priority())
tm.complete_task("Task 2")
for task in tm.pending_tasks():
    print(f"  ⏳ {task.title}")
print(tm.get_by_priority())




