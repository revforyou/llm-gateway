from fastapi import APIRouter, Depends, HTTPException, status
from app.core.auth import verify_api_key_dep
from app.core.security import generate_api_key
from app.core.db import get_db
from app.core.audit import log_audit
from app.models.schemas import CreateKeyRequest, CreateKeyResponse, KeyListItem, ApiResponse

router = APIRouter(prefix="/v1/keys", tags=["keys"])


@router.post("", response_model=ApiResponse)
async def create_key(
    body: CreateKeyRequest,
    auth: dict = Depends(verify_api_key_dep),
) -> ApiResponse:
    plaintext, prefix, hashed = generate_api_key()
    db = get_db()
    result = (
        db.table("api_keys")
        .insert({
            "team_id": auth["team_id"],
            "name": body.name,
            "key_hash": hashed,
            "key_prefix": prefix,
        })
        .execute()
    )
    row = result.data[0]
    log_audit(auth["team_id"], auth["key_id"], "create_key", f"api_keys/{row['id']}")
    return ApiResponse(data=CreateKeyResponse(
        id=row["id"],
        name=row["name"],
        key=plaintext,
        prefix=prefix,
        created_at=row["created_at"],
    ))


@router.get("", response_model=ApiResponse)
async def list_keys(auth: dict = Depends(verify_api_key_dep)) -> ApiResponse:
    db = get_db()
    result = (
        db.table("api_keys")
        .select("id, name, key_prefix, last_used_at, created_at")
        .eq("team_id", auth["team_id"])
        .is_("revoked_at", "null")
        .order("created_at", desc=True)
        .execute()
    )
    keys = [
        KeyListItem(
            id=r["id"],
            name=r["name"],
            prefix=r["key_prefix"],
            last_used_at=r.get("last_used_at"),
            created_at=r["created_at"],
        )
        for r in result.data
    ]
    return ApiResponse(data=keys)


@router.delete("/{key_id}", response_model=ApiResponse)
async def revoke_key(key_id: str, auth: dict = Depends(verify_api_key_dep)) -> ApiResponse:
    db = get_db()
    result = (
        db.table("api_keys")
        .select("id, team_id")
        .eq("id", key_id)
        .single()
        .execute()
    )
    if not result.data or result.data["team_id"] != auth["team_id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found")
    db.table("api_keys").update({"revoked_at": "now()"}).eq("id", key_id).execute()
    log_audit(auth["team_id"], auth["key_id"], "revoke_key", f"api_keys/{key_id}")
    return ApiResponse(data={"revoked": True})
