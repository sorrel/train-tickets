from core.storage import load_record, save_day


def test_load_record_missing_file_returns_empty(tmp_path):
    assert load_record(tmp_path / "nope.json") == {}


def test_save_day_creates_file_and_parent(tmp_path):
    path = tmp_path / "deep" / "prices.json"
    save_day(path, "2026-08-12", {"trains": [], "checked_at": "2026-06-06T10:00:00"})
    record = load_record(path)
    assert "2026-08-12" in record
    assert record["2026-08-12"]["checked_at"] == "2026-06-06T10:00:00"


def test_save_day_merges_without_clobbering(tmp_path):
    path = tmp_path / "prices.json"
    save_day(path, "2026-08-12", {"trains": [1]})
    save_day(path, "2026-08-13", {"trains": [2]})
    record = load_record(path)
    assert set(record) == {"2026-08-12", "2026-08-13"}
