"""
API endpoints for managing credentials stored in the database.
GET  /api/credentials        — list all (values masked)
PUT  /api/credentials/{key}  — set a credential
DELETE /api/credentials/{key} — remove a credential
POST /api/credentials/test   — test an API key (e.g. Anthropic)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from credential_store import (
    list_credentials,
    set_credential,
    delete_credential,
    get_credential,
    KNOWN_CREDENTIALS,
)
from logger import log

router = APIRouter()


class CredentialUpdate(BaseModel):
    value: str
    label: str = ""


@router.get("/")
async def get_credentials():
    """List all credentials with masked values, plus known definitions."""
    stored = list_credentials()
    stored_keys = {c["key"] for c in stored}
    # Merge in known credentials that aren't yet stored
    result = list(stored)
    for known in KNOWN_CREDENTIALS:
        if known["key"] not in stored_keys:
            result.append({
                "key": known["key"],
                "label": known["label"],
                "hint": "",
                "updated_at": None,
                "has_value": False,
                "group": known.get("group", ""),
            })
    # Add group info to stored credentials
    known_map = {k["key"]: k for k in KNOWN_CREDENTIALS}
    for item in result:
        if "group" not in item and item["key"] in known_map:
            item["group"] = known_map[item["key"]].get("group", "Other")
        elif "group" not in item:
            item["group"] = "Other"
    return {"credentials": result}


@router.put("/{key}")
async def update_credential(key: str, body: CredentialUpdate):
    """Set or update a credential."""
    if not body.value.strip():
        raise HTTPException(400, "Value cannot be empty")
    ok = set_credential(key, body.value.strip(), label=body.label)
    if not ok:
        raise HTTPException(500, "Failed to save credential")
    return {"ok": True, "key": key}


@router.delete("/{key}")
async def remove_credential(key: str):
    """Delete a credential (reverts to .env fallback)."""
    ok = delete_credential(key)
    if not ok:
        raise HTTPException(500, "Failed to delete credential")
    return {"ok": True, "key": key}


class TestRequest(BaseModel):
    key: str


@router.post("/test")
async def test_credential(body: TestRequest):
    """Test whether a credential works (currently supports Anthropic and OpenAI)."""
    key = body.key
    value = get_credential(key, fallback="")
    if not value:
        return {"ok": False, "error": "No value set for this credential"}

    if key == "anthropic_api_key":
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=value)
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                messages=[{"role": "user", "content": "Say 'ok'"}],
                max_tokens=5,
            )
            return {"ok": True, "detail": f"Connected — model responded"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    elif key == "openai_api_key":
        try:
            from openai import OpenAI
            client = OpenAI(api_key=value)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Say 'ok'"}],
                max_tokens=5,
            )
            return {"ok": True, "detail": "Connected — model responded"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    elif key == "voyage_api_key":
        try:
            import voyageai
            client = voyageai.Client(api_key=value)
            result = client.embed(["test"], model="voyage-3-lite")
            return {"ok": True, "detail": f"Connected — embedding dim={len(result.embeddings[0])}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    return {"ok": False, "error": f"No test implemented for '{key}'"}
