"""
Run:  python test_survival.py
Logic + smoke tests. Uses a tiny fake `streamlit`, so it needs no browser.
"""
import json
import sys
import types
from unittest.mock import MagicMock


class State(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k)

    def __setattr__(self, k, v):
        self[k] = v


def make_fake_streamlit():
    mod = types.ModuleType("streamlit")
    mod.session_state = State()
    def many(spec, **kw):
        n = spec if isinstance(spec, int) else len(spec)
        return [MagicMock() for _ in range(n)]
    mod.columns, mod.tabs = many, many
    mod.button = lambda *a, **k: False
    mod.checkbox = lambda *a, **k: False
    mod.file_uploader = lambda *a, **k: None
    mod.selectbox = lambda label, options, **k: list(options)[0]
    mod.__getattr__ = lambda name: MagicMock()
    return mod


st = make_fake_streamlit()
sys.modules["streamlit"] = st
import survival as sv  # noqa: E402


def fresh():
    st.session_state.clear()
    sv.initialize_survival_state()
    return st.session_state


def test_init_does_not_reset():
    s = fresh()
    s.health = 50
    sv.initialize_survival_state()
    assert s.health == 50


def test_change_resource_caps_and_log():
    s = fresh()
    sv.change_resource("food", 999, "test")
    assert s.food == sv.MAX["food"]
    sv.change_resource("health", -999)
    assert s.health == 0
    assert sv.change_resource("gold", 1)[0] is False


def test_guards():
    s = fresh()
    s.medicine = 0; sv.use_medicine(); assert s.last_reward["kind"] == "warning"
    s.medicine = 2; s.health = 100; sv.use_medicine(); assert s.medicine == 2
    s.food = 0; sv.use_food(); assert s.last_reward["kind"] == "warning"
    s.supplies = 1; sv.rest_at_safehouse(); assert s.supplies == 1
    s.supplies = 30; sv.collect_supply(); assert s.supplies == 30


def test_medkit_and_food_work():
    s = fresh()
    s.health = 40; s.medicine = 2
    sv.use_medicine()
    assert s.health == 70 and s.medicine == 1 and s.xp > 0
    s.food = 3; s.stamina = 50
    sv.use_food()
    assert s.food == 2 and s.stamina == 68


def test_medbay_upgrade_boosts_heal():
    s = fresh()
    s.upgrades["medbay"] = 2; s.health = 20; s.medicine = 1
    sv.use_medicine()
    assert s.health == 60


def test_scavenge_rarity_and_resources_in_range():
    for _ in range(300):
        s = fresh()
        s.supplies = 10; s.stamina = 80
        sv.scavenge()
        assert s.crates_opened == 1 and s.last_loot["rarity"] in ("Common", "Rare", "Epic", "Legendary")
        for k, cap in sv.MAX.items():
            assert 0 <= s[k] <= cap
        assert all(0 <= v <= sv.INV_MAX for v in s.inventory.values())


def test_night_cycle_and_sleep():
    s = fresh()
    s.actions_today = 9
    assert sv.phase_index() == 3
    s.food = 2; s.health = 50
    day = s.day
    sv.end_day()
    assert s.day == day + 1 and s.actions_today == 0 and s.food == 1 and s.health == 75 and not s.daily_bonus_claimed
    s.food = 0; s.health = 5
    sv.end_day()
    assert s.health >= 1


def test_garden_harvest():
    s = fresh()
    s.upgrades["garden"] = 2; s.food = 3
    sv.end_day()
    assert s.food == 3 - 1 + 2


def test_daily_drop_streak():
    s = fresh()
    sv.claim_daily_bonus(); assert s.daily_streak == 1
    sv.claim_daily_bonus(); assert s.daily_streak == 1       # same day: blocked
    sv.end_day(); sv.claim_daily_bonus(); assert s.daily_streak == 2
    sv.end_day(); sv.end_day(); sv.claim_daily_bonus(); assert s.daily_streak == 1   # missed a day
    assert "First Check-In" in s.achievements


def test_crafting():
    s = fresh()
    s.inventory.update({"bandage": 2, "water": 1}); m0 = s.medicine
    sv.craft("medkit")
    assert s.medicine == m0 + 1 and s.inventory["bandage"] == 0
    sv.craft("medkit")                                       # not enough now
    assert s.last_reward["kind"] == "warning"
    assert "Craftsman" in s.achievements


def test_upgrades():
    s = fresh()
    s.inventory["scrap"] = 10; s.supplies = 20
    sv.buy_upgrade("walls")
    assert s.upgrades["walls"] == 1 and s.inventory["scrap"] == 7 and s.supplies == 16
    assert sv.upgrade_cost("walls") == {"scrap": 6, "supplies": 8}
    s.upgrades["walls"] = 3
    sv.buy_upgrade("walls"); assert s.upgrades["walls"] == 3
    assert "Homesteader" in s.achievements


def test_quests_claim():
    s = fresh()
    q = sv.todays_quests()
    assert len(q) == 3 and len({x["id"] for x in q}) == 3
    first = q[0]
    sv.claim_quest(first["id"]); assert first["id"] not in s.quests_done     # not done yet
    s.daily[first["stat"]] = first["target"]
    xp0 = s.xp
    sv.claim_quest(first["id"])
    assert first["id"] in s.quests_done and s.xp > xp0
    sv.claim_quest(first["id"]); assert s.quests_claimed_total == 1           # no double claim
    assert [x["id"] for x in sv.todays_quests()] == [x["id"] for x in q]      # stable within a day


def test_levels_and_toast_queue():
    assert sv.level_info(0)[0] == 1 and sv.level_info(50)[0] == 2 and sv.level_info(200)[0] == 3
    s = fresh()
    sv.reward_xp(60, "boost", boosted=False)
    assert s.last_level == 2 and s.pending_balloons and len(s.pending_toast) >= 1
    s.upgrades["radio"] = 3
    assert sv.reward_xp(10) == 13


def test_save_load_roundtrip_and_rejects_bad_data():
    s = fresh()
    s.health = 33; s.xp = 123; s.upgrades["walls"] = 2
    raw = sv.export_save()
    fresh()
    ok, _ = sv.import_save(raw)
    assert ok and s.health == 33 and s.xp == 123 and s.upgrades["walls"] == 2
    assert sv.import_save("not json")[0] is False
    ok, _ = sv.import_save(json.dumps({"health": "lots", "xp": 999999999999, "food": 9999, "evil": 1}))
    assert ok and s.health == 33 and s.food == sv.MAX["food"] and "evil" not in s


def test_revive_and_reset():
    s = fresh()
    s.health = 0; s.medicine = 1
    sv.revive(); assert s.health == 30 and s.medicine == 0
    s.xp = 500
    sv.reset_game(); assert s.xp == 0


def test_full_ui_smoke():
    s = fresh()
    s.supplies = 20; s.xp = 300; s.health = 20
    for actions in range(1, 12):
        sv.render_survival_dashboard()
        sv.collect_supply()
    sv.render_survival_dashboard()


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t(); print("PASS", t.__name__)
    print(f"\nAll {len(tests)} tests passed.")
