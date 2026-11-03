from pathlib import Path

import pytest
from fastapi.testclient import TestClient

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
    db.reset_engine()
    services.mapper.cache_clear()
    from hunar.api.main import app

    with TestClient(app) as c:
        yield c
    db.reset_engine()
    services.mapper.cache_clear()
