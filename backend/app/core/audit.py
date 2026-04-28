import asyncio
from app.core.db import get_db


def log_audit(
    team_id: str,
    actor: str,
    action: str,
    resource: str,
    metadata: dict | None = None,
) -> None:
    asyncio.create_task(_write_audit(team_id, actor, action, resource, metadata or {}))


async def _write_audit(
    team_id: str, actor: str, action: str, resource: str, metadata: dict
) -> None:
    try:
        db = get_db()
        db.table("audit_log").insert(
            {
                "team_id": team_id,
                "actor": actor,
                "action": action,
                "resource": resource,
                "metadata": metadata,
            }
        ).execute()
    except Exception:
        pass
