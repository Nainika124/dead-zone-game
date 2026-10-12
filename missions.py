"""
DEAD ZONE  -  Member 3: Missions & Scoring System
=================================================
Day 1 : 3 interactive missions, player choices, success/failure outcomes.
Day 2 : scoring, XP, ranks, stars, combo streak, random events,
        mission-completion tracking, scoreboard, achievements,
        integration with Member 2's survival dashboard.

Integration (one line in the main app):
    import missions
    missions.render_missions()

SHARED STATE  (same keys Member 2's dashboard uses, all in st.session_state)
    health, stamina, food, medicine, supplies, xp
Missions only ever *add to / subtract from* these values, so the dashboard
updates automatically. Nothing is overwritten if it already exists.
"""
import copy
import random

try:  # the engine below works (and is unit-tested) even without Streamlit
    import streamlit as st
except ImportError:  # pragma: no cover
    st = None

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------
MAX_VALUES = {"health": 100, "stamina": 100, "food": 99, "medicine": 99, "supplies": 99}
RESOURCE_KEYS = list(MAX_VALUES)

# Use Member 2's real caps + activity log when survival.py is present
try:
    import survival as _survival
    MAX_VALUES.update({k: v for k, v in _survival.MAX.items() if k in MAX_VALUES})
except Exception:  # standalone use / tests
    _survival = None


def _log(text):
    """Write to Member 2's safehouse activity feed if available."""
    try:
        if _survival is not None:
            _survival.add_event(text)
    except Exception:
        pass

RESOURCE_ICONS = {"health": "❤️", "stamina": "⚡", "food": "🥫", "medicine": "💊", "supplies": "🧰"}

DEFAULT_SHARED = {
    "health": 100, "stamina": 100, "food": 5, "medicine": 3, "supplies": 5, "xp": 0,
}
DEFAULT_MISSION_STATE = {
    "score": 0,
    "streak": 0,
    "best_streak": 0,
    "attempts": 0,
    "completed_missions": [], # mission ids completed (same key Member 2 reads)
    "best": {},               # mission id -> {"points": int, "stars": int}
    "history": [],            # list of finished runs
    "mission_achievements": [],  # unlocked mission-achievement ids
    "run": None,              # the active run (dict) or None
    "last_result": None,      # result of the most recent run
}
MIN_STAMINA_TO_START = 15
START_STAMINA_COST = 10
PASS_MAX_FAILS = 1            # 2 failed stages = mission failed
EVENT_CHANCE = 0.40
STAGE_POINTS = 100
COMPLETE_BONUS = 250

# ----------------------------------------------------------------------------
# MISSION DATA   (edit text / numbers here - no logic changes needed)
# chance = base success probability.  Effects are deltas to shared stats.
# ----------------------------------------------------------------------------
MISSIONS = {
    "medicine": {
        "icon": "💊", "title": "Operation: Last Dose", "location": "St. Mary's Hospital",
        "difficulty": "Medium", "color": "#ff4d6d",
        "brief": "Your safehouse is out of antibiotics. The old hospital pharmacy is the only place left "
                 "that might still have some. The hallways are crawling with the infected.",
        "stages": [
            {"title": "The Hospital Entrance",
             "text": "The lobby doors hang open. Groans echo from the east wing. A stretcher blocks the stairwell.",
             "choices": [
                 {"label": "Sneak through the side door", "risk": "Low", "chance": 0.80,
                  "success": "You slip in unnoticed and reach the pharmacy corridor.",
                  "fail": "A rusty hinge screams. Zombies turn your way and you fight your way in.",
                  "ok_fx": {"stamina": -5}, "fail_fx": {"health": -15, "stamina": -10}},
                 {"label": "Smash through the front doors", "risk": "High", "chance": 0.55,
                  "success": "You barrel through and the horde is too slow to react. Bold move.",
                  "fail": "The noise draws a swarm. You escape bleeding.",
                  "ok_fx": {"stamina": -5}, "fail_fx": {"health": -30, "stamina": -15},
                  "bonus": 40},
                 {"label": "Throw a flare to distract them", "risk": "Medium", "chance": 0.70, "cost": {"supplies": 1},
                  "success": "The flare lures the zombies away. The path is clear.",
                  "fail": "The flare fizzles and lands at your feet. You scramble inside.",
                  "ok_fx": {}, "fail_fx": {"health": -10}},
             ]},
            {"title": "The Pharmacy",
             "text": "Shelves are ransacked, but the locked drug cabinet behind the counter looks untouched.",
             "choices": [
                 {"label": "Pick the lock carefully", "risk": "Medium", "chance": 0.65,
                  "success": "Click. The cabinet opens - rows of untouched medicine.",
                  "fail": "The pick snaps and you lose precious time.",
                  "ok_fx": {"medicine": 3}, "fail_fx": {"stamina": -10}},
                 {"label": "Break the glass", "risk": "High", "chance": 0.60,
                  "success": "Glass shatters but nothing comes. You grab everything.",
                  "fail": "The crash echoes through the building. You snatch a little and run.",
                  "ok_fx": {"medicine": 4}, "fail_fx": {"medicine": 1, "health": -15}, "bonus": 30},
                 {"label": "Search the shelves instead", "risk": "Low", "chance": 0.85,
                  "success": "Behind the counter you find a few forgotten bottles.",
                  "fail": "Mostly empty boxes. You find one bandage roll.",
                  "ok_fx": {"medicine": 2}, "fail_fx": {"medicine": 1}},
             ]},
            {"title": "Escape Route",
             "text": "Your bag is heavy with medicine, but footsteps thunder behind you. Time to leave.",
             "choices": [
                 {"label": "Run for the main exit", "risk": "Medium", "chance": 0.65,
                  "success": "You burst into daylight with the horde behind you.",
                  "fail": "Something grabs your leg - you rip free but it hurts.",
                  "ok_fx": {"stamina": -10}, "fail_fx": {"health": -20, "stamina": -10}},
                 {"label": "Climb out via the fire escape", "risk": "Low", "chance": 0.75,
                  "success": "A quiet climb and a safe drop to the alley below.",
                  "fail": "You slip on the rusty rungs and land hard.",
                  "ok_fx": {"stamina": -10}, "fail_fx": {"health": -15}},
                 {"label": "Hide in the morgue until it's quiet", "risk": "Low", "chance": 0.70,
                  "success": "Cold, creepy - but the horde wanders off.",
                  "fail": "You hear scratching from a drawer... you leave in a hurry.",
                  "ok_fx": {"food": -1}, "fail_fx": {"health": -10, "food": -1}},
             ]},
        ],
    },
    "food": {
        "icon": "🥫", "title": "Supply Run: Market Raid", "location": "Greenfield Supermarket",
        "difficulty": "Easy", "color": "#ffb703",
        "brief": "Rations are running low. The abandoned supermarket across the street still has "
                 "canned food in the back - if you can get past what is wandering the aisles.",
        "stages": [
            {"title": "The Parking Lot",
             "text": "Abandoned cars, a shopping cart rattling in the wind, and a few shuffling shapes.",
             "choices": [
                 {"label": "Move between cars quietly", "risk": "Low", "chance": 0.80,
                  "success": "You weave between the wrecks without a sound.",
                  "fail": "You step on broken glass. Two zombies lunge.",
                  "ok_fx": {"stamina": -5}, "fail_fx": {"health": -15}},
                 {"label": "Honk a car alarm to lure them", "risk": "Medium", "chance": 0.70,
                  "success": "The alarm wails and the zombies stumble toward it. You dash in.",
                  "fail": "More zombies than expected respond. You barely make it inside.",
                  "ok_fx": {}, "fail_fx": {"health": -20, "stamina": -10}},
             ]},
            {"title": "The Canned Goods Aisle",
             "text": "Shelves are mostly bare. A storeroom door at the back is slightly open.",
             "choices": [
                 {"label": "Check the storeroom", "risk": "Medium", "chance": 0.65,
                  "success": "Jackpot! Crates of canned food, still sealed.",
                  "fail": "Something was nesting in there. You grab a few cans and run.",
                  "ok_fx": {"food": 5}, "fail_fx": {"food": 2, "health": -15}, "bonus": 30},
                 {"label": "Scavenge the shelves", "risk": "Low", "chance": 0.85,
                  "success": "Slow and steady - you find a decent haul.",
                  "fail": "Mostly dented or expired cans, but something is better than nothing.",
                  "ok_fx": {"food": 3}, "fail_fx": {"food": 1}},
                 {"label": "Raid the cash-register area for supplies", "risk": "Low", "chance": 0.75,
                  "success": "Batteries, tape and a first-aid kit. Useful finds.",
                  "fail": "Empty drawers. A few coins and a lighter.",
                  "ok_fx": {"supplies": 3}, "fail_fx": {"supplies": 1}},
             ]},
            {"title": "The Way Back",
             "text": "Arms full, you head for the exit - and a lone, very large zombie blocks the doorway.",
             "choices": [
                 {"label": "Fight it", "risk": "High", "chance": 0.50,
                  "success": "A hard fight, but it goes down. Nothing can stop you now.",
                  "fail": "It hits like a truck. You escape but you're hurt.",
                  "ok_fx": {"stamina": -15}, "fail_fx": {"health": -30, "stamina": -15}, "bonus": 50},
                 {"label": "Sneak out the loading dock", "risk": "Low", "chance": 0.75,
                  "success": "The back door opens without a creak. Clean getaway.",
                  "fail": "The dock door is jammed - you lose time and energy forcing it.",
                  "ok_fx": {"stamina": -5}, "fail_fx": {"stamina": -15, "health": -10}},
             ]},
        ],
    },
    "rescue": {
        "icon": "🆘", "title": "Rescue: The Signal", "location": "Riverside Apartments",
        "difficulty": "Hard", "color": "#4cc9f0",
        "brief": "A radio crackles with a faint distress call: 'Anyone... trapped on the 4th floor...' "
                 "A survivor is alive in the Riverside Apartments. Nobody else is coming.",
        "stages": [
            {"title": "The Lobby",
             "text": "The elevator is dead, the lobby is dark, and you can hear movement above.",
             "choices": [
                 {"label": "Take the stairs quietly", "risk": "Medium", "chance": 0.70,
                  "success": "Step by careful step you climb past the sleeping infected.",
                  "fail": "A step creaks. You're spotted and forced to fight upward.",
                  "ok_fx": {"stamina": -10}, "fail_fx": {"health": -20, "stamina": -15}},
                 {"label": "Use the rope to climb the outside wall", "risk": "High", "chance": 0.55,
                  "success": "Daring! You reach the 4th-floor balcony in minutes.",
                  "fail": "Your grip slips halfway and you drop to a lower balcony.",
                  "ok_fx": {"stamina": -15}, "fail_fx": {"health": -25, "stamina": -15}, "bonus": 50, "cost": {"supplies": 1}},
             ]},
            {"title": "Apartment 4B",
             "text": "You find the door barricaded from the inside. A frightened voice whispers: 'Are you real?'",
             "choices": [
                 {"label": "Talk calmly to earn trust", "risk": "Low", "chance": 0.80,
                  "success": "The barricade moves. A tired survivor lets you in. Friend, not foe.",
                  "fail": "Panic. The survivor takes a swing at you before recognizing you.",
                  "ok_fx": {"stamina": -5}, "fail_fx": {"health": -10}},
                 {"label": "Offer food through the gap", "risk": "Low", "chance": 0.90, "cost": {"food": 1},
                  "success": "Hunger wins. The door opens, tears and thanks.",
                  "fail": "They grab the food but stay suspicious. You eventually convince them.",
                  "ok_fx": {}, "fail_fx": {"stamina": -5}},
                 {"label": "Break down the door", "risk": "High", "chance": 0.45,
                  "success": "The door gives way and you're inside before they can panic.",
                  "fail": "The racket draws zombies from the hall. Fight!",
                  "ok_fx": {"stamina": -10}, "fail_fx": {"health": -25, "stamina": -15}},
             ]},
            {"title": "Extraction",
             "text": "The survivor is weak. A pack of infected is converging on the building. Decide fast.",
             "choices": [
                 {"label": "Carry them to the roof for pickup", "risk": "High", "chance": 0.55,
                  "success": "Rooftop. A rope. Safe! You made it out together.",
                  "fail": "The roof access collapses under you both. You barely make it out.",
                  "ok_fx": {"stamina": -20}, "fail_fx": {"health": -30, "stamina": -20}, "bonus": 80},
                 {"label": "Sneak out the back way together", "risk": "Medium", "chance": 0.65,
                  "success": "A hidden service tunnel leads straight to safety.",
                  "fail": "A dead end. You fight back to the stairwell and escape together.",
                  "ok_fx": {"stamina": -10}, "fail_fx": {"health": -20, "stamina": -10}},
                 {"label": "Use a medkit to heal them, then run", "risk": "Low", "chance": 0.80, "cost": {"medicine": 1},
                  "success": "Healed and revitalized, they run beside you. Both of you escape.",
                  "fail": "The medkit helps, but you're slower than hoped. You make it by a hair.",
                  "ok_fx": {}, "fail_fx": {"health": -10}},
             ]},
        ],
    },
}
MISSION_ORDER = ["medicine", "food", "rescue"]

# Random events: the reason no two runs feel the same
RANDOM_EVENTS = [
    {"icon": "🎒", "text": "You find a hidden supply bag under a collapsed shelf.", "fx": {"supplies": 2}, "points": 20},
    {"icon": "🥫", "text": "A forgotten stash of canned beans!", "fx": {"food": 2}, "points": 20},
    {"icon": "💊", "text": "A medic's pouch lies beside a fallen soldier.", "fx": {"medicine": 1}, "points": 25},
    {"icon": "🧟", "text": "A lone zombie lunges from the shadows. You fend it off.", "fx": {"health": -12}, "points": 15},
    {"icon": "🌧️", "text": "Heavy rain soaks you through. It slows you down.", "fx": {"stamina": -10}, "points": 0},
    {"icon": "📻", "text": "A friendly radio broadcast lifts your spirits.", "fx": {"stamina": 10}, "points": 10},
    {"icon": "🚁", "text": "A distant helicopter passes - hope! You take a breath.", "fx": {"health": 8, "stamina": 5}, "points": 15},
    {"icon": "🪤", "text": "You trip an old tripwire trap. Ouch.", "fx": {"health": -10, "supplies": -1}, "points": 0},
    {"icon": "🍀", "text": "Lucky break: a safe room with a working water tap.", "fx": {"health": 10, "food": 1}, "points": 25},
    {"icon": "🔦", "text": "You find a flashlight. Dark corners just got safer.", "fx": {"stamina": 5, "supplies": 1}, "points": 15},
]

ACHIEVEMENTS = {
    "first_blood": ("🩸", "First Mission", "Finish your first mission."),
    "medic": ("💊", "Field Medic", "Complete Operation: Last Dose."),
    "provider": ("🥫", "Provider", "Complete the Market Raid."),
    "hero": ("🦸", "Hero", "Complete the Rescue mission."),
    "perfect": ("⭐", "Perfectionist", "Earn 3 stars on any mission."),
    "streak3": ("🔥", "Hot Streak", "Win 3 missions in a row."),
    "all_clear": ("🏆", "Dead Zone Legend", "Complete all three missions."),
    "score1000": ("💯", "Four Digits", "Reach a total score of 1000."),
    "survivor": ("🛡️", "Close Call", "Win a mission with less than 20 health."),
}

RANKS = [(0, "Rookie"), (150, "Scavenger"), (400, "Survivor"), (800, "Hunter"), (1500, "Dead Zone Legend")]


# ----------------------------------------------------------------------------
# ENGINE  (pure Python - works on any dict-like store, e.g. st.session_state)
# ----------------------------------------------------------------------------
def clamp(value, low, high):
    return max(low, min(high, value))


def ensure_state(store):
    """Create any missing keys. Never overwrites values Member 2 already set."""
    for key, value in DEFAULT_SHARED.items():
        if key not in store:
            store[key] = value
    for key, value in DEFAULT_MISSION_STATE.items():
        if key not in store:
            store[key] = copy.deepcopy(value)
    return store


def rank_for(xp):
    name = RANKS[0][1]
    for threshold, rank in RANKS:
        if xp >= threshold:
            name = rank
    return name


def next_rank_info(xp):
    for threshold, rank in RANKS:
        if xp < threshold:
            return rank, threshold
    return None, None


def apply_effects(store, effects):
    for key, delta in (effects or {}).items():
        if key in MAX_VALUES:
            store[key] = clamp(store.get(key, 0) + delta, 0, MAX_VALUES[key])


def can_afford(store, cost):
    return all(store.get(k, 0) >= v for k, v in (cost or {}).items())


def pay(store, cost):
    for k, v in (cost or {}).items():
        store[k] = max(0, store.get(k, 0) - v)


def can_start(store):
    if store.get("run"):
        return False, "Finish your current mission first."
    if store.get("stamina", 0) < MIN_STAMINA_TO_START:
        return False, f"Too tired - you need at least {MIN_STAMINA_TO_START} stamina. Rest or eat first."
    if store.get("health", 0) <= 0:
        return False, "You need to heal before heading out."
    return True, ""


def start_mission(store, mission_id):
    ensure_state(store)
    ok, msg = can_start(store)
    if not ok:
        return False, msg
    apply_effects(store, {"stamina": -START_STAMINA_COST})
    store["attempts"] += 1
    store["last_result"] = None
    store["run"] = {
        "id": mission_id, "stage": 0, "points": 0, "fails": 0, "successes": 0,
        "log": [], "status": "active",
        "start_health": store["health"],
    }
    return True, "Mission started."


def choice_chance(store, choice):
    """Base chance, nudged by how healthy and rested the player is."""
    chance = choice["chance"]
    if store.get("health", 100) < 30:
        chance -= 0.10
    if store.get("stamina", 100) < 25:
        chance -= 0.10
    if store.get("health", 100) >= 80 and store.get("stamina", 100) >= 80:
        chance += 0.05
    return clamp(chance, 0.10, 0.95)


def risk_label(chance):
    if chance >= 0.75:
        return "Low"
    if chance >= 0.60:
        return "Medium"
    return "High"


def current_stage(run):
    stages = MISSIONS[run["id"]]["stages"]
    return stages[run["stage"]] if run["stage"] < len(stages) else None


def make_choice(store, choice_index, rng=random):
    """Resolve one choice. Returns a dict describing what happened."""
    run = store["run"]
    stage = current_stage(run)
    choice = stage["choices"][choice_index]
    if not can_afford(store, choice.get("cost")):
        return {"ok": False, "message": "You can't afford that option right now."}
    pay(store, choice.get("cost"))

    success = rng.random() < choice_chance(store, choice)
    if success:
        apply_effects(store, choice["ok_fx"])
        points = STAGE_POINTS + choice.get("bonus", 0)
        run["successes"] += 1
        text = choice["success"]
    else:
        apply_effects(store, choice["fail_fx"])
        points = 25  # consolation points - the story always goes on
        run["fails"] += 1
        text = choice["fail"]
    # streak bonus inside a run keeps players chasing "one more perfect stage"
    if success and run["successes"] >= 2 and run["fails"] == 0:
        points += 20
    run["points"] += points
    result = {"ok": True, "success": success, "text": text, "points": points,
              "stage_title": stage["title"], "choice": choice["label"], "event": None}
    run["log"].append({"kind": "choice", "success": success, "title": stage["title"],
                       "choice": choice["label"], "text": text, "points": points})

    # random event between stages
    last_stage = run["stage"] >= len(MISSIONS[run["id"]]["stages"]) - 1
    if not last_stage and store["health"] > 0 and rng.random() < EVENT_CHANCE:
        event = rng.choice(RANDOM_EVENTS)
        apply_effects(store, event["fx"])
        run["points"] += event["points"]
        result["event"] = event
        run["log"].append({"kind": "event", "icon": event["icon"], "text": event["text"],
                           "points": event["points"]})

    run["stage"] += 1
    if store["health"] <= 0 or run["fails"] > PASS_MAX_FAILS:
        finish_mission(store, forced_fail=True)
    elif run["stage"] >= len(MISSIONS[run["id"]]["stages"]):
        finish_mission(store)
    return result


def stars_for(run, health):
    if run["fails"] == 0 and health >= 50:
        return 3
    if run["fails"] == 0:
        return 2
    return 1


def finish_mission(store, forced_fail=False):
    run = store["run"]
    mission_id = run["id"]
    won = (not forced_fail) and run["fails"] <= PASS_MAX_FAILS and store["health"] > 0
    result = {"mission_id": mission_id, "won": won, "points": run["points"],
              "stars": 0, "bonus": 0, "xp": 0, "log": run["log"], "new_achievements": [],
              "rescued": False}

    if won:
        stars = stars_for(run, store["health"])
        bonus = COMPLETE_BONUS + 100 * (stars - 1)
        store["streak"] += 1
        store["best_streak"] = max(store["best_streak"], store["streak"])
        combo = min(store["streak"] - 1, 4) * 25          # streak multiplier
        bonus += combo
        total = run["points"] + bonus
        xp = total // 2
        result.update({"stars": stars, "bonus": bonus, "points": total, "xp": xp, "combo": combo})
        store["score"] += total
        store["xp"] += xp
        store["supplies"] = clamp(store["supplies"] + 1, 0, MAX_VALUES["supplies"])   # mission reward
        if mission_id not in store["completed_missions"]:
            store["completed_missions"].append(mission_id)
        best = store["best"].get(mission_id, {"points": 0, "stars": 0})
        store["best"][mission_id] = {"points": max(best["points"], total),
                                     "stars": max(best["stars"], stars)}
    else:
        store["streak"] = 0
        if store["health"] <= 0:
            store["health"] = 15                          # a patrol drags you back alive
            store["supplies"] = max(0, store["supplies"] - 2)
            result["rescued"] = True
        consolation = run["points"] // 3
        result["points"] = consolation
        result["xp"] = consolation // 2
        store["score"] += consolation
        store["xp"] += result["xp"]

    store["history"].insert(0, {"mission": mission_id, "won": won, "points": result["points"],
                                "stars": result["stars"]})
    store["history"] = store["history"][:25]
    result["new_achievements"] = check_achievements(store, result)
    store["last_result"] = result
    store["run"] = None
    _log(("Mission complete: " if won else "Mission failed: ") + MISSIONS[mission_id]["title"] + f" (+{result['points']} pts)")
    return result


def check_achievements(store, result):
    unlocked = []

    def give(key, condition):
        if condition and key not in store["mission_achievements"]:
            store["mission_achievements"].append(key)
            unlocked.append(key)

    won = result["won"]
    give("first_blood", True)
    give("medic", won and result["mission_id"] == "medicine")
    give("provider", won and result["mission_id"] == "food")
    give("hero", won and result["mission_id"] == "rescue")
    give("perfect", won and result["stars"] == 3)
    give("streak3", store["streak"] >= 3)
    give("all_clear", all(m in store["completed_missions"] for m in MISSION_ORDER))
    give("score1000", store["score"] >= 1000)
    give("survivor", won and store["health"] < 20)
    return unlocked


def abandon_mission(store):
    """Giving up costs a little stamina and breaks the streak."""
    if store.get("run"):
        store["run"] = None
        store["streak"] = 0
        apply_effects(store, {"stamina": -5})


def reset_progress(store):
    for key, value in DEFAULT_MISSION_STATE.items():
        store[key] = copy.deepcopy(value)


def progress_percent(store):
    return int(100 * len(store["completed_missions"]) / len(MISSION_ORDER))


# ----------------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------------
CSS = """
<style>
.m3-hero{background:linear-gradient(135deg,#1a0a0a 0%,#2b0f14 50%,#120808 100%);
 border:1px solid #5c1a24;border-radius:18px;padding:22px 26px;margin-bottom:16px;
 box-shadow:0 0 30px rgba(255,40,70,.15)}
.m3-hero h1{margin:0;font-size:2rem;letter-spacing:2px;color:#ff4d6d}
.m3-hero p{margin:4px 0 0;color:#c9a9ae}
.m3-chip{display:inline-block;background:#241216;border:1px solid #4a2128;border-radius:999px;
 padding:4px 12px;margin:4px 6px 0 0;font-size:.85rem;color:#f2d4d8}
.m3-card{background:#16090c;border:1px solid #3a1a20;border-radius:16px;padding:16px;height:100%}
.m3-card h3{margin:.2rem 0;color:#fff}
.m3-card .loc{color:#b08a90;font-size:.85rem}
.m3-stars{font-size:1.3rem;letter-spacing:3px}
.m3-stage{background:#140a0d;border-left:4px solid #ff4d6d;border-radius:10px;padding:14px 18px;margin:10px 0}
.m3-ok{border-left:4px solid #2ecc71;background:#0e1f15;border-radius:10px;padding:10px 14px;margin:6px 0}
.m3-bad{border-left:4px solid #ff4d6d;background:#240e12;border-radius:10px;padding:10px 14px;margin:6px 0}
.m3-evt{border-left:4px solid #ffb703;background:#22190a;border-radius:10px;padding:10px 14px;margin:6px 0}
.m3-result{text-align:center;border-radius:18px;padding:26px;margin:10px 0}
.m3-win{background:linear-gradient(135deg,#0d2417,#143a22);border:1px solid #2ecc71}
.m3-lose{background:linear-gradient(135deg,#2a0c10,#3d1218);border:1px solid #ff4d6d}
.m3-big{font-size:2.4rem;font-weight:800}
.m3-badge{background:#1b1015;border:1px solid #3a1a20;border-radius:12px;padding:10px;text-align:center;height:100%}
.m3-badge.off{opacity:.35;filter:grayscale(1)}
</style>
"""


def _store():
    return st.session_state


def _stars(n):
    return "⭐" * n + "☆" * (3 - n)


def _hud(store):
    rank = rank_for(store["xp"])
    chips = "".join(f'<span class="m3-chip">{RESOURCE_ICONS[k]} {k.title()}: <b>{store[k]}</b></span>'
                    for k in RESOURCE_KEYS)
    chips += f'<span class="m3-chip">🏅 {rank}</span><span class="m3-chip">✨ XP: <b>{store["xp"]}</b></span>'
    chips += f'<span class="m3-chip">🎯 Score: <b>{store["score"]}</b></span>'
    if store["streak"] > 0:
        chips += f'<span class="m3-chip">🔥 Streak x{store["streak"]}</span>'
    st.markdown(
        f'<div class="m3-hero"><h1>🧟 MISSION BOARD</h1>'
        f'<p>Every choice has a price. Choose wisely, survivor.</p>{chips}</div>',
        unsafe_allow_html=True)
    nxt, need = next_rank_info(store["xp"])
    if nxt:
        st.progress(min(store["xp"] / need, 1.0), text=f"Next rank: {nxt} at {need} XP")
    st.progress(store["health"] / 100, text=f"❤️ Health {store['health']}/100")
    if store["health"] < 30:
        st.warning("⚠️ Health critical! Use a medkit on the Survival dashboard before another mission.")


def _mission_board(store):
    st.subheader("Choose your mission")
    st.caption(f"Campaign progress: {len(store['completed_missions'])}/{len(MISSION_ORDER)} missions complete")
    st.progress(progress_percent(store) / 100)
    cols = st.columns(len(MISSION_ORDER))
    for col, mid in zip(cols, MISSION_ORDER):
        m = MISSIONS[mid]
        best = store["best"].get(mid)
        done = mid in store["completed_missions"]
        with col:
            st.markdown(
                f'<div class="m3-card" style="border-top:4px solid {m["color"]}">'
                f'<div style="font-size:2.2rem">{m["icon"]}</div><h3>{m["title"]}</h3>'
                f'<div class="loc">📍 {m["location"]} · {m["difficulty"]}</div>'
                f'<p style="color:#d6bcc0;font-size:.9rem">{m["brief"]}</p>'
                f'<div class="m3-stars">{_stars(best["stars"]) if best else "☆☆☆"}</div>'
                f'<div class="loc">{"✅ Best: " + str(best["points"]) + " pts" if done else "Not completed yet"}</div></div>',
                unsafe_allow_html=True)
            ok, msg = can_start(store)
            if st.button(f"{'Replay' if done else 'Start'} mission", key=f"start_{mid}",
                         disabled=not ok, use_container_width=True):
                good, message = start_mission(store, mid)
                if good:
                    st.rerun()
                else:
                    st.error(message)
            if not ok:
                st.caption(msg)


def _log_view(run_or_log):
    for entry in run_or_log:
        if entry["kind"] == "choice":
            cls = "m3-ok" if entry["success"] else "m3-bad"
            icon = "✅" if entry["success"] else "❌"
            st.markdown(f'<div class="{cls}"><b>{icon} {entry["title"]}</b> - {entry["choice"]}<br>'
                        f'{entry["text"]} <b>+{entry["points"]}</b></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="m3-evt"><b>{entry["icon"]} Random event</b><br>{entry["text"]}'
                        f'{" <b>+" + str(entry["points"]) + "</b>" if entry["points"] else ""}</div>',
                        unsafe_allow_html=True)


def _active_mission(store):
    run = store["run"]
    m = MISSIONS[run["id"]]
    stage = current_stage(run)
    total = len(m["stages"])
    st.markdown(f"### {m['icon']} {m['title']}  ·  📍 {m['location']}")
    st.progress(run["stage"] / total, text=f"Stage {run['stage'] + 1} of {total}  ·  Points so far: {run['points']}")
    st.markdown(f'<div class="m3-stage"><b>{stage["title"]}</b><br>{stage["text"]}</div>',
                unsafe_allow_html=True)
    st.write("**What do you do?**")
    for i, ch in enumerate(stage["choices"]):
        chance = choice_chance(store, ch)
        afford = can_afford(store, ch.get("cost"))
        cost_txt = ""
        if ch.get("cost"):
            cost_txt = "  ·  costs " + ", ".join(f"{v} {k}" for k, v in ch["cost"].items())
        label = f"{ch['label']}   —   Risk: {risk_label(chance)}{cost_txt}"
        if st.button(label, key=f"choice_{run['id']}_{run['stage']}_{i}", disabled=not afford,
                     use_container_width=True):
            res = make_choice(store, i)
            if res.get("event"):
                st.toast(f"{res['event']['icon']} {res['event']['text']}")
            st.rerun()
    if run["log"]:
        with st.expander("Mission log", expanded=True):
            _log_view(run["log"])
    if st.button("🏳️ Abandon mission (breaks your streak)", key="abandon"):
        abandon_mission(store)
        st.rerun()


def _result_view(store):
    r = store["last_result"]
    m = MISSIONS[r["mission_id"]]
    if r["won"]:
        st.markdown(
            f'<div class="m3-result m3-win"><div class="m3-big">MISSION COMPLETE</div>'
            f'<div class="m3-stars" style="font-size:2.2rem">{_stars(r["stars"])}</div>'
            f'<p>{m["title"]}</p><div class="m3-big">+{r["points"]} pts</div>'
            f'<p>+{r["xp"]} XP · Completion bonus {r["bonus"]}'
            f'{" (includes streak combo +" + str(r.get("combo", 0)) + ")" if r.get("combo") else ""}'
            f' · +1 supplies reward</p></div>', unsafe_allow_html=True)
        if r["stars"] == 3:
            st.balloons()
    else:
        extra = " A patrol dragged you back barely alive (lost 2 supplies)." if r["rescued"] else ""
        st.markdown(
            f'<div class="m3-result m3-lose"><div class="m3-big">MISSION FAILED</div>'
            f'<p>{m["title"]}</p><p>Consolation: +{r["points"]} pts · +{r["xp"]} XP.{extra}</p>'
            f'<p>Your streak was reset. Heal up and try again - the dead aren\'t going anywhere.</p></div>',
            unsafe_allow_html=True)
    for key in r["new_achievements"]:
        icon, name, desc = ACHIEVEMENTS[key]
        st.success(f"🏆 Achievement unlocked: {icon} {name} — {desc}")
    with st.expander("See what happened"):
        _log_view(r["log"])
    if st.button("Back to mission board", key="back_board", use_container_width=True):
        store["last_result"] = None
        st.rerun()


def _scoreboard(store):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total score", store["score"])
    c2.metric("Rank", rank_for(store["xp"]))
    c3.metric("Best streak", store["best_streak"])
    c4.metric("Attempts", store["attempts"])
    st.subheader("Recent runs")
    if not store["history"]:
        st.info("No missions finished yet. Your story starts on the Mission Board.")
    for h in store["history"][:10]:
        m = MISSIONS[h["mission"]]
        st.write(f"{m['icon']} **{m['title']}** — {'✅ Win' if h['won'] else '❌ Failed'} · "
                 f"{h['points']} pts {_stars(h['stars']) if h['won'] else ''}")
    if st.button("Reset mission progress", key="reset_missions"):
        reset_progress(store)
        st.rerun()


def _achievements(store):
    st.caption(f"{len(store['mission_achievements'])}/{len(ACHIEVEMENTS)} unlocked")
    cols = st.columns(3)
    for i, (key, (icon, name, desc)) in enumerate(ACHIEVEMENTS.items()):
        on = key in store["mission_achievements"]
        with cols[i % 3]:
            st.markdown(f'<div class="m3-badge {"" if on else "off"}"><div style="font-size:1.8rem">{icon}</div>'
                        f'<b>{name}</b><br><span style="font-size:.8rem;color:#b08a90">{desc}</span></div>',
                        unsafe_allow_html=True)
            st.write("")


def render_missions():
    """Main entry point - call this from the main app's navigation."""
    store = _store()
    ensure_state(store)
    st.markdown(CSS, unsafe_allow_html=True)
    _hud(store)
    tab_board, tab_score, tab_ach = st.tabs(["🎯 Missions", "📊 Scoreboard", "🏆 Achievements"])
    with tab_board:
        if store["run"]:
            _active_mission(store)
        elif store["last_result"]:
            _result_view(store)
        else:
            _mission_board(store)
    with tab_score:
        _scoreboard(store)
    with tab_ach:
        _achievements(store)


if __name__ == "__main__":  # `streamlit run missions.py` also works on its own
    st.set_page_config(page_title="Dead Zone - Missions", page_icon="🧟", layout="wide")
    render_missions()
