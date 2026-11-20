from datetime import datetime

import pytest

from spaceutil.analysis import (Visit, flag, hourly_profile, load_spaces, load_visits,
                                peak_occupancy, space_stats)
from spaceutil.cli import main


def v(space, a, b, badge="B1"):
    f = "%Y-%m-%d %H:%M"
    return Visit(badge, space, datetime.strptime(a, f), datetime.strptime(b, f))


def test_peak_counts_overlap():
    visits = [v("R", "2026-03-02 09:00", "2026-03-02 10:00"), v("R", "2026-03-02 09:30", "2026-03-02 11:00")]
    assert peak_occupancy(visits) == 2


def test_peak_back_to_back_is_one():
    visits = [v("R", "2026-03-02 09:00", "2026-03-02 10:00"), v("R", "2026-03-02 10:00", "2026-03-02 11:00")]
    assert peak_occupancy(visits) == 1


def test_peak_empty():
    assert peak_occupancy([]) == 0


def test_utilization_math():
    visits = [v("R", "2026-03-02 09:00", "2026-03-02 12:00")]
    row = space_stats(visits, {"R": 2}, day_hours=9)[0]
    assert row["utilization"] == round(100 * 3 / (2 * 9), 1)


def test_utilization_uses_all_days_in_data():
    visits = [v("R", "2026-03-02 09:00", "2026-03-02 11:00"), v("Q", "2026-03-03 09:00", "2026-03-03 10:00")]
    rows = {r["space"]: r for r in space_stats(visits, {"R": 1, "Q": 1}, day_hours=10)}
    assert rows["R"]["utilization"] == 10.0


def test_flags():
    assert flag({"peak": 5, "capacity": 4, "utilization": 90}, 30) == "OVER"
    assert flag({"peak": 1, "capacity": 4, "utilization": 10}, 30) == "UNDER"
    assert flag({"peak": 2, "capacity": 4, "utilization": 50}, 30) == ""


def test_hourly_profile_splits_partial_hours():
    visits = [v("R", "2026-03-02 09:30", "2026-03-02 10:30")]
    prof = hourly_profile(visits)
    assert prof[9] == 0.5 and prof[10] == 0.5 and prof[8] == 0.0


def test_load_spaces_rejects_zero_capacity(tmp_path):
    f = tmp_path / "s.csv"
    f.write_text("space,capacity\nRoom,0\n")
    with pytest.raises(ValueError):
        load_spaces(f)


def test_load_visits_unknown_space(tmp_path):
    f = tmp_path / "e.csv"
    f.write_text("badge,space,entry,exit\nB1,Nowhere,2026-03-02 09:00,2026-03-02 10:00\n")
    with pytest.raises(ValueError, match="unknown space"):
        load_visits(f, {"Room": 4})


def test_load_visits_exit_before_entry(tmp_path):
    f = tmp_path / "e.csv"
    f.write_text("badge,space,entry,exit\nB1,Room,2026-03-02 10:00,2026-03-02 09:00\n")
    with pytest.raises(ValueError, match="not after"):
        load_visits(f, {"Room": 4})


def test_cli_report_on_examples(capsys):
    code = main(["report", "examples/badge_events.csv", "examples/spaces.csv"])
    out = capsys.readouterr().out
    assert code == 0 and "Open Office East" in out and "Under 30% used" in out


def test_cli_bad_file_exits_2(capsys):
    assert main(["report", "missing.csv", "examples/spaces.csv"]) == 2
    assert "error:" in capsys.readouterr().err
