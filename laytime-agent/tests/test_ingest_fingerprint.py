from laytime_agent import config, ingest


def configure_sources(monkeypatch, tmp_path):
    cases = tmp_path / "cases"
    shared = tmp_path / "shared"
    store = tmp_path / "storage"
    (cases / "case_one").mkdir(parents=True)
    shared.mkdir()
    monkeypatch.setattr(config, "CASES_DIR", cases)
    monkeypatch.setattr(config, "SHARED_DIR", shared)
    monkeypatch.setattr(config, "STORE_DIR", store)
    return cases, shared


def test_sources_changed_until_current_inputs_are_recorded(monkeypatch, tmp_path):
    cases, _ = configure_sources(monkeypatch, tmp_path)
    document = cases / "case_one" / "charter_party.pdf"
    document.write_bytes(b"version one")

    assert ingest.sources_changed()
    ingest._record_indexed_sources()
    assert not ingest.sources_changed()

    document.write_bytes(b"version two")
    assert ingest.sources_changed()


def test_new_case_file_requires_rebuild(monkeypatch, tmp_path):
    cases, _ = configure_sources(monkeypatch, tmp_path)
    (cases / "case_one" / "charter_party.pdf").write_bytes(b"contract")
    ingest._record_indexed_sources()

    (cases / "case_one" / "statement_of_facts.pdf").write_bytes(b"facts")

    assert ingest.sources_changed()


def test_only_ingested_shared_files_trigger_rebuild(monkeypatch, tmp_path):
    _, shared = configure_sources(monkeypatch, tmp_path)
    (shared / "port_information.json").write_text("{}", encoding="utf-8")
    ingest._record_indexed_sources()

    (shared / "demurrage_claim_letter_template.md").write_text("template", encoding="utf-8")
    assert not ingest.sources_changed()

    (shared / "port_information.json").write_text('{"Port A": {}}', encoding="utf-8")
    assert ingest.sources_changed()