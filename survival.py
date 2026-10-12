"""
DEAD ZONE  -  Member 2: Survival Dashboard & Inventory  (PRO EDITION)
=====================================================================
Day 1 : dashboard, vitals, inventory cards, collect / use resources, session state.
Day 2 : warnings, invalid-action guards, activity log, shared helpers, integration.
PRO   : player level + rank, day/night cycle, loot crates with rarity, workshop
        crafting, safehouse upgrades, daily ops (quests), daily-drop streak,
        20 achievements-style unlocks, vitals chart, save/load file, animated HUD.

Main entry point:   render_survival_dashboard()
Shared helpers  :   initialize_survival_state, change_resource, add_event,
                    reward_xp, unlock_achievement   (same names as before)

SHARED STATE KEYS (shared with Member 3's missions.py)
    health stamina food medicine supplies   - the resources
    xp   - experience (drives level + rank)    score - total points
    completed_missions, event_log, inventory, achievements
"""
import copy
import json
import random
from datetime import datetime

import streamlit as st

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------
MAX = {"health": 100, "food": 20, "medicine": 12, "supplies": 30, "stamina": 100}
INV_MAX = 20
PHASES = [("🌅", "Dawn"), ("☀️", "Midday"), ("🌇", "Dusk"), ("🌙", "Night")]
ACTIONS_PER_PHASE = 3
THREAT_NAMES = ["", "LOW", "GUARDED", "ELEVATED", "HIGH", "EXTREME"]
RANKS = [(0, "Rookie"), (150, "Scavenger"), (400, "Survivor"), (800, "Hunter"), (1500, "Dead Zone Legend")]
RARITIES = [("Common", "#9aa5b1", 60), ("Rare", "#4cc9f0", 25), ("Epic", "#b388ff", 12), ("Legendary", "#ffb703", 3)]

UPGRADES = {
    "walls":  {"icon": "🧱", "name": "Reinforced Walls", "desc": "Fewer and weaker night ambushes.",     "base": {"scrap": 3, "supplies": 4}},
    "garden": {"icon": "🌱", "name": "Rooftop Garden",   "desc": "+1 ration every dawn per level.",      "base": {"scrap": 2, "supplies": 5}},
    "medbay": {"icon": "🏥", "name": "Med Bay",          "desc": "Medkits heal +5 more per level.",      "base": {"scrap": 3, "supplies": 6}},
    "radio":  {"icon": "📻", "name": "Radio Tower",      "desc": "+10% XP from survival actions per level.", "base": {"scrap": 4, "supplies": 6}},
}
UPGRADE_MAX = 3

RECIPES = {
    "medkit":  {"icon": "🧪", "name": "Medkit",        "needs": {"bandage": 2, "water": 1},  "gives": ("medicine", 1), "xp": 12},
    "ration":  {"icon": "🥫", "name": "Ration pack",   "needs": {"water": 1, "supplies": 2}, "gives": ("food", 2),     "xp": 8},
    "bandage": {"icon": "🩹", "name": "Bandages x2",   "needs": {"supplies": 2},             "gives": ("bandage", 2),  "xp": 4},
    "salvage": {"icon": "🔩", "name": "Salvage supplies", "needs": {"scrap": 3},             "gives": ("supplies", 2), "xp": 5},
}
INV_ICONS = {"bandage": "🩹", "scrap": "🔩", "water": "💧"}

QUEST_POOL = [
    ("actions",   "Take {n} survival actions today", (4, 7), 25, 1),
    ("scavenged", "Search {n} supply caches",        (1, 3), 30, 1),
    ("crafted",   "Craft {n} item(s) in the workshop", (1, 2), 30, 2),
    ("healed",    "Use a medkit {n} time(s)",        (1, 1), 20, 1),
    ("ate",       "Eat {n} ration(s)",               (1, 2), 20, 1),
    ("rested",    "Rest at the safehouse {n} time(s)", (1, 2), 25, 1),
]

ACHIEVEMENTS = [
    ("First Check-In",      "🎁", "Claim your first daily supply drop.",     lambda s: s.daily_streak >= 1),
    ("Resourceful Survivor", "🎒", "Take 5 survival actions.",               lambda s: s.survival_actions >= 5),
    ("Craftsman",           "🔧", "Craft your first item.",                  lambda s: s.stats.get("crafted", 0) >= 1),
    ("Homesteader",         "🏠", "Buy your first safehouse upgrade.",       lambda s: sum(s.upgrades.values()) >= 1),
    ("Night Owl",           "🌙", "Survive your first night.",               lambda s: s.nights_survived >= 1),
    ("Week One",            "📅", "Reach Day 7.",                            lambda s: s.day >= 7),
    ("Crate Hunter",        "📦", "Open 5 supply caches.",                   lambda s: s.crates_opened >= 5),
    ("Lucky Find",          "💎", "Find an Epic or Legendary cache.",        lambda s: s.best_rarity >= 2),
    ("Quartermaster",       "🏦", "Hold 25+ supplies at once.",              lambda s: s.supplies >= 25),
    ("Peak Condition",      "💪", "Reach 100 health and 100 stamina.",       lambda s: s.health >= 100 and s.stamina >= 100),
    ("Quest Master",        "🎯", "Claim 3 daily ops.",                      lambda s: s.quests_claimed_total >= 3),
    ("Veteran",             "⭐", "Reach level 5.",                          lambda s: level_info(s.xp)[0] >= 5),
]

DEFAULTS = {
    "health": 86, "food": 6, "medicine": 3, "supplies": 8, "stamina": 78,
    "xp": 0, "score": 0, "completed_missions": [], "exploration_rewards": [],
    "event_log": ["You made it to the safehouse. The city is still dangerous."],
    "game_started": False, "survival_actions": 0,
    "inventory": {"bandage": 2, "scrap": 3, "water": 4},
    "achievements": [], "last_reward": None, "action_message": "", "daily_bonus_claimed": False,
    # --- pro edition ---
    "day": 1, "actions_today": 0, "daily_streak": 0, "last_claim_day": 0,
    "upgrades": {k: 0 for k in UPGRADES}, "daily": {}, "quests_done": [], "quests_claimed_total": 0,
    "stats": {}, "crates_opened": 0, "best_rarity": 0, "last_loot": None, "nights_survived": 0,
    "vital_history": [], "last_level": 1, "pending_toast": [], "pending_balloons": False,
    "mission_achievements": [],
}
EPHEMERAL = {"last_reward", "action_message", "last_loot", "pending_toast", "pending_balloons"}
MISSION_KEYS = ["streak", "best_streak", "attempts", "best", "history", "mission_achievements", "run", "last_result"]
MISSION_TYPES = {"streak": 0, "best_streak": 0, "attempts": 0, "best": {}, "history": []}
SAVE_KEYS = [k for k in DEFAULTS if k not in EPHEMERAL] + ["streak", "best_streak", "attempts", "best", "history"]


# ----------------------------------------------------------------------------
# STATE + SHARED HELPERS  (Members 3 & 4 call these)
# ----------------------------------------------------------------------------
def initialize_survival_state():
    """Initialize once; reruns do not reset progress."""
    for key, value in DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = copy.deepcopy(value)


def add_event(message):
    initialize_survival_state()
    st.session_state.event_log.insert(0, f"{datetime.now().strftime('%H:%M')} • {message}")
    st.session_state.event_log = st.session_state.event_log[:20]


def level_info(xp):
    """-> (level, xp into level, xp needed for next level)."""
    level = int((max(xp, 0) / 50) ** 0.5) + 1
    start, nxt = 50 * (level - 1) ** 2, 50 * level ** 2
    return level, xp - start, nxt - start


def rank_for(xp):
    name = RANKS[0][1]
    for threshold, rank in RANKS:
        if xp >= threshold:
            name = rank
    return name


def _toast(text):
    """Queue a pop-up message; several can be queued per action (e.g. level-up + reward)."""
    queue = st.session_state.pending_toast
    if not isinstance(queue, list):
        queue = []
    queue.append(text)
    st.session_state.pending_toast = queue[-3:]


def change_resource(resource, amount, reason=""):
    """Shared helper for mission/exploration modules."""
    initialize_survival_state()
    if resource not in MAX:
        return False, f"Unknown resource: {resource}"
    before = int(st.session_state[resource])
    after = max(0, min(MAX[resource], before + int(amount)))
    st.session_state[resource] = after
    delta = after - before
    if delta:
        add_event(f"{resource.title()} {'+' if delta > 0 else ''}{delta}" + (f" • {reason}" if reason else ""))
    return True, f"{resource.title()} is now {after}."


def reward_xp(amount, reason="", boosted=True):
    """Give (or remove) XP. Radio Tower upgrade boosts positive survival XP."""
    initialize_survival_state()
    amount = int(amount)
    if amount > 0 and boosted:
        amount = round(amount * (1 + 0.10 * st.session_state.upgrades.get("radio", 0)))
    old_level = level_info(st.session_state.xp)[0]
    st.session_state.xp = max(0, int(st.session_state.xp) + amount)
    st.session_state.score = max(0, int(st.session_state.score) + amount)
    if amount:
        add_event(f"{'+' if amount > 0 else ''}{amount} XP" + (f" • {reason}" if reason else ""))
    _check_level_up(old_level)
    return amount


def _check_level_up(old_level):
    new_level = level_info(st.session_state.xp)[0]
    if new_level > old_level:
        st.session_state.last_level = new_level
        add_event(f"LEVEL UP! You are now level {new_level}")
        _toast(f"🎉 LEVEL UP! You reached level {new_level} ({rank_for(st.session_state.xp)})")
        st.session_state.pending_balloons = True


def unlock_achievement(name):
    initialize_survival_state()
    if name not in st.session_state.achievements:
        st.session_state.achievements.append(name)
        add_event(f"Achievement unlocked: {name}")
        _toast(f"🏅 Achievement unlocked: {name}")


def check_achievements():
    s = st.session_state
    for name, _icon, _desc, cond in ACHIEVEMENTS:
        try:
            if name not in s.achievements and cond(s):
                unlock_achievement(name)
        except Exception:
            pass


def _set_message(text, kind="info"):
    st.session_state.last_reward = {"text": text, "kind": kind}
    if kind == "success":
        _toast(text)


def _bump(key, n=1):
    for bucket in ("daily", "stats"):
        d = st.session_state[bucket]
        d[key] = d.get(key, 0) + n


def phase_index():
    return min(len(PHASES) - 1, st.session_state.actions_today // ACTIONS_PER_PHASE)


def threat_level():
    base = [1, 2, 3, 5][phase_index()]
    return max(1, base - st.session_state.upgrades.get("walls", 0) + (1 if st.session_state.health < 35 else 0))


def _after_action(advance=True):
    s = st.session_state
    s.survival_actions += 1
    _bump("actions")
    if advance:
        s.actions_today += 1
    s.vital_history.append({"Health": s.health, "Stamina": s.stamina})
    s.vital_history = s.vital_history[-40:]
    check_achievements()


def _inv_add(item, amount):
    inv = st.session_state.inventory
    inv[item] = min(INV_MAX, inv.get(item, 0) + amount)


def _has(needs):
    s = st.session_state
    return all((s.inventory.get(k, 0) if k in INV_ICONS else s[k]) >= v for k, v in needs.items())


def _pay(needs):
    s = st.session_state
    for k, v in needs.items():
        if k in INV_ICONS:
            s.inventory[k] -= v
        else:
            s[k] -= v


# ----------------------------------------------------------------------------
# ACTIONS
# ----------------------------------------------------------------------------
def use_medicine():
    initialize_survival_state()
    s = st.session_state
    if s.medicine <= 0:
        _set_message("No medkits left. Craft one in the Workshop or search the hospital.", "warning"); return
    if s.health >= 100:
        _set_message("Health is full — save your medkit for a dangerous encounter."); return
    before = s.health
    s.medicine -= 1
    s.health = min(100, before + 30 + 5 * s.upgrades["medbay"])
    _bump("healed")
    _after_action(advance=False)
    reward_xp(5, "careful treatment")
    _set_message(f"Medkit used! +{s.health - before} health and +5 XP.", "success")


def use_food():
    initialize_survival_state()
    s = st.session_state
    if s.food <= 0:
        _set_message("No food left. Try the supermarket, a ration pack, or a food mission.", "warning"); return
    s.food -= 1
    before = s.stamina
    s.stamina = min(100, before + 18)
    s.health = min(100, s.health + 3)
    _bump("ate")
    _after_action(advance=False)
    add_event("Ate a ration • stamina restored")
    _set_message(f"Ration consumed! +{s.stamina - before} stamina and +3 health.", "success")


def collect_supply():
    initialize_survival_state()
    s = st.session_state
    if s.supplies >= MAX["supplies"]:
        _set_message("Your pack is full. Use supplies before collecting more.", "warning"); return
    s.supplies += 1
    extra = ""
    if random.random() < 0.25:
        _inv_add("scrap", 1)
        extra = " You also spotted some scrap metal!"
    _after_action()
    add_event("Collected 1 loose supply")
    _set_message("Supply secured." + extra, "success")


def rest_at_safehouse():
    initialize_survival_state()
    s = st.session_state
    if s.supplies < 2:
        _set_message("Resting costs 2 supplies. Find more before resting.", "warning"); return
    if s.health >= 100 and s.stamina >= 100:
        _set_message("You're already fully rested. Save your supplies."); return
    s.supplies -= 2
    h0, s0 = s.health, s.stamina
    s.health = min(100, h0 + 12)
    s.stamina = min(100, s0 + 30)
    _bump("rested")
    _after_action()
    reward_xp(8, "safehouse rest")
    add_event(f"Rested • +{s.health - h0} health, +{s.stamina - s0} stamina")
    _set_message("Safehouse rest complete. +8 XP.", "success")


def _roll_rarity():
    idx = random.choices(range(len(RARITIES)), weights=[r[2] for r in RARITIES])[0]
    return idx


def scavenge():
    """Search a supply cache: costs 1 supply + 10 stamina. Rarity decides the loot."""
    initialize_survival_state()
    s = st.session_state
    if s.stamina < 10:
        _set_message("Too exhausted to search. Eat a ration or rest first.", "warning"); return
    if s.supplies < 1:
        _set_message("Searching costs 1 supply for tools. Collect supplies first.", "warning"); return
    s.supplies -= 1
    s.stamina = max(0, s.stamina - 10)

    ambush = ""
    if phase_index() == 3 and random.random() < max(0.05, 0.35 - 0.08 * s.upgrades["walls"]):
        dmg = max(3, random.randint(8, 14) - 2 * s.upgrades["walls"])
        change_resource("health", -dmg, "night ambush")
        ambush = f" A zombie ambushed you in the dark (-{dmg} health)."

    idx = _roll_rarity()
    name, color, _ = RARITIES[idx]
    loot = {}
    for _ in range(idx + 1):
        if random.random() < 0.6:
            res = random.choice(["food", "medicine", "supplies"])
            qty = random.randint(1, 2) if res != "medicine" else 1
            if idx >= 2:
                qty += 1
            change_resource(res, qty, f"{name.lower()} cache")
            loot[res] = loot.get(res, 0) + qty
        else:
            item = random.choice(list(INV_ICONS))
            qty = random.randint(1, 2)
            _inv_add(item, qty)
            loot[item] = loot.get(item, 0) + qty
    xp_gain = [7, 15, 30, 70][idx]
    s.crates_opened += 1
    s.best_rarity = max(s.best_rarity, idx)
    s.last_loot = {"rarity": name, "color": color, "loot": loot, "xp": xp_gain}
    _bump("scavenged")
    _after_action()
    reward_xp(xp_gain, f"{name.lower()} cache")
    if idx == 3:
        s.pending_balloons = True
    _set_message(f"{name} cache! " + ", ".join(f"+{v} {k}" for k, v in loot.items()) + f". +{xp_gain} XP." + ambush,
                 "warning" if ambush else "success")


random_supply_cache = scavenge  # old name kept so earlier imports still work


def claim_daily_bonus():
    """Daily supply drop - bigger reward for consecutive days."""
    initialize_survival_state()
    s = st.session_state
    if s.daily_bonus_claimed:
        _set_message("Today's supply drop was already claimed. Sleep until dawn for the next one."); return
    s.daily_streak = s.daily_streak + 1 if s.last_claim_day == s.day - 1 else 1
    s.last_claim_day = s.day
    s.daily_bonus_claimed = True
    sup = 2 + min(s.daily_streak, 5)
    s.supplies = min(MAX["supplies"], s.supplies + sup)
    reward_xp(10 + 5 * s.daily_streak, "daily supply drop")
    check_achievements()
    _set_message(f"Daily drop (streak x{s.daily_streak}): +{sup} supplies and +{10 + 5 * s.daily_streak} XP!", "success")


def end_day():
    """Sleep until dawn: heal, grow food, new day, new daily ops."""
    initialize_survival_state()
    s = st.session_state
    hungry = s.food <= 0
    if not hungry:
        s.food -= 1
    s.health = min(100, s.health + (25 if not hungry else -10))
    s.health = max(1, s.health)
    s.stamina = min(100, s.stamina + 40)
    garden = s.upgrades["garden"]
    if garden:
        change_resource("food", garden, "rooftop garden harvest")
    s.day += 1
    s.actions_today = 0
    s.daily_bonus_claimed = False
    s.daily = {}
    s.quests_done = []
    s.nights_survived += 1
    s.vital_history.append({"Health": s.health, "Stamina": s.stamina})
    add_event(f"Day {s.day - 1} ended • you survived the night" + (" (hungry!)" if hungry else ""))
    reward_xp(15, "survived the night")
    check_achievements()
    _set_message(f"Day {s.day} begins. " + ("You went to bed hungry (-10 health)." if hungry else "You slept well (+25 health, +40 stamina)."),
                 "warning" if hungry else "success")


def craft(recipe_id):
    initialize_survival_state()
    s = st.session_state
    r = RECIPES[recipe_id]
    if not _has(r["needs"]):
        _set_message(f"Missing materials for {r['name']}.", "warning"); return
    key, qty = r["gives"]
    if key in MAX and s[key] >= MAX[key]:
        _set_message(f"{key.title()} storage is full.", "warning"); return
    _pay(r["needs"])
    if key in INV_ICONS:
        _inv_add(key, qty)
    else:
        change_resource(key, qty, f"crafted {r['name'].lower()}")
    _bump("crafted")
    _after_action()
    reward_xp(r["xp"], "crafting")
    _set_message(f"Crafted {r['name']}! +{r['xp']} XP.", "success")


def upgrade_cost(uid):
    lvl = st.session_state.upgrades[uid]
    return {k: v * (lvl + 1) for k, v in UPGRADES[uid]["base"].items()}


def buy_upgrade(uid):
    initialize_survival_state()
    s = st.session_state
    if s.upgrades[uid] >= UPGRADE_MAX:
        _set_message(f"{UPGRADES[uid]['name']} is already maxed.", "info"); return
    cost = upgrade_cost(uid)
    if not _has(cost):
        _set_message("Not enough materials for this upgrade.", "warning"); return
    _pay(cost)
    s.upgrades[uid] += 1
    _bump("upgrades")
    add_event(f"Upgraded {UPGRADES[uid]['name']} to level {s.upgrades[uid]}")
    reward_xp(20 * s.upgrades[uid], "safehouse upgrade")
    check_achievements()
    _set_message(f"{UPGRADES[uid]['name']} upgraded to level {s.upgrades[uid]}!", "success")


def revive():
    initialize_survival_state()
    s = st.session_state
    if s.medicine >= 1:
        s.medicine -= 1
    elif s.supplies >= 2:
        s.supplies -= 2
    else:
        s.health = 10
        add_event("Dragged to safety by a passing survivor")
        _set_message("A stranger dragged you to safety with almost nothing to spare.", "warning"); return
    s.health = 30
    add_event("Revived at the safehouse")
    _set_message("You're back on your feet. Be careful out there.", "success")


# ---- daily ops --------------------------------------------------------------
def todays_quests():
    rng = random.Random(st.session_state.day * 7919)
    picks = rng.sample(QUEST_POOL, 3)
    quests = []
    for i, (stat, text, (lo, hi), xp, sup) in enumerate(picks):
        n = rng.randint(lo, hi)
        quests.append({"id": f"d{st.session_state.day}q{i}", "stat": stat, "target": n,
                       "text": text.format(n=n), "xp": xp, "sup": sup})
    return quests


def claim_quest(qid):
    s = st.session_state
    q = next((q for q in todays_quests() if q["id"] == qid), None)
    if not q or qid in s.quests_done or s.daily.get(q["stat"], 0) < q["target"]:
        _set_message("Finish the objective first.", "warning"); return
    s.quests_done.append(qid)
    s.quests_claimed_total += 1
    s.supplies = min(MAX["supplies"], s.supplies + q["sup"])
    reward_xp(q["xp"], "daily op complete")
    check_achievements()
    _set_message(f"Daily op complete! +{q['xp']} XP and +{q['sup']} supplies.", "success")


# ---- save / load ------------------------------------------------------------
def export_save():
    data = {k: st.session_state[k] for k in SAVE_KEYS if k in st.session_state}
    return json.dumps(data, indent=2)


def import_save(raw):
    """Load a save file. Only known keys with matching types are accepted."""
    try:
        data = json.loads(raw)
        assert isinstance(data, dict)
    except Exception:
        return False, "That file isn't a valid Dead Zone save."
    initialize_survival_state()
    loaded = 0
    for key in SAVE_KEYS:
        if key not in data:
            continue
        val = data[key]
        default = DEFAULTS.get(key, MISSION_TYPES.get(key))
        if default is not None and type(val) is not type(default):
            continue
        if key in MAX:
            val = max(0, min(MAX[key], int(val)))
        st.session_state[key] = val
        loaded += 1
    return True, f"Save loaded ({loaded} fields restored)."


def reset_game():
    for key in list(DEFAULTS) + MISSION_KEYS:
        if key in st.session_state:
            del st.session_state[key]
    initialize_survival_state()


# ----------------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------------
CSS = """
<style>
.block-container{padding-top:1.2rem;max-width:1300px}
.dz-hud{display:flex;gap:18px;align-items:center;flex-wrap:wrap;padding:18px 22px;border-radius:20px;margin-bottom:14px;
 background:radial-gradient(circle at 92% 0%,rgba(255,77,109,.22),transparent 40%),linear-gradient(135deg,#1a0a0a,#2b0f14 55%,#120808);
 border:1px solid #5c1a24;box-shadow:0 0 34px rgba(255,40,70,.14)}
.dz-avatar{width:64px;height:64px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:2rem;
 background:radial-gradient(circle,#3a1a20,#16090c);border:2px solid #ff4d6d;box-shadow:0 0 18px rgba(255,77,109,.5)}
.dz-id{flex:1;min-width:230px}
.dz-name{font-size:.72rem;letter-spacing:3px;color:#ff8fa3;font-weight:800}
.dz-rank{font-size:1.5rem;font-weight:850;color:#fff}
.dz-lvl{display:inline-block;margin-left:8px;padding:2px 10px;border-radius:999px;background:#ff4d6d;color:#fff;font-size:.8rem;font-weight:800}
.dz-chips{display:flex;gap:8px;flex-wrap:wrap}
.dz-chip{background:#241216;border:1px solid #4a2128;border-radius:999px;padding:5px 13px;font-size:.84rem;color:#f2d4d8}
.dz-bar{height:16px;border-radius:999px;background:#1c0f12;border:1px solid #3a1a20;overflow:hidden;position:relative}
.dz-fill{height:100%;border-radius:999px;position:relative;transition:width .6s ease}
.dz-fill:after{content:"";position:absolute;inset:0;background:linear-gradient(100deg,transparent 30%,rgba(255,255,255,.28) 50%,transparent 70%);
 background-size:200% 100%;animation:dzshine 2.4s linear infinite}
@keyframes dzshine{from{background-position:200% 0}to{background-position:-200% 0}}
.dz-fill.crit{animation:dzpulse 1s ease-in-out infinite}
@keyframes dzpulse{50%{filter:brightness(1.6)}}
.dz-barlabel{display:flex;justify-content:space-between;font-size:.8rem;color:#d8bcc1;margin:8px 0 3px;font-weight:700;letter-spacing:.5px}
.dz-card{padding:15px;border-radius:16px;background:linear-gradient(145deg,#1b0d11,#140a0d);border:1px solid #3a1a20;min-height:118px;
 transition:transform .15s ease,box-shadow .15s ease}
.dz-card:hover{transform:translateY(-3px);box-shadow:0 8px 22px rgba(255,77,109,.18)}
.dz-clabel{font-size:.74rem;color:#c9a9ae;letter-spacing:1.4px;font-weight:800}
.dz-cval{font-size:2rem;font-weight:850;color:#fff;margin:.3rem 0 .1rem}
.dz-cfoot{font-size:.78rem;color:#a98a90}
.dz-loot{border-radius:18px;padding:18px;text-align:center;margin:10px 0;animation:dzpop .5s ease}
@keyframes dzpop{0%{transform:scale(.8);opacity:0}100%{transform:scale(1);opacity:1}}
.dz-feed{background:#0e0709;border:1px solid #2e1519;border-radius:12px;padding:10px 14px;font-family:Consolas,monospace;font-size:.82rem;color:#e8b9c0}
.dz-feed div{padding:2px 0;border-bottom:1px dashed #2a1519}
.dz-ach{padding:12px;border-radius:14px;background:#1b1015;border:1px solid #3a1a20;text-align:center;height:100%}
.dz-ach.off{opacity:.33;filter:grayscale(1)}
.dz-radar{width:130px;height:130px;border-radius:50%;position:relative;margin:auto;overflow:hidden;
 background:repeating-radial-gradient(circle,rgba(46,204,113,.18) 0 2px,transparent 2px 22px),#06120b;border:2px solid #1f6b3e;box-shadow:0 0 22px rgba(46,204,113,.3)}
.dz-radar .sweep{position:absolute;inset:0;border-radius:50%;background:conic-gradient(from 0deg,rgba(46,204,113,.55),transparent 28%);animation:dzspin 3s linear infinite}
@keyframes dzspin{to{transform:rotate(360deg)}}
.dz-blip{position:absolute;width:9px;height:9px;border-radius:50%;background:#ff4d6d;box-shadow:0 0 9px #ff4d6d;animation:dzpulse 1.2s infinite}
.dz-down{padding:18px;border-radius:16px;background:#2a0c10;border:1px solid #ff4d6d;text-align:center;margin-bottom:12px;animation:dzpulse 1.4s infinite}
div.stButton>button{border-radius:12px;min-height:2.7rem;font-weight:750;border:1px solid #4a2128;background:#1d0f13;transition:all .15s ease}
div.stButton>button:hover{border-color:#ff4d6d;transform:translateY(-2px);box-shadow:0 6px 16px rgba(255,77,109,.28)}
@media (max-width:640px){.dz-rank{font-size:1.2rem}.dz-cval{font-size:1.6rem}.dz-hud{padding:14px}}
</style>
"""


def _bar(label, value, maximum, color, right=None):
    pct = max(0, min(100, 100 * value / maximum))
    crit = " crit" if pct < 30 else ""
    return (f'<div class="dz-barlabel"><span>{label}</span><span>{right or f"{value} / {maximum}"}</span></div>'
            f'<div class="dz-bar"><div class="dz-fill{crit}" style="width:{pct}%;background:{color}"></div></div>')


def _health_color(v):
    return "linear-gradient(90deg,#2ecc71,#7bed9f)" if v >= 60 else ("linear-gradient(90deg,#f39c12,#ffd166)" if v >= 30 else "linear-gradient(90deg,#c0132f,#ff4d6d)")


def _hud():
    s = st.session_state
    level, into, need = level_info(s.xp)
    icon, phase = PHASES[phase_index()]
    chips = (f'<span class="dz-chip">📅 Day <b>{s.day}</b></span><span class="dz-chip">{icon} {phase}</span>'
             f'<span class="dz-chip">☠️ Threat <b>{THREAT_NAMES[min(5, threat_level())]}</b></span>'
             f'<span class="dz-chip">🔥 Drop streak <b>{s.daily_streak}</b></span>'
             f'<span class="dz-chip">🎯 Score <b>{s.score}</b></span>')
    st.markdown(
        f'<div class="dz-hud"><div class="dz-avatar">🧍</div><div class="dz-id">'
        f'<div class="dz-name">SURVIVOR PROFILE</div><div class="dz-rank">{rank_for(s.xp)}<span class="dz-lvl">LVL {level}</span></div>'
        f'{_bar("XP", into, need, "linear-gradient(90deg,#ff4d6d,#ffb703)", f"{into} / {need} to next level")}'
        f'</div><div class="dz-chips">{chips}</div></div>', unsafe_allow_html=True)


def _radar():
    lvl = min(5, threat_level())
    spots = [(20, 30), (70, 22), (55, 68), (28, 74), (78, 58)][:lvl]
    blips = "".join(f'<span class="dz-blip" style="left:{x}%;top:{y}%;animation-delay:{i * .25}s"></span>' for i, (x, y) in enumerate(spots))
    st.markdown(f'<div class="dz-radar"><div class="sweep"></div>{blips}</div>'
                f'<div style="text-align:center;color:#9fd8b5;font-size:.78rem;margin-top:6px;letter-spacing:2px">THREAT RADAR · {THREAT_NAMES[lvl]}</div>',
                unsafe_allow_html=True)


def _resource_cards():
    s = st.session_state
    heal = 30 + 5 * s.upgrades["medbay"]
    items = [("❤️ HEALTH", s.health, "/ 100", "Survivor vitality", "#2ecc71"),
             ("⚡ STAMINA", s.stamina, "/ 100", "Needed for missions", "#ffb703"),
             ("🥫 FOOD", s.food, "rations", "Restores stamina", "#ff9f43"),
             ("🧪 MEDKITS", s.medicine, "kits", f"Heals up to {heal} health", "#ff4d6d"),
             ("📦 SUPPLIES", s.supplies, "units", "Rest, search, build", "#4cc9f0")]
    for col, (label, val, unit, hint, color) in zip(st.columns(5), items):
        with col:
            st.markdown(f'<div class="dz-card" style="border-top:3px solid {color}"><div class="dz-clabel">{label}</div>'
                        f'<div class="dz-cval">{val}<span style="font-size:.78rem;color:#a98a90"> {unit}</span></div>'
                        f'<div class="dz-cfoot">{hint}</div></div>', unsafe_allow_html=True)


def _loot_card():
    loot = st.session_state.last_loot
    if not loot:
        return
    items = "  ".join(f"{INV_ICONS.get(k, {'food': '🥫', 'medicine': '🧪', 'supplies': '📦'}.get(k, '🎁'))} +{v}" for k, v in loot["loot"].items())
    c = loot["color"]
    st.markdown(f'<div class="dz-loot" style="border:2px solid {c};background:radial-gradient(circle,{c}33,#140a0d);box-shadow:0 0 28px {c}66">'
                f'<div style="color:{c};letter-spacing:3px;font-weight:900">{loot["rarity"].upper()} CACHE</div>'
                f'<div style="font-size:1.6rem;margin:6px 0">{items}</div><div style="color:#e8b9c0">+{loot["xp"]} XP</div></div>',
                unsafe_allow_html=True)


def _warnings():
    s = st.session_state
    w = []
    if s.health < 35: w.append("Critical health! Heal before exploring dangerous locations.")
    elif s.health < 60: w.append("Health is low. Consider using a medkit or resting.")
    if s.stamina < 20: w.append("Stamina is nearly depleted. Eat or rest before your next run.")
    if s.food <= 1: w.append("Food reserves are nearly empty.")
    if s.medicine <= 1: w.append("Medkit supply is low. Craft one in the Workshop.")
    if s.supplies <= 2: w.append("General supplies are low; safehouse rest may be unavailable.")
    if phase_index() == 3: w.append("It's night. Searching is risky now - sleep until dawn to reset the day.")
    return w


def _tab_base():
    s = st.session_state
    if s.health <= 0:
        st.markdown('<div class="dz-down"><b style="font-size:1.3rem">💀 YOU ARE DOWN</b><br>Revive to continue.</div>', unsafe_allow_html=True)
        st.button("🚑 Revive (uses 1 medkit or 2 supplies)", on_click=revive, use_container_width=True, key="revive")
    left, right = st.columns([2, 1])
    with left:
        st.markdown(_bar("❤️ HEALTH", s.health, 100, _health_color(s.health)) +
                    _bar("⚡ STAMINA", s.stamina, 100, "linear-gradient(90deg,#f39c12,#ffd166)"), unsafe_allow_html=True)
    with right:
        _radar()
    st.write("")
    _resource_cards()
    st.markdown("#### ⚡ Quick actions")
    r1 = st.columns(4)
    r1[0].button("🧪 Use medkit", on_click=use_medicine, use_container_width=True, key="b_med")
    r1[1].button("🥫 Eat ration", on_click=use_food, use_container_width=True, key="b_food")
    r1[2].button("🛏️ Rest (−2 📦)", on_click=rest_at_safehouse, use_container_width=True, key="b_rest")
    r1[3].button("🔎 Search cache", on_click=scavenge, use_container_width=True, key="b_search")
    r2 = st.columns(3)
    r2[0].button("📦 Collect supply", on_click=collect_supply, use_container_width=True, key="b_collect")
    r2[1].button("🎁 Daily supply drop", on_click=claim_daily_bonus, use_container_width=True, key="b_daily", disabled=s.daily_bonus_claimed)
    r2[2].button("🌙 Sleep until dawn", on_click=end_day, use_container_width=True, key="b_sleep", type="primary")
    msg = s.last_reward
    if msg:
        {"success": st.success, "warning": st.warning}.get(msg["kind"], st.info)(msg["text"])
    _loot_card()
    warns = _warnings()
    col_a, col_b = st.columns([1.1, 1])
    with col_a:
        st.markdown("#### 🚨 Threat monitor")
        if warns:
            for w in warns:
                st.warning(w)
        else:
            st.success("Resources are stable. Plan your next move.")
    with col_b:
        st.markdown("#### 🎒 Backpack")
        st.markdown(" ".join(f'<span class="dz-chip">{INV_ICONS[k]} {k.title()}: <b>{s.inventory.get(k, 0)}</b></span>' for k in INV_ICONS), unsafe_allow_html=True)
        st.markdown("#### 📡 Safehouse activity")
        st.markdown('<div class="dz-feed">' + "".join(f"<div>› {e}</div>" for e in s.event_log[:8]) + "</div>", unsafe_allow_html=True)


def _tab_workshop():
    s = st.session_state
    st.markdown("#### 🔧 Crafting bench")
    st.caption("Turn your backpack items into the things you need most.")
    cols = st.columns(2)
    for i, (rid, r) in enumerate(RECIPES.items()):
        need = " + ".join(f"{v} {INV_ICONS.get(k, '')}{k}" for k, v in r["needs"].items())
        key, qty = r["gives"]
        with cols[i % 2]:
            st.markdown(f'<div class="dz-card"><div class="dz-clabel">{r["icon"]} {r["name"].upper()}</div>'
                        f'<div class="dz-cfoot" style="margin-top:6px">Needs: {need}</div>'
                        f'<div class="dz-cfoot">Makes: +{qty} {key} · +{r["xp"]} XP</div></div>', unsafe_allow_html=True)
            st.button(f"Craft {r['name']}", on_click=craft, args=(rid,), key=f"craft_{rid}", disabled=not _has(r["needs"]), use_container_width=True)
    st.markdown("#### 🏗️ Safehouse upgrades")
    st.caption("Permanent bonuses. Each level costs more scrap and supplies.")
    ucols = st.columns(2)
    for i, (uid, u) in enumerate(UPGRADES.items()):
        lvl = s.upgrades[uid]
        cost = upgrade_cost(uid)
        cost_txt = "MAXED" if lvl >= UPGRADE_MAX else " + ".join(f"{v} {k}" for k, v in cost.items())
        pips = "🟥" * lvl + "⬛" * (UPGRADE_MAX - lvl)
        with ucols[i % 2]:
            st.markdown(f'<div class="dz-card"><div class="dz-clabel">{u["icon"]} {u["name"].upper()} · LVL {lvl}</div>'
                        f'<div style="margin:6px 0">{pips}</div><div class="dz-cfoot">{u["desc"]}</div>'
                        f'<div class="dz-cfoot">Next: {cost_txt}</div></div>', unsafe_allow_html=True)
            st.button(f"Upgrade {u['name']}", on_click=buy_upgrade, args=(uid,), key=f"up_{uid}",
                      disabled=lvl >= UPGRADE_MAX or not _has(cost), use_container_width=True)


def _tab_daily():
    s = st.session_state
    st.markdown(f"#### 🎯 Daily ops — Day {s.day}")
    st.caption("Fresh objectives every day. Sleeping until dawn refreshes them.")
    for q in todays_quests():
        prog = min(s.daily.get(q["stat"], 0), q["target"])
        done = q["id"] in s.quests_done
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(f"**{'✅' if done else '🎯'} {q['text']}**  ·  reward: +{q['xp']} XP, +{q['sup']} 📦")
            st.progress(prog / q["target"], text=f"{prog} / {q['target']}")
        with c2:
            st.write("")
            st.button("Claimed" if done else "Claim reward", on_click=claim_quest, args=(q["id"],), key=f"q_{q['id']}",
                      disabled=done or prog < q["target"], use_container_width=True)
    st.markdown("#### 🎁 Supply drop streak")
    st.write(f"Current streak: **{s.daily_streak}** day(s). Claim every day to grow the reward "
             f"(next drop: +{2 + min(s.daily_streak + 1, 5)} supplies).")


def _tab_awards():
    s = st.session_state
    check_achievements()
    mission_count = len(s.get("mission_achievements", []))
    st.caption(f"{len(s.achievements)}/{len(ACHIEVEMENTS)} survival awards unlocked · {mission_count} mission awards (see Missions tab)")
    cols = st.columns(4)
    for i, (name, icon, desc, _c) in enumerate(ACHIEVEMENTS):
        on = name in s.achievements
        with cols[i % 4]:
            st.markdown(f'<div class="dz-ach {"" if on else "off"}"><div style="font-size:1.8rem">{icon if on else "🔒"}</div>'
                        f'<b>{name}</b><div style="font-size:.76rem;color:#b08a90">{desc}</div></div>', unsafe_allow_html=True)
            st.write("")


def _tab_stats():
    s = st.session_state
    c = st.columns(4)
    c[0].metric("⭐ Total XP", s.xp)
    c[1].metric("🧭 Missions cleared", len(s.completed_missions))
    c[2].metric("🔥 Actions taken", s.survival_actions)
    c[3].metric("📦 Caches opened", s.crates_opened)
    c = st.columns(4)
    c[0].metric("🌙 Nights survived", s.nights_survived)
    c[1].metric("🔧 Items crafted", s.stats.get("crafted", 0))
    c[2].metric("🏅 Achievements", len(s.achievements) + len(s.get("mission_achievements", [])))
    c[3].metric("🎯 Score", s.score)
    st.markdown("#### 📈 Vitals history")
    if len(s.vital_history) >= 2:
        import pandas as pd
        st.line_chart(pd.DataFrame(s.vital_history), height=220)
    else:
        st.caption("Take a few actions and your health/stamina graph will appear here.")
    st.markdown("#### 💾 Save & settings")
    st.caption("The page forgets progress when refreshed. Download a save file and load it back anytime.")
    st.download_button("💾 Download save file", data=export_save(), file_name="dead_zone_save.json", mime="application/json", use_container_width=True)
    up = st.file_uploader("Load a save file", type=["json"], key="save_upload")
    if up is not None:
        sig = (up.name, up.size)
        if s.get("_last_import") != sig:
            ok, msg = import_save(up.getvalue().decode("utf-8", errors="ignore"))
            s["_last_import"] = sig
            (st.success if ok else st.error)(msg)
            if ok:
                st.rerun()
    with st.expander("⚠️ Reset game"):
        if st.checkbox("Yes, delete all my progress", key="confirm_reset"):
            st.button("Reset everything", on_click=reset_game, key="do_reset")
    with st.expander("🛠️ Integration contract for Members 3 and 4"):
        st.code('''from survival import initialize_survival_state, change_resource, add_event, reward_xp
initialize_survival_state()
change_resource("food", 2, "supermarket mission reward")
change_resource("health", -12, "zombie encounter")
change_resource("medicine", 1, "hospital reward")
reward_xp(25, "mission completed")''', language="python")
        st.caption("Initialize before reading shared keys. Never reset default values on every rerun.")


def show_celebrations():
    """Pop-ups / balloons queued by any module (call once per page run)."""
    initialize_survival_state()
    s = st.session_state
    cur_level = level_info(s.xp)[0]
    if cur_level > s.last_level:
        _toast(f"🎉 LEVEL UP! You reached level {cur_level} ({rank_for(s.xp)})")
        s.pending_balloons = True
        s.last_level = cur_level
    for message in (s.pending_toast if isinstance(s.pending_toast, list) else []):
        st.toast(message)
    s.pending_toast = []
    if s.pending_balloons:
        st.balloons()
        s.pending_balloons = False


def render_survival_dashboard():
    """Main entry point - call from the main app's navigation."""
    initialize_survival_state()
    s = st.session_state
    st.markdown(CSS, unsafe_allow_html=True)
    show_celebrations()
    _hud()
    tabs = st.tabs(["🏠 Base", "🔧 Workshop", "🎯 Daily Ops", "🏆 Awards", "📊 Stats & Save"])
    with tabs[0]: _tab_base()
    with tabs[1]: _tab_workshop()
    with tabs[2]: _tab_daily()
    with tabs[3]: _tab_awards()
    with tabs[4]: _tab_stats()


if __name__ == "__main__":
    st.set_page_config(page_title="Dead Zone - Survival", page_icon="🧟", layout="wide")
    render_survival_dashboard()
