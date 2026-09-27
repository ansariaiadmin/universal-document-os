"""Shared pytest fixtures — isolate tests from the real ./data directory."""
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Point all app data paths (uploads/outputs/workrooms/audit) at a temp dir.

    Tests never touch or pollute the repository's real data/ folder, and each
    test starts with clean directories.
    """
    import app.config as config
    import app.main as main

    data = tmp_path / "data"
    uploads = data / "uploads"
    outputs = data / "outputs"
    workrooms = data / "workrooms"
    for d in (uploads, outputs, workrooms):
        d.mkdir(parents=True, exist_ok=True)
    audit_file = data / "audit.jsonl"

    monkeypatch.setattr(config, "DATA", data, raising=False)
    monkeypatch.setattr(config, "UPLOADS", uploads, raising=False)
    monkeypatch.setattr(config, "OUTPUTS", outputs, raising=False)
    monkeypatch.setattr(config, "WORKROOMS", workrooms, raising=False)
    monkeypatch.setattr(config, "AUDIT_FILE", audit_file, raising=False)
    monkeypatch.setattr(main, "UPLOADS", uploads)
    monkeypatch.setattr(main, "OUTPUTS", outputs)
    monkeypatch.setattr(main, "WORKROOMS", workrooms)
    monkeypatch.setattr(main, "AUDIT_FILE", audit_file)
    yield data


@pytest.fixture
def data_tree():
    """Convenience: return the module-level path constants for direct assertions."""
    import app.main as main

    return {
        "uploads": main.UPLOADS,
        "outputs": main.OUTPUTS,
        "workrooms": main.WORKROOMS,
        "audit": main.AUDIT_FILE,
    }
