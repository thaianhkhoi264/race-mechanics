from racemech.evaluation import load_questions, numbers_in, score, unsupported


def test_numbers_in_handles_commas_ranges_and_decimals():
    assert numbers_in("1,674–2,200 m and +0.4 for 8.8 s") == [1674, 2200, 0.4, 8.8]


def test_number_tolerance_and_keywords():
    q = {"id": "x", "question": "q", "numbers": [{"value": 3, "tol": 0.35}], "keywords": [["3.5%", "0.035"]]}
    assert score(q, "About 3.3 debuffers, reading 0.35 as 3.5%.", "ctx 3.3 3.5").passed
    s = score(q, "About 5 debuffers.", "ctx")
    assert not s.passed and len(s.failures) == 2


def test_decline_detection():
    q = {"id": "d", "question": "q", "decline": True}
    assert score(q, "I don't have information about that skill.", "").passed
    assert not score(q, "It gives +0.35 speed.", "").passed


def test_unsupported_numbers_allow_rounding_and_percent_forms():
    ctx = "spare HP 8.2% of max; Max HP 2216; Recovery 0.035"
    assert unsupported("You have 8% spare and 2,216 HP, a 3.5% heal", ctx, "") == []
    assert unsupported("That heal is 77.56 HP", ctx, "") == [77.56]


def test_question_file_is_well_formed():
    qs = load_questions()
    ids = [q["id"] for q in qs]
    assert len(ids) == len(set(ids)) >= 25
    assert all(q["question"].strip() for q in qs)
