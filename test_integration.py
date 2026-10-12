"""Run: python test_integration.py  - plays through the whole integrated game with a fake Streamlit."""
import random, sys
sys.path.insert(0, ".")
import test_survival as ts
st = sys.modules["streamlit"]
import survival as sv, missions as m, exploration as ex, exploration_ui as ui

s = ts.fresh(); m.ensure_state(s)
assert s.health == 86 and m.MAX_VALUES["food"] == sv.MAX["food"]

# --- Member 4 exploration against Member 2 state (live session state) ---
for seed in range(400):
    s = ts.fresh(); m.ensure_state(s)
    rng = random.Random(seed)
    for loc in ex.LOCATIONS:
        s.stamina = 100; s.health = max(s.health, 40)
        out = ex.explore_location(loc, state=s, rng=rng)
        assert out["ok"]
        for k, cap in sv.MAX.items():
            assert 0 <= s[k] <= cap, (k, s[k])
        assert all(isinstance(v, int) for v in s.inventory.values())
assert s.runs == 5 and set(s.explored) == set(ex.LOCATIONS) and s.xp > 0
assert any("Explored" in e for e in s.event_log), "exploration must write to the safehouse feed"
assert any("XP" in e for e in s.event_log)

# exhausted / downed handling
s = ts.fresh(); s.stamina = 1
assert ex.explore_location("Abandoned Hospital", state=s)["ok"] is False
s.stamina = 100; s.health = 0
assert "revive" in ex.explore_location("Abandoned Hospital", state=s)["message"].lower()

# plain dict still works (Member 4 standalone)
d = {"health": 80, "stamina": 80, "xp": 0, "inventory": {}, "activity": []}
assert ex.explore_location("Safehouse Outpost", state=d, rng=random.Random(3))["ok"] and d["activity"]

# --- missions + survival + exploration share one player ---
s = ts.fresh(); m.ensure_state(s)
rng = random.Random(1); rng.random = lambda: 0.0
for mid in m.MISSION_ORDER:
    s.stamina = 100; s.health = 100
    m.start_mission(s, mid)
    while s.run:
        stage = m.current_stage(s.run)
        opts = [i for i, c in enumerate(stage["choices"]) if m.can_afford(s, c.get("cost"))]
        m.make_choice(s, opts[0], rng)
assert set(s.completed_missions) == set(m.MISSION_ORDER)
lvl = sv.level_info(s.xp)[0]
assert lvl > 1 and s.last_level < lvl
sv.show_celebrations()
assert s.last_level == lvl and s.pending_toast == []

# --- whole app, every page, plus a few real clicks ---
src = open("app.py").read()
for page in ["🏠 Home", "🩺 Survival Command", "🎯 Missions", "🗺️ Explore", "📖 How to Play"]:
    st.radio = lambda *a, _p=page, **k: _p
    exec(compile(src, "app.py", "exec"), {"__name__": "__main__"})
    print("page OK:", page)
ui.render_exploration()
s.exploration_last_result = ex.explore_location("Rusted Supermarket", state=s)
ui.render_exploration()
sv.render_survival_dashboard(); m.render_missions()

# save/load carries everything
raw = sv.export_save(); score = s.score; ts.fresh(); sv.import_save(raw); assert s.score == score
print("INTEGRATION OK")
