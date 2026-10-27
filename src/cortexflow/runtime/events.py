"""Flow control signals and wait event for suspension."""

from __future__ import annotations


class WaitEvent(Exception):
    """Raised when a node needs to suspend the flow and wait for an event."""

    def __init__(self, event_type: str, filter: dict | None = None):
        self.event_type = event_type
        self.filter = filter
        super().__init__(f"Waiting for event: {event_type}")


class LoopBreak(Exception):
    """Raised by a `break` node to exit the enclosing loop immediately."""

    def __init__(self, node_id: str = ""):
        self.node_id = node_id
        super().__init__(
            f"Loop break at node '{node_id}'"
            if node_id else "Loop break outside of a loop body"
        )


class LoopContinue(Exception):
    """Raised by a `continue` node to skip to the next loop iteration."""

    def __init__(self, node_id: str = ""):
        self.node_id = node_id
        super().__init__(
            f"Loop continue at node '{node_id}'"
            if node_id else "Loop continue outside of a loop body"
        )


class AskQuestion(WaitEvent):
    """Raised by an `ask` node to suspend the flow with a user question.

    Carries the rendered question and the variable that should receive
    the answer on resume. Handled exactly like :class:`WaitEvent` by the
    executor; the API layer turns it into a 202 suspended response.
    """

    def __init__(self, question: str, answer_var: str = "answer",
                 node_id: str = ""):
        self.question = question
        self.answer_var = answer_var or "answer"
        self.node_id = node_id
        super().__init__("ask", {"question": question, "node_id": node_id})
