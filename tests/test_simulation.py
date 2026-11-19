"""simulation snapshot analysis on a small synthetic snapshot (no network, no bot)."""
import pytest

from racemech import simulation

COLUMNS = ["skillId", "style", "players", "owned", "activated", "procs", "repeat",
           "ownWinsActive", "ownWinsInactive", "teamWinsActive", "teamWinsInactive"]


def snapshot(sid="cm22-2026-11-18", activated=400):
    overview = {
        "columns": COLUMNS, "courseDistance": 1600,
        "variants": {"100511": [100511, 900511]},
        "populationByStyle": {"Sashi": [10000, 1000]},
        # owned 1000, fired `activated`, 120 wins when fired, 60 wins when not
        "rows": [[100511, "Sashi", 50, 1000, activated, activated, 0, 120, 60, 0, 0]],
    }
    details = {"100511": {"styles": {"Sashi": [
        # bucket, procs, firstEntries, firstIndividualWins, firstTeamWins
        [66, 200, 200, 80, 0], [67, 40, 40, 10, 0], [80, 160, 160, 30, 0]]}}}
    meta = {"snapshotId": sid, "meta": {"cumulativeSimulations": 10_000_000, "evaluatedTeams": 27164,
                                         "capturedThrough": "2026-11-18"}}
    return {"snapshot_id": sid, "captured": "2026-11-18", "meta": meta, "overview": overview,
            "details": details}


def test_inherited_copy_maps_to_base_id():
    assert simulation.base_id("900511", snapshot()["overview"]) == "100511"
    assert simulation.base_id("123456", snapshot()["overview"]) is None


def test_rates_and_win_split():
    st = simulation.skill_stats("900511", [snapshot()]).styles["late"]
    assert st.rate == pytest.approx(0.4)
    assert st.win_active == pytest.approx(120 / 400)
    assert st.win_inactive == pytest.approx(60 / 600)
    assert st.win_without == pytest.approx((1000 - 180) / (10000 - 1000))


def test_timing_from_heatmap():
    st = simulation.skill_stats("100511", [snapshot()]).styles["late"]
    assert st.earliest_m == pytest.approx(1056)
    assert st.share_earliest == pytest.approx(240 / 400)        # buckets 66-67
    assert st.median_m == pytest.approx(1056)                   # 200 of 400 already at bucket 66
    assert st.win_early == pytest.approx(90 / 240)
    assert st.win_later == pytest.approx(30 / 160)


def test_stability_and_description():
    snaps = [snapshot("cm22-2026-11-17", 380), snapshot("cm22-2026-11-18", 400)]
    stats = simulation.skill_stats("100511", snaps)
    assert stats.history["late"] == pytest.approx([0.38, 0.40])
    text = "\n".join(simulation.describe(stats, snaps[-1]["meta"], ["late"]))
    assert "fired in 40.0%" in text and "small sample" in text and "38.0% to 40.0%" in text
    assert "correlation, not cause" in text


def test_phase_labels():
    assert simulation.phase_of(540, 1200) == "mid-race"
    assert simulation.phase_of(100, 1200) == "early-race"
    assert simulation.phase_of(1056, 1600) == "mid-race"        # late-race starts at 1067 m
    assert simulation.phase_of(1100, 1600) == "late-race"
