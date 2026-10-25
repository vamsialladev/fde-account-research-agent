"""'Share this brief': a read-only link with the brief (and any chat about it) inside the URL. Nothing is stored.

The brief's Markdown and the chat turns are JSON, zlib-compressed and base64url-encoded into `?share=...`. Personal
data is removed first with the same redaction as everything else (research/pii.py). Opening a link only decodes and
shows it; it never searches the web or calls the model.
"""

import base64
import binascii
import json
import zlib

from research.pii import scrub_text

VERSION = 1
MAX_TOKEN = 12_000
MAX_TURNS = 6


def make_token(company: str, markdown: str, turns: list[dict]) -> str | None:
    """None when even the brief alone is too long for a link."""
    chat = [{"q": scrub_text(t["question"])[:600], "a": scrub_text(t["answer"])[:1500]} for t in turns][-MAX_TURNS:]
    while True:
        raw = json.dumps({"v": VERSION, "c": company[:120], "b": markdown, "t": chat}, ensure_ascii=False).encode()
        token = base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode("ascii").rstrip("=")
        if len(token) <= MAX_TOKEN:
            return token
        if not chat:
            return None
        chat = chat[1:]


def decode(token: str) -> dict | None:
    if not token or len(token) > MAX_TOKEN:
        return None
    try:
        raw = zlib.decompressobj().decompress(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)), 400_000)
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, binascii.Error, zlib.error, UnicodeDecodeError):
        return None
    if not isinstance(data, dict) or data.get("v") != VERSION or not isinstance(data.get("b"), str):
        return None
    turns = [t for t in data.get("t", []) if isinstance(t, dict) and isinstance(t.get("q"), str)][:MAX_TURNS]
    return {"company": str(data.get("c", ""))[:120], "brief": data["b"][:60_000], "turns": turns}


def share_url(base_url: str, token: str) -> str:
    base = (base_url or "").split("?", 1)[0].split("#", 1)[0]
    return f"{base}?share={token}"
