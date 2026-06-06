from core.fares import TrainOption
from commands.record import day_payload


def test_day_payload_serialises_trains():
    options = [TrainOption("06:40", "07:30", 1640, True, "/b")]
    payload = day_payload(options, checked_at="2026-06-06T10:00:00")
    assert payload["checked_at"] == "2026-06-06T10:00:00"
    assert payload["trains"] == [
        {"depart": "06:40", "arrive": "07:30", "price_pence": 1640, "is_advance": True}
    ]
