"""gamedata conversion and Global-first merging, on tiny synthetic databases (CI-safe)."""
import sqlite3

import pytest

from racemech import gamedata

_ALT_COLS = []
for alt in (1, 2):
    _ALT_COLS += [f"precondition_{alt}", f"condition_{alt}", f"float_ability_time_{alt}",
                  f"ability_time_usage_{alt}", f"float_cooldown_time_{alt}"]
    for n in (1, 2, 3):
        _ALT_COLS += [f"ability_type_{alt}_{n}", f"ability_value_usage_{alt}_{n}",
                      f"float_ability_value_{alt}_{n}", f"target_type_{alt}_{n}"]


def _make_db(path, skills: dict[int, dict], names: dict[int, str]):
    con = sqlite3.connect(path)
    cols = ["id", "rarity", "tag_id", "activate_lot"] + _ALT_COLS
    con.execute(f"create table skill_data ({', '.join(cols)})")
    con.execute("create table text_data (id integer, category integer, [index] integer, text text)")
    for ddl in ("champions_schedule (id, start_date, end_date)",
                "champions_race_condition (champions_id, round_id, race_instance_id, race_condition_id)",
                "race_instance (id, race_id)",
                "race (id, course_set)",
                "race_course_set (id, race_track_id, distance, ground, turn)",
                "race_condition (id, season, weather, ground)"):
        con.execute(f"create table {ddl}")
    for sid, fields in skills.items():
        row = {c: 0 for c in cols} | {"precondition_1": "", "condition_1": "", "precondition_2": "",
                                       "condition_2": "", "tag_id": ""} | {"id": sid} | fields
        con.execute(f"insert into skill_data values ({', '.join('?' * len(cols))})", [row[c] for c in cols])
    for sid, name in names.items():
        con.execute("insert into text_data values (0, 47, ?, ?)", (sid, name))
    con.commit()
    con.close()


ACCEL = {"rarity": 2, "condition_1": "running_style==3&is_lastspurt==1", "float_ability_time_1": 15000,
         "ability_time_usage_1": 1, "ability_type_1_1": 31, "ability_value_usage_1_1": 1,
         "float_ability_value_1_1": 4000, "target_type_1_1": 1, "ability_type_1_2": 9,
         "ability_value_usage_1_2": 1, "float_ability_value_1_2": -200, "target_type_1_2": 1,
         "tag_id": "103/204", "activate_lot": 1}


@pytest.fixture
def data_dir(tmp_path):
    gd = tmp_path / "game"
    gd.mkdir()
    _make_db(gd / "global_master.mdb", {202421: ACCEL, 200532: {"rarity": 1, "condition_1": "phase==0"}},
             {202421: "Claw Forward", 200532: "Early Lead"})
    jp_skills = {200532: {"rarity": 1, "condition_1": "always==1"},
                 999991: {"rarity": 1, "condition_1": "phase==1"}}
    _make_db(gd / "jp_master.mdb", jp_skills, {200532: "逃げのコツ", 999991: "新スキル"})
    return tmp_path


def test_row_conversion_matches_uma_tools_shape(data_dir):
    g = gamedata.load(data_dir)
    e = g.skills["202421"].entry
    assert e["rarity"] == 2 and e["tags"] == [103, 204] and e["wisdomCheck"] == 1
    (alt,) = e["alternatives"]
    assert alt["condition"] == "running_style==3&is_lastspurt==1"
    assert alt["baseDuration"] == 15000
    assert [(x["type"], x["modifier"], x["target"]) for x in alt["effects"]] == [(31, 4000, 1), (9, -200, 1)]


def test_global_wins_and_jp_only_fills_gaps(data_dir):
    g = gamedata.load(data_dir)
    early = g.skills["200532"]
    assert early.source == "global" and early.name == "Early Lead"
    assert early.entry["alternatives"][0]["condition"] == "phase==0"     # not JP's always==1
    jp_only = g.skills["999991"]
    assert jp_only.source == "jp" and jp_only.name == "新スキル"


def test_missing_global_db_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        gamedata.load(tmp_path)
