from typing import Any
from supabase import Client


def log_audit(
    db: Client,
    user_id: str,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """Best-effort audit trail write — must never break the calling operation."""
    try:
        db.from_("audit_log").insert({
            "user_id": user_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "meta": meta,
        }).execute()
    except Exception:
        pass
