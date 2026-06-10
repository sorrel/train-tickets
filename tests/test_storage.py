from core.storage import (
    load_record, save_day, remove_day, write_meta, updated_horizon,
    clear_day_direction, META_KEY,
)
from core.directions import morning_direction, evening_direction
from types import SimpleNamespace


def _both_cfg():
    return SimpleNamespace(
        origin_nlc="5230", origin_name="TW", destination_nlc="1072",
        destination_name="LDN", window_start="05:55", window_end="08:05",
        evening_window_start="17:45", evening_window_end="19:15")


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


def test_remove_day_drops_entry(tmp_path):
    path = tmp_path / "prices.json"
    save_day(path, "2026-08-12", {"trains": [1]})
    remove_day(path, "2026-08-12")
    assert load_record(path) == {}


def test_remove_day_missing_is_noop(tmp_path):
    path = tmp_path / "prices.json"
    save_day(path, "2026-08-12", {"trains": [1]})
    remove_day(path, "2026-08-13")   # not present
    assert set(load_record(path)) == {"2026-08-12"}


def test_clear_day_direction_keeps_day_when_other_direction_has_trains(tmp_path):
    path = tmp_path / "prices.json"
    save_day(path, "2026-08-12", {
        "checked_at": "2026-06-06T10:00:00", "trains": [{"depart": "06:05"}],
        "evening_checked_at": "2026-06-06T10:00:00",
        "evening_trains": [{"depart": "18:00"}],
        "evening_price_history": [{"checked_at": "x", "cheapest_pence": 1}],
    })
    clear_day_direction(path, "2026-08-12", evening_direction(_both_cfg()), "trains")
    day = load_record(path)["2026-08-12"]
    assert "evening_trains" not in day and "evening_checked_at" not in day
    assert "evening_price_history" not in day
    assert day["trains"] == [{"depart": "06:05"}]   # morning untouched


def test_clear_day_direction_removes_date_when_no_other_trains(tmp_path):
    path = tmp_path / "prices.json"
    save_day(path, "2026-08-12", {
        "evening_checked_at": "2026-06-06T10:00:00",
        "evening_trains": [{"depart": "18:00"}],
    })
    clear_day_direction(path, "2026-08-12", evening_direction(_both_cfg()), "trains")
    assert "2026-08-12" not in load_record(path)


def test_clear_day_direction_missing_day_is_noop(tmp_path):
    path = tmp_path / "prices.json"
    save_day(path, "2026-08-12", {"trains": [1]})
    clear_day_direction(path, "2026-09-01", morning_direction(_both_cfg()), "evening_trains")
    assert set(load_record(path)) == {"2026-08-12"}


def test_write_meta_sets_and_clears(tmp_path):
    path = tmp_path / "prices.json"
    save_day(path, "2026-08-12", {"trains": [1]})
    write_meta(path, {"no_trains_from": "2026-09-15", "checked_at": "2026-06-06T10:00:00"})
    assert load_record(path)[META_KEY]["no_trains_from"] == "2026-09-15"
    write_meta(path, None)
    assert META_KEY not in load_record(path)
    assert "2026-08-12" in load_record(path)   # days untouched


# --- updated_horizon (pure) ------------------------------------------------

def test_horizon_set_when_first_no_trains_seen():
    meta = updated_horizon(None, [], ["2026-09-15", "2026-09-16"], "2026-06-06T10:00:00")
    assert meta == {"no_trains_from": "2026-09-15", "checked_at": "2026-06-06T10:00:00"}


def test_horizon_none_when_all_dates_have_trains():
    assert updated_horizon(None, ["2026-08-12"], [], "2026-06-06T10:00:00") is None


def test_horizon_refreshes_check_date_when_boundary_week_rechecked():
    current = {"no_trains_from": "2026-09-15", "checked_at": "2026-06-01T09:00:00"}
    # Re-checking the boundary week itself still finds no trains — the horizon
    # is unchanged, but we have freshly confirmed it, so the check date updates.
    meta = updated_horizon(current, [], ["2026-09-15"], "2026-06-06T10:00:00")
    assert meta == {"no_trains_from": "2026-09-15", "checked_at": "2026-06-06T10:00:00"}


def test_horizon_keeps_check_date_when_only_further_weeks_checked():
    current = {"no_trains_from": "2026-09-15", "checked_at": "2026-06-01T09:00:00"}
    # A week further ahead than the horizon is checked (still no trains). The
    # boundary date itself was not re-checked, so its discovery date stands.
    meta = updated_horizon(current, [], ["2026-10-06"], "2026-06-06T10:00:00")
    assert meta == {"no_trains_from": "2026-09-15", "checked_at": "2026-06-01T09:00:00"}


def test_horizon_advances_earlier_with_new_check_date():
    current = {"no_trains_from": "2026-09-15", "checked_at": "2026-06-01T09:00:00"}
    meta = updated_horizon(current, [], ["2026-09-08"], "2026-06-06T10:00:00")
    assert meta == {"no_trains_from": "2026-09-08", "checked_at": "2026-06-06T10:00:00"}


def test_horizon_cleared_when_trains_appear_at_or_after_it():
    current = {"no_trains_from": "2026-09-15", "checked_at": "2026-06-01T09:00:00"}
    # Trains now found on 2026-09-15 → old horizon gone; no new no-train dates.
    assert updated_horizon(current, ["2026-09-15"], [], "2026-06-06T10:00:00") is None


def test_horizon_moves_forward_when_boundary_recedes():
    current = {"no_trains_from": "2026-09-15", "checked_at": "2026-06-01T09:00:00"}
    # Tue now has trains (clears 15th), but Thu 17th still has none → new horizon.
    meta = updated_horizon(current, ["2026-09-15"], ["2026-09-17"], "2026-06-06T10:00:00")
    assert meta == {"no_trains_from": "2026-09-17", "checked_at": "2026-06-06T10:00:00"}
