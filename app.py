"""
DEAD ZONE - combined app (Member 2 edition).   Run:  streamlit run app.py

Integrated build: survival.py (Member 2), missions.py (Member 3), exploration_ui.py (Member 4).
home.py (Member 1) is used automatically if present; otherwise the built-in landing page is shown.
"""
import importlib
import streamlit as st
from survival import initialize_survival_state, render_survival_dashboard, show_celebrations, level_info, rank_for, PHASES, phase_index

st.set_page_config(page_title="Dead Zone | Arcade Arenas", page_icon="🧟", layout="wide")
initialize_survival_state()
s = st.session_state
show_celebrations()

CANDIDATES = {
    "home": ["render_home", "show_home", "home_page", "main", "app"],
    "missions": ["render_missions"],
    "exploration_ui": ["render_exploration"],
}


def load_module(name):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as exc:
        if exc.name == name:
            return None
        raise


def render_external(name, label):
    mod = load_module(name)
    if mod is None:
        st.info(f"{label} isn't connected yet. Put `{name}.py` next to app.py and it will appear here.")
        return
    for fn_name in CANDIDATES[name]:
        fn = getattr(mod, fn_name, None)
        if callable(fn):
            fn()
            return
    st.warning(f"`{name}.py` loaded, but none of {CANDIDATES[name]} exists. Edit CANDIDATES in app.py.")


def landing():
    st.markdown("""<style>
    .dz-land{padding:2.6rem 2rem;border-radius:24px;border:1px solid #5c1a24;text-align:center;
     background:radial-gradient(circle at 50% 0%,rgba(255,77,109,.28),transparent 55%),linear-gradient(160deg,#120707,#2b0f14 60%,#0b0507)}
    .dz-land .tag{color:#ff8fa3;letter-spacing:4px;font-weight:800;font-size:.75rem}
    .dz-land h1{font-size:3.6rem;margin:.5rem 0;letter-spacing:6px;color:#fff;text-shadow:0 0 28px rgba(255,77,109,.7)}
    .dz-land p{color:#d6bcc0;max-width:680px;margin:0 auto;font-size:1.05rem}
    .dz-feat{padding:16px;border-radius:16px;background:#16090c;border:1px solid #3a1a20;height:100%}
    </style>
    <div class="dz-land"><div class="tag">ARCADE ARENAS · BUILD. BATTLE. PLAY.</div>
    <h1>DEAD ZONE</h1><h3 style="color:#ff8fa3">Survive the fall. Become the hope.</h3>
    <p>The city has fallen. Scavenge supplies, craft gear, upgrade your safehouse, complete missions
    and make it through the night. Every decision counts.</p></div>""", unsafe_allow_html=True)
    st.write("")
    feats = [("🩺", "Survival Command", "Manage health, stamina, food and medkits through a day/night cycle."),
             ("📦", "Loot & Craft", "Search caches of four rarities, craft medkits and rations."),
             ("🏗️", "Upgrade", "Fortify walls, grow a garden, add a med bay and radio tower."),
             ("🎯", "Daily Ops", "New objectives and a growing supply-drop streak every day."),
             ("🏆", "Level up", "Earn XP, climb ranks and unlock awards."),
             ("💾", "Save anywhere", "Download your progress and pick up where you left off.")]
    for row in (feats[:3], feats[3:]):
        for col, (icon, title, text) in zip(st.columns(3), row):
            col.markdown(f'<div class="dz-feat"><div style="font-size:1.8rem">{icon}</div><b>{title}</b><br>'
                         f'<span style="color:#b08a90;font-size:.88rem">{text}</span></div>', unsafe_allow_html=True)
        st.write("")
    if st.button("▶  ENTER THE SAFEHOUSE", type="primary", use_container_width=True):
        s.game_started = True
        s.last_reward = {"text": "Welcome to the safehouse. Check your vitals before heading out.", "kind": "success"}
        s.pending_toast = ["🏚️ Safehouse unlocked. Open Survival Command in the sidebar."]
        st.rerun()
    if s.game_started:
        st.success("Safehouse unlocked. Select **Survival Command** in the sidebar.")


def how_to_play():
    st.title("📖 How to Play")
    st.markdown("""
**Goal:** stay alive, grow stronger and climb from *Rookie* to *Dead Zone Legend*.

1. **Watch your vitals.** Health and stamina drain as you act; food, medkits and supplies fix that.
2. **Time passes.** Every few actions the day moves Dawn → Midday → Dusk → Night. Searching at night is risky.
3. **Search caches** for Common, Rare, Epic or Legendary loot (costs 1 supply and 10 stamina).
4. **Craft & upgrade** in the Workshop. Upgrades are permanent.
5. **Sleep until dawn** to heal, harvest your garden and start a new day with fresh Daily Ops.
6. **Claim the daily supply drop** every day to build a streak.
7. **Run missions** (Missions tab) for big XP, stars and achievements.
""")


PAGES = ["🏠 Home", "🩺 Survival Command", "🎯 Missions", "🗺️ Explore", "📖 How to Play"]
with st.sidebar:
    st.title("🧟 DEAD ZONE")
    page = st.radio("OPERATIONS", PAGES, label_visibility="collapsed")
    st.divider()
    level, into, need = level_info(s.xp)
    st.caption(f"{rank_for(s.xp)} · Level {level} · Day {s.day} {PHASES[phase_index()][0]}")
    st.progress(max(0.0, min(1.0, s.health / 100)), text=f"❤️ {s.health}/100")
    st.progress(max(0.0, min(1.0, s.stamina / 100)), text=f"⚡ {s.stamina}/100")
    st.write(f"🥫 {s.food} · 🧪 {s.medicine} · 📦 {s.supplies}")
    st.caption("Prototype build · Arcade Arenas")

if page == PAGES[0]:
    mod = load_module("home")
    if mod is None:
        landing()
    else:
        render_external("home", "Home")
elif page == PAGES[1]:
    render_survival_dashboard()
elif page == PAGES[2]:
    render_external("missions", "Missions")
elif page == PAGES[3]:
    render_external("exploration_ui", "Exploration")
else:
    how_to_play()
