from pathlib import Path

import pytest

from laytime_agent.uploads import stage_case_uploads

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_CASE = ROOT / "data" / "cases" / "case_A_coral_meridian"


def required_documents():
    return [
        (name, (SAMPLE_CASE / name).read_bytes())
        for name in ("charter_party.pdf", "statement_of_facts.pdf", "notice_of_readiness.pdf")
    ]


def test_stage_new_case_with_required_documents(tmp_path):
    result = stage_case_uploads(tmp_path, "claim_001", required_documents(), create_case=True)

    assert result["files"] == 3
    assert {"charter_party", "sof", "nor"}.issubset(result["types"])
    assert (tmp_path / "claim_001" / "statement_of_facts.pdf").is_file()


def test_new_case_requires_charter_party_sof_and_nor(tmp_path):
    with pytest.raises(ValueError, match="new case needs a PDF"):
        stage_case_uploads(tmp_path, "claim_001", required_documents()[:1], create_case=True)

    assert not (tmp_path / "claim_001").exists()


def test_existing_case_upload_rejects_duplicate_name(tmp_path):
    case_dir = tmp_path / "case_a"
    case_dir.mkdir()
    (case_dir / "notice.pdf").write_bytes(b"already here")

    with pytest.raises(ValueError, match="already exists"):
        stage_case_uploads(tmp_path, "case_a", [("notice.pdf", b"replacement")])

    assert (case_dir / "notice.pdf").read_bytes() == b"already here"


@pytest.mark.parametrize("name", ["../escape.pdf", "bad.exe"])
def test_rejects_unsafe_or_unsupported_upload_names(tmp_path, name):
    case_dir = tmp_path / "case_a"
    case_dir.mkdir()

    with pytest.raises(ValueError):
        stage_case_uploads(tmp_path, "case_a", [(name, b"content")])

    assert list(case_dir.iterdir()) == []