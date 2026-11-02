from sqlalchemy import text

from app.db import engine
from app.errors import AppError

# BR4: the only legal moves; COMPLETED and FAILED are final
ALLOWED = {
    "PENDING": {"CHARGED", "FAILED"},
    "CHARGED": {"COMPLETED"},
    "COMPLETED": set(),
    "FAILED": set(),
}


class InvalidTransition(AppError):
    # Raised when a crossing is asked to make an illegal status change
    def __init__(self, new_status: str):
        super().__init__(409, "INVALID_STATE_TRANSITION", f"Crossing cannot move to {new_status} from its current status")


def transition(crossing_id: int, new_status: str, reason: str | None = None) -> None:
    # Atomically change status only if the current status allows it, and record the history row
    allowed_from = [s for s, nxt in ALLOWED.items() if new_status in nxt]
    if not allowed_from:
        raise InvalidTransition(new_status)
    params = {f"s{i}": s for i, s in enumerate(allowed_from)}
    marks = ", ".join(f":s{i}" for i in range(len(allowed_from)))
    with engine.begin() as conn:
        res = conn.execute(  # conditional UPDATE so two racing callers cannot both move the crossing
            text(f"UPDATE crossings SET status = :new, failure_reason = :reason WHERE id = :id AND status IN ({marks})"),
            {"new": new_status, "reason": reason, "id": crossing_id, **params},
        )
        if res.rowcount == 0:
            raise InvalidTransition(new_status)
        conn.execute(
            text("INSERT INTO crossing_status_history (crossing_id, status, reason) VALUES (:c, :s, :r)"),
            {"c": crossing_id, "s": new_status, "r": reason},
        )