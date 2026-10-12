"""Dead Zone exploration engine — Member 4 module.
Compatible with the Member 2 shared state keys when available.
"""
import random
from datetime import datetime

LOCATIONS = {
    "Abandoned Hospital": {
        "emoji": "🏥", "tagline": "Medical Wing", "danger": "HIGH", "danger_score": 82,
        "encounter_chance": 0.68, "stamina_cost": 12,
        "description": "Emergency lights flicker across abandoned wards. Medical supplies may still be locked inside.",
        "supplies": ["Medicine", "First Aid Kit", "Medicine", "Bandage"],
        "reward_xp": (12, 24), "color": "#d58b73",
    },
    "Rusted Supermarket": {
        "emoji": "🛒", "tagline": "Supply District", "danger": "MEDIUM", "danger_score": 53,
        "encounter_chance": 0.42, "stamina_cost": 9,
        "description": "A looted grocery store with a few sealed shelves and plenty of dark corners.",
        "supplies": ["Food", "Water", "Food", "Canned Beans"],
        "reward_xp": (8, 18), "color": "#d9b66c",
    },
    "Safehouse Outpost": {
        "emoji": "🏚️", "tagline": "Low-risk Zone", "danger": "LOW", "danger_score": 18,
        "encounter_chance": 0.16, "stamina_cost": 5,
        "description": "A boarded-up shelter with a chance to find water, tools, or a quiet moment to recover.",
        "supplies": ["Water", "Blanket", "Scrap Metal", "Water"],
        "reward_xp": (5, 12), "color": "#81bd8b",
    },
    "Underground Metro": {
        "emoji": "🚇", "tagline": "Transit Tunnels", "danger": "EXTREME", "danger_score": 94,
        "encounter_chance": 0.78, "stamina_cost": 16,
        "description": "Echoes travel far in the flooded tunnels. Rare gear may be worth the risk.",
        "supplies": ["Scrap Metal", "Flare", "Medicine", "Battery Pack"],
        "reward_xp": (18, 32), "color": "#c18be0",
    },
    "Police Checkpoint": {
        "emoji": "🚧", "tagline": "Restricted Sector", "danger": "HIGH", "danger_score": 75,
        "encounter_chance": 0.61, "stamina_cost": 13,
        "description": "An abandoned checkpoint. Protective gear and useful equipment could remain in the lockers.",
        "supplies": ["Protective Gear", "Flare", "Scrap Metal", "First Aid Kit"],
        "reward_xp": (14, 26), "color": "#82a9d8",
    },
}


# --- integration with Member 2's survival.py (falls back to plain dicts if absent) -------------
try:
    import survival as _sv
except Exception:  # standalone use / tests
    _sv = None

_CAPS = dict(_sv.MAX) if _sv else {"health": 100, "food": 25, "medicine": 15, "supplies": 30, "stamina": 100}
_POCKET = {"Bandage": "bandage", "Water": "water", "Scrap Metal": "scrap"}   # -> Member 2 backpack keys
_INV_CAP = 20


def _is_live_state(state):
    return _sv is not None and state is getattr(_sv.st, "session_state", None)


def _give_xp(state, xp):
    if _is_live_state(state):
        _sv.reward_xp(xp, "city exploration")          # level-ups, radio bonus, activity feed
    else:
        state["xp"] = max(0, int(state.get("xp", state.get("score", 0))) + xp)
        if "score" in state:
            state["score"] = int(state.get("score", 0)) + xp


def _add(state, key, amount):
    state[key] = max(0, min(_CAPS.get(key, 99), int(state.get(key, 0)) + amount))


def _apply_loot(state, supply):
    inv = state.get("inventory")
    if not isinstance(inv, dict):
        inv = {}
        state["inventory"] = inv
    if supply == "Medicine":
        _add(state, "medicine", 1)
    elif supply == "First Aid Kit":
        _add(state, "medicine", 2)
        _add(state, "health", 8)
    elif supply == "Food":
        _add(state, "food", 1)
    elif supply == "Canned Beans":
        _add(state, "food", 2)
    elif supply in _POCKET:
        key = _POCKET[supply]
        inv[key] = min(_INV_CAP, int(inv.get(key, 0)) + 1)
        if supply == "Scrap Metal":
            _add(state, "supplies", 1)
    else:                                   # Flare, Battery Pack, Protective Gear, Blanket ...
        _add(state, "supplies", 2)
        inv[supply] = int(inv.get(supply, 0)) + 1


def _log(state, text):
    if _is_live_state(state):
        _sv.add_event(text)
        return
    activity = state.get("activity")
    if isinstance(activity, list):
        activity.insert(0, f"{datetime.now().strftime('%H:%M')} · {text}")
        del activity[12:]

def _get(state, key, default):
    try:
        return state.get(key, default)
    except Exception:
        return default

def explore_location(location_name, state=None, rng=None):
    """Resolve one exploration run and return a structured outcome.

    `state` is optional. Pass st.session_state for direct shared-state integration.
    Reward prevention is handled by the UI via per-run action, not by blocking repeat visits.
    """
    rng = rng or random
    if location_name not in LOCATIONS:
        raise ValueError(f"Unknown location: {location_name}")
    loc = LOCATIONS[location_name]
    if state is not None:
        health = int(_get(state, "health", 100))
        stamina = int(_get(state, "stamina", 100))
        if health <= 0:
            return {"ok": False, "location": location_name, "message": "Your survivor is down. Open Survival Command and revive first.", "encounter": False, "damage": 0, "supply": None, "xp": 0}
        if stamina < loc["stamina_cost"]:
            return {"ok": False, "location": location_name, "message": f"Not enough stamina. This expedition costs {loc['stamina_cost']} stamina.", "encounter": False, "damage": 0, "supply": None, "xp": 0}
        state["stamina"] = max(0, stamina - loc["stamina_cost"])
    encounter = rng.random() < loc["encounter_chance"]
    damage = rng.randint(8, 24) if encounter else 0
    supply = rng.choice(loc["supplies"])
    xp = rng.randint(*loc["reward_xp"])
    outcome = {
        "ok": True, "location": location_name, "encounter": encounter,
        "damage": damage, "supply": supply, "xp": xp,
        "stamina_cost": loc["stamina_cost"], "danger": loc["danger"],
        "event": rng.choice([
            "You hear footsteps behind a metal door.",
            "A radio crackles once, then falls silent.",
            "Dust shifts in the beam of your flashlight.",
            "You discover fresh tracks near the exit.",
            "A distant alarm draws the infected away.",
        ]),
    }
    if state is not None:
        state["health"] = max(0, int(_get(state, "health", 100)) - damage)
        _give_xp(state, xp)
        _apply_loot(state, supply)
        state["total_loot"] = int(_get(state, "total_loot", 0)) + 1
        state["runs"] = int(_get(state, "runs", 0)) + 1
        explored = state.get("explored")
        if not isinstance(explored, list):
            explored = []
            state["explored"] = explored
        if location_name not in explored:
            explored.append(location_name)
        _log(state, f"Explored {location_name}: {supply}, +{xp} XP" + (f" · ambush -{damage} HP" if encounter else ""))
    return outcome

def apply_exploration_reward(state, outcome):
    """Use this only if the caller used explore_location(..., state=None).
    Do not call when state was passed to explore_location, because rewards are already applied.
    """
    if not outcome or not outcome.get("ok"):
        return
    state["health"] = max(0, int(state.get("health", 100)) - int(outcome.get("damage", 0)))
    state["xp"] = int(state.get("xp", state.get("score", 0))) + int(outcome.get("xp", 0))
    supply = outcome.get("supply")
    inv = state.setdefault("inventory", [])
    if isinstance(inv, list): inv.append(supply)
    elif isinstance(inv, dict): inv[supply] = int(inv.get(supply, 0)) + 1
    state["total_loot"] = int(state.get("total_loot", 0)) + 1
