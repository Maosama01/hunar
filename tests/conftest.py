from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hunar.accounts import auth
from hunar.api import db, services
from hunar.schemas import QualificationPack

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def stub_qp() -> QualificationPack:
    return QualificationPack.model_validate_json((FIXTURES / "stub_qp.json").read_text())


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HUNAR_DB", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("HUNAR_MAPPER", "tfidf")
    monkeypatch.setattr(services, "UPLOADS", tmp_path / "uploads")
    monkeypatch.setattr("hunar.api.services.DATA", tmp_path)
    monkeypatch.setattr("hunar.api.main.DATA", tmp_path)
    monkeypatch.setenv("HUNAR_PIN_PEPPER", "test-pepper")
    monkeypatch.delenv("HUNAR_OTP_PROVIDER", raising=False)
    auth._pepper.cache_clear()
    db.reset_engine()
    services._load_mapper.cache_clear()
    from hunar.api.main import app

    with TestClient(app) as c:
        # Assessor-side endpoints need a staff login; the default client is an assessor.
        c.headers["Authorization"] = f"Bearer {make_account(role='assessor', phone='9000000001')[1]}"
        yield c
    db.reset_engine()
    services._load_mapper.cache_clear()
    auth._pepper.cache_clear()


def make_account(role: str, phone: str, name: str = "Test", pin: str = "482913") -> tuple[str, str]:
    """Create an account directly (staff accounts cannot self-register) and return (id, bearer token)."""
    from sqlmodel import Session

    from hunar.accounts.models import Account
    from hunar.accounts.routes import record_consent

    with Session(db.engine()) as s:
        acc = Account(phone=auth.normalise_phone(phone), pin_hash=auth.hash_pin(pin), role=role, display_name=name)
        s.add(acc)
        s.flush()
        record_consent(s, acc, "account", True)
        s.commit()
        s.refresh(acc)
        return acc.id, auth.new_session(s, acc)
