"""Append-only, hash-chained audit log.

Each entry stores the SHA-256 of the previous entry, so editing or deleting any past entry
breaks every hash after it and `verify` finds the first broken link. SQLite triggers also
refuse UPDATE and DELETE on the table.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json

from sqlmodel import Session, select

from hunar.api.models import AuditEntry

GENESIS = "0" * 64


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def entry_hash(seq: int, ts: str, actor: str, action: str, subject: str, payload_json: str, prev_hash: str) -> str:
    body = canonical({"seq": seq, "ts": ts, "actor": actor, "action": action, "subject": subject,
                      "payload": payload_json, "prev": prev_hash})
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def append(session: Session, actor: str, action: str, subject: str, payload: dict | None = None,
           commit: bool = True) -> AuditEntry:
    last = session.exec(select(AuditEntry).order_by(AuditEntry.seq.desc()).limit(1)).first()
    seq = (last.seq if last else 0) + 1
    prev = last.hash if last else GENESIS
    ts = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    pj = canonical(payload or {})
    e = AuditEntry(seq=seq, ts=ts, actor=actor, action=action, subject=subject, payload_json=pj, prev_hash=prev,
                   hash=entry_hash(seq, ts, actor, action, subject, pj, prev))
    session.add(e)
    if commit:
        session.commit()
    return e


def verify(session: Session) -> dict:
    prev, n = GENESIS, 0
    for e in session.exec(select(AuditEntry).order_by(AuditEntry.seq)):
        n += 1
        expected = entry_hash(e.seq, e.ts, e.actor, e.action, e.subject, e.payload_json, prev)
        if e.prev_hash != prev or e.hash != expected or e.seq != n:
            return {"ok": False, "entries": n, "first_bad_seq": e.seq}
        prev = e.hash
    return {"ok": True, "entries": n, "head": prev}
