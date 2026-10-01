import os
import time

import pytest

from doctrace.config import ConfigError, load_settings
from doctrace.indexer import IngestError, IngestLock, run_ingest
from doctrace.search import SearchEngine


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def quiet(_msg):
    pass


def ingest(cfg, **kw):
    return run_ingest(cfg, log=quiet, show_progress=False, **kw)


@pytest.fixture
def notes(cfg):
    write(cfg.data_dir / "Sem 3" / "DBMS" / "normal forms.md",
          "Third normal form removes transitive dependencies between attributes.")
    write(cfg.data_dir / "Sem 3" / "OS" / "deadlock.txt",
          "Coffman conditions: mutual exclusion, hold and wait, no preemption, circular wait.")
    write(cfg.data_dir / "Sem 4" / "CN" / "tcp.txt",
          "TCP is a reliable connection oriented transport protocol.")
    (cfg.data_dir / "Sem 4" / "broken.pdf").write_bytes(b"%PDF-1.4 not really a pdf")
    (cfg.data_dir / "old.doc").write_bytes(b"legacy format")
    return cfg


def test_ingest_and_search(notes):
    summary = ingest(notes)
    assert summary.files == 3
    assert summary.chunks == 3
    assert [p for p, _ in summary.failed] == ["Sem 4/broken.pdf"]

    engine = SearchEngine(notes, log=quiet)
    files, _ = engine.search("coffman deadlock conditions", k=3)
    assert files[0].path == "Sem 3/OS/deadlock.txt"
    assert files[0].best.keyword
    assert os.path.isabs(files[0].uri)

    only_sem4, _ = engine.search("conditions protocol", k=5, folder="Sem 4")
    assert only_sem4 and all(f.path.startswith("Sem 4/") for f in only_sem4)
    assert "Sem 3/DBMS" in engine.folders()
    assert engine.store.problem_files()[0][:2] == ("Sem 4/broken.pdf", "error")


def test_incremental_update(notes):
    ingest(notes)
    time.sleep(0.05)
    write(notes.data_dir / "Sem 4" / "CN" / "tcp.txt", "UDP is connectionless and unreliable.")
    (notes.data_dir / "Sem 3" / "OS" / "deadlock.txt").unlink()
    write(notes.data_dir / "Sem 5" / "new.md", "Dijkstra shortest path uses a priority queue.")

    summary = ingest(notes)
    assert summary.changed_files == 2
    assert summary.removed_files == 1
    assert summary.files == 3

    engine = SearchEngine(notes, log=quiet)
    assert engine.search("dijkstra", k=1)[0][0].path == "Sem 5/new.md"
    paths = [f.path for f in engine.search("coffman deadlock", k=5)[0]]
    assert "Sem 3/OS/deadlock.txt" not in paths

    # nothing changed -> nothing re-processed
    assert ingest(notes).changed_files == 0


def test_engine_reload_after_ingest(notes):
    engine = SearchEngine(notes, log=quiet)
    assert not engine.ready
    assert engine.search("anything") == ([], [])
    ingest(notes)
    engine.reload()
    assert engine.ready
    assert engine.search("tcp protocol", k=1)[0][0].path == "Sem 4/CN/tcp.txt"


def test_rebuild(notes):
    ingest(notes)
    assert ingest(notes, rebuild=True).changed_files == 4


def test_missing_data_dir(cfg, tmp_path):
    cfg.data_dir = tmp_path / "nope"
    with pytest.raises(IngestError):
        ingest(cfg)


def test_lock_blocks_second_ingest(cfg):
    with IngestLock(cfg.index_dir), pytest.raises(IngestError):
        ingest(cfg)


def test_stale_lock_is_ignored(cfg):
    cfg.index_dir.mkdir(parents=True, exist_ok=True)
    (cfg.index_dir / "ingest.lock").write_text("999999999")
    assert ingest(cfg).files == 0


def test_bad_config(monkeypatch):
    monkeypatch.setenv("DOCTRACE_CHUNK_SIZE", "big")
    with pytest.raises(ConfigError):
        load_settings()
    monkeypatch.setenv("DOCTRACE_CHUNK_SIZE", "1000")
    monkeypatch.setenv("DOCTRACE_LLM", "gpt")
    with pytest.raises(ConfigError):
        load_settings()


def test_gdrive_ingest(cfg, monkeypatch):
    import doctrace.gdrive
    from doctrace.gdrive import DriveFile
    from doctrace.store import FileRecord

    contents = {"f1": b"Kirchhoff voltage law sums to zero around a loop.",
                "f2": b"Ohm law relates voltage current and resistance."}

    class FakeDrive:
        def __init__(self, _credentials):
            pass

        def scan(self, _folder_id, _max_mb):
            return [
                DriveFile(FileRecord("gdrive", f"Circuits/{fid}.txt", f"v-{fid}",
                                     f"https://drive.google.com/file/d/{fid}/view"), fid, "text/plain", ".txt")
                for fid in contents
            ]

        def download(self, f):
            return contents[f.file_id]

    monkeypatch.setattr(doctrace.gdrive, "Drive", FakeDrive)
    cfg.gdrive_folder_id = "folder"
    summary = ingest(cfg, local_source=False, gdrive=True)
    assert summary.files == 2 and summary.changed_files == 2

    engine = SearchEngine(cfg, log=quiet)
    top = engine.search("kirchhoff loop", k=1)[0][0]
    assert top.path == "Circuits/f1.txt" and top.uri.startswith("https://")

    # unchanged Drive files are not downloaded again
    assert ingest(cfg, local_source=False, gdrive=True).changed_files == 0
