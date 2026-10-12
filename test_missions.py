"""Run:  python test_missions.py   (no Streamlit needed)"""
import random
import missions as m


def play(store, mid, rng, pick=None):
    ok, msg = m.start_mission(store, mid)
    assert ok, msg
    while store["run"]:
        stage = m.current_stage(store["run"])
        options = [i for i, c in enumerate(stage["choices"]) if m.can_afford(store, c.get("cost"))]
        m.make_choice(store, pick if pick in options else rng.choice(options), rng)
    return store["last_result"]


def test_defaults_do_not_overwrite():
    s = {"health": 42, "food": 9}
    m.ensure_state(s)
    assert s["health"] == 42 and s["food"] == 9 and s["xp"] == 0


def test_all_missions_play_through():
    for seed in range(300):
        rng = random.Random(seed)
        s = m.ensure_state({})
        for mid in m.MISSION_ORDER:
            s["stamina"] = 100
            if s["health"] <= 0:
                s["health"] = 50
            play(s, mid, rng)
            for k, cap in m.MAX_VALUES.items():
                assert 0 <= s[k] <= cap, (k, s[k])
            assert s["run"] is None


def test_win_gives_rewards():
    wins = 0
    for seed in range(200):
        s = m.ensure_state({})
        r = play(s, "food", random.Random(seed), pick=0)
        if r["won"]:
            wins += 1
            assert r["stars"] >= 1 and r["points"] > 0 and "food" in s["completed_missions"]
            assert s["score"] >= r["points"]
    assert wins > 0


def test_cannot_start_when_exhausted():
    s = m.ensure_state({})
    s["stamina"] = 5
    ok, _ = m.start_mission(s, "food")
    assert not ok and s["run"] is None


def test_cost_blocks_choice():
    s = m.ensure_state({})
    m.start_mission(s, "medicine")
    s["supplies"] = 0
    res = m.make_choice(s, 2, random.Random(1))   # flare costs 1 supplies
    assert not res["ok"]


def test_death_is_rescued_not_game_over():
    s = m.ensure_state({})
    m.start_mission(s, "medicine")
    s["health"] = 1
    rng = random.Random(0)
    rng.random = lambda: 0.99                       # force failure
    m.make_choice(s, 0, rng)
    assert s["run"] is None and s["last_result"]["won"] is False and s["health"] == 15


def test_randomness_varies():
    outcomes = set()
    for seed in range(40):
        s = m.ensure_state({})
        r = play(s, "rescue", random.Random(seed))
        outcomes.add((r["won"], r["points"]))
    assert len(outcomes) > 5


def test_streak_and_achievements():
    s = m.ensure_state({})
    for _ in range(3):
        s["streak"] = s["streak"]            # keep
    rng = random.Random(5)
    rng.random = lambda: 0.0                 # always succeed
    for mid in m.MISSION_ORDER:
        s["stamina"] = 100; s["health"] = 100
        play(s, mid, rng)
    assert s["streak"] == 3 and "streak3" in s["mission_achievements"] and "all_clear" in s["mission_achievements"]
    assert m.rank_for(s["xp"]) != "Rookie"


def test_abandon_and_reset():
    s = m.ensure_state({})
    m.start_mission(s, "food"); s["streak"] = 2
    m.abandon_mission(s)
    assert s["run"] is None and s["streak"] == 0
    m.reset_progress(s)
    assert s["score"] == 0 and s["completed_missions"] == []


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t(); print("PASS", t.__name__)
    print(f"\nAll {len(tests)} tests passed.")
