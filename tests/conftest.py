from pathlib import Path

import pytest

from hunar.schemas import QualificationPack

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def stub_qp() -> QualificationPack:
    return QualificationPack.model_validate_json((FIXTURES / "stub_qp.json").read_text())
