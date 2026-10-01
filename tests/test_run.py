from doctrace.indexer import run_ingest
from run import find_changes, update_index


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def ingest(cfg):
    return run_ingest(cfg, log=lambda _m: None, show_progress=False)


def test_find_changes(cfg):
    write(cfg.data_dir / "a" / "one.txt", "first file about tcp")
    write(cfg.data_dir / "two.md", "second file about udp")
    first = find_changes(cfg)
    assert first.needed and first.indexed == 0
    assert first.new == ["a/one.txt", "two.md"]

    ingest(cfg)
    assert not find_changes(cfg).needed

    write(cfg.data_dir / "a" / "one.txt", "first file, now about routing")
    (cfg.data_dir / "two.md").unlink()
    write(cfg.data_dir / "three.txt", "third file")
    c = find_changes(cfg)
    assert (c.new, c.changed, c.removed) == (["three.txt"], ["a/one.txt"], ["two.md"])


def test_model_change_forces_rebuild(cfg):
    write(cfg.data_dir / "one.txt", "some text")
    ingest(cfg)
    cfg.embed_model = "another-model"
    assert "search model changed" in find_changes(cfg).reason


def test_update_index_messages(cfg, capsys):
    write(cfg.data_dir / "one.txt", "some text about deadlock")
    update_index(cfg)
    out = capsys.readouterr().out
    assert "First-time indexing: 1 files" in out and "[OK] Index updated" in out

    update_index(cfg)
    assert "No new data: all 1 files are already indexed" in capsys.readouterr().out


def test_missing_data_dir_still_starts(cfg, tmp_path, capsys):
    cfg.data_dir = tmp_path / "nope"
    update_index(cfg)
    assert "does not exist" in capsys.readouterr().out
