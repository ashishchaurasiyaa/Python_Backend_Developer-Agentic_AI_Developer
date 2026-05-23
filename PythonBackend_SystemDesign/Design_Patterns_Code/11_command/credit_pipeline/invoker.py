"""
Invoker — the heart of the Command pattern.

PipelineInvoker receives Command objects, executes them, and maintains
a history stack so that any command can be undone in LIFO order.

In a production system (like Youngman's ERP), the invoker would be
backed by a persistent store (Redis, DB). Here we use a module-level
singleton for simplicity across Django request/response cycles.
"""


class PipelineInvoker:
    """
    Executes commands and keeps an undo stack.

    Usage:
        invoker = get_invoker()
        result = invoker.execute(some_command)
        undo_result = invoker.undo_last()
    """

    def __init__(self):
        self._history: list = []

    def execute(self, command) -> dict:
        """Execute a command and push it onto the history stack on success."""
        result = command.execute()
        if result.get('success'):
            self._history.append(command)
        return result

    def undo_last(self) -> dict:
        """Pop the most recent command and call its undo()."""
        if not self._history:
            return {'success': False, 'error': 'Nothing to undo — history is empty'}
        command = self._history.pop()
        return command.undo()

    def get_history_count(self) -> int:
        """Number of undoable commands in the stack."""
        return len(self._history)

    def get_history(self) -> list:
        """List of command names in execution order."""
        return [cmd.get_name() for cmd in self._history]

    def clear_history(self):
        """Clear the entire undo stack."""
        self._history.clear()


# ── Module-level singleton ───────────────────────────────────
# This ensures the invoker (and its undo history) persists across
# Django request/response cycles within the same process.
_invoker_instance = None


def get_invoker() -> PipelineInvoker:
    """Return the module-level PipelineInvoker singleton."""
    global _invoker_instance
    if _invoker_instance is None:
        _invoker_instance = PipelineInvoker()
    return _invoker_instance
