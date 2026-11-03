"""SQLite database (data/hunar.db by default; HUNAR_DB overrides, e.g. for tests)."""
from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine, text

from hunar.paths import DATA

_engine = None

# The audit table is append-only at the database level too.
AUDIT_TRIGGERS = [
    """CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON auditentry
       BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END""",
    """CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON auditentry
       BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END""",
]


def db_url() -> str:
    return os.environ.get("HUNAR_DB", f"sqlite:///{DATA / 'hunar.db'}")


def engine():
    global _engine
    if _engine is None:
        _engine = create_engine(db_url(), connect_args={"check_same_thread": False})

        @event.listens_for(_engine, "connect")
        def _fk_on(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return _engine


def reset_engine() -> None:
    global _engine
    _engine = None


def init_db() -> None:
    from hunar.accounts import models as _accounts  # noqa: F401  (register tables)
    from hunar.api import models  # noqa: F401
    from hunar.api.services import index_phashes
    from hunar.market import models as _market  # noqa: F401
    from hunar.quiz import models as _quiz  # noqa: F401

    SQLModel.metadata.create_all(engine())
    with Session(engine()) as s:
        for t in AUDIT_TRIGGERS:
            s.exec(text(t))
        s.commit()
        index_phashes(s)  # photos stored before the reuse index existed


def get_session() -> Iterator[Session]:
    with Session(engine()) as s:
        yield s
