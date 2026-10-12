"""Streamlit UI for Member 4 city exploration. Import render_exploration() in the main app."""
import streamlit as st
from exploration import LOCATIONS, explore_location

def _init():
    defaults = {
        "health": 88, "stamina": 82, "food": 7, "medicine": 3, "supplies": 10,
        "xp": 0, "score": 0, "inventory": {}, "explored": [], "activity": [],
        "total_loot": 0, "runs": 0, "exploration_last_result": None,
        "exploration_achievements": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value.copy() if isinstance(value, (dict, list)) else value

def _style():
    st.markdown("""
    <style>
    .explore-hero{padding:1.4rem 1.6rem;border:1px solid #3c5943;border-radius:18px;background:radial-gradient(circle at 90% 15%,#304c37 0%,transparent 35%),linear-gradient(120deg,#111b15,#203528);margin-bottom:1rem}
    .explore-kicker{font-size:.72rem;letter-spacing:2px;font-weight:800;color:#a8edaa}
    .explore-hero h2{font-size:2rem;color:#f2fff3;margin:.3rem 0}
    .explore-hero p{color:#bfd0c2;margin:0}
    .loc-card{border:1px solid #354c3a;background:linear-gradient(145deg,#19271e,#111a14);border-radius:16px;padding:1rem;min-height:155px}
    .loc-name{font-size:1.04rem;font-weight:800;color:#eff8f0}
    .loc-sub{font-size:.76rem;letter-spacing:1px;color:#9fb5a4;text-transform:uppercase}
    .loc-desc{font-size:.85rem;color:#bfd0c2}
    .explore-hero{background:radial-gradient(circle at 92% 0%,rgba(255,77,109,.22),transparent 40%),linear-gradient(135deg,#1a0a0a,#2b0f14 55%,#120808)!important;border:1px solid #5c1a24!important;box-shadow:0 0 30px rgba(255,40,70,.14)}
    .explore-kicker{color:#ff8fa3!important}
    .loc-card{background:linear-gradient(145deg,#1b0d11,#140a0d)!important;border:1px solid #3a1a20!important;transition:transform .15s ease,box-shadow .15s ease}
    .loc-card:hover{transform:translateY(-3px);box-shadow:0 8px 22px rgba(255,77,109,.2)}
    .loc-sub{color:#c9a9ae!important}.loc-desc{color:#d6bcc0!important}
    </style>""", unsafe_allow_html=True)

def render_exploration():
    _init()
    _style()
    st.markdown('<div class="explore-hero"><div class="explore-kicker">DEAD ZONE / CITY INTELLIGENCE</div><h2>Explore the Quarantine Zone</h2><p>Choose your route. Weigh the risk. Bring something useful back to the safehouse.</p></div>', unsafe_allow_html=True)
    m1,m2,m3,m4=st.columns(4)
    m1.metric("❤️ Health", f'{st.session_state.health}/100')
    m2.metric("⚡ Stamina", f'{st.session_state.stamina}/100')
    m3.metric("⭐ Survival XP", st.session_state.get("xp", st.session_state.get("score", 0)))
    m4.metric("📍 Locations found", f'{len(st.session_state.explored)}/{len(LOCATIONS)}')
    st.markdown("### 📡 Available sectors")
    cols=st.columns(3)
    for i,(name,loc) in enumerate(LOCATIONS.items()):
        with cols[i%3]:
            st.markdown(f'<div class="loc-card"><div class="loc-sub">{loc["tagline"]}</div><div class="loc-name">{loc["emoji"]} {name}</div><p class="loc-desc">{loc["description"]}</p><b style="color:{loc["color"]}">● {loc["danger"]} DANGER</b><br><span style="color:#9fb5a4;font-size:.8rem">Stamina cost: {loc["stamina_cost"]} · Loot: {", ".join(loc["supplies"][:2])}</span></div>', unsafe_allow_html=True)
            if name in st.session_state.explored:
                st.caption("✓ Previously explored")
    st.markdown("### 🧭 Plan an expedition")
    selected=st.selectbox("Select destination", list(LOCATIONS.keys()), key="m4_destination")
    loc=LOCATIONS[selected]
    st.info(f'{loc["emoji"]} **{selected}** — {loc["danger"]} danger · {int(loc["encounter_chance"]*100)}% estimated encounter chance · {loc["stamina_cost"]} stamina required.')
    st.caption("Possible loot: " + " • ".join(loc["supplies"]))
    if st.button("🚨 Explore selected location", type="primary", use_container_width=True):
        result=explore_location(selected, state=st.session_state)
        st.session_state.exploration_last_result=result
        if not result.get("ok"):
            st.warning(result.get("message","Unable to explore."))
        else:
            if result["encounter"]:
                st.session_state.exploration_last_result["headline"]="🧟 Ambush!"
            else:
                st.session_state.exploration_last_result["headline"]="🟢 Route clear"
            st.rerun()
    result=st.session_state.exploration_last_result
    if result:
        st.markdown("### 📟 Expedition report")
        if not result.get("ok"):
            st.warning(result.get("message","Unable to explore."))
        else:
            if result["encounter"]:
                st.error(f'🧟 Zombie encounter! You lost {result["damage"]} health.')
            else:
                st.success("🟢 No zombie encounter this time.")
            st.markdown(f'**Loot recovered:** 🎒 {result["supply"]}  ·  **XP earned:** ⭐ +{result["xp"]}')
            st.caption("Field intel: " + result.get("event",""))
            if st.session_state.health < 35:
                st.warning("Critical health. Return to the dashboard and heal before another expedition.")
            elif st.session_state.stamina < 15:
                st.warning("Stamina is low. Rest or consume food before continuing.")
    with st.expander("🎒 Recovered inventory"):
        inv=st.session_state.inventory
        if isinstance(inv, dict):
            if inv:
                for item,count in inv.items(): st.write(f"• {item}: **{count}**")
            else: st.caption("No recovered items yet.")
        elif inv:
            for item in inv[-12:]: st.write(f"• {item}")
        else:
            st.caption("No recovered items yet.")
    with st.expander("🧩 Integration notes for the main app"):
        st.code('from exploration_ui import render_exploration\n# In your main app navigation:\nrender_exploration()', language="python")
        st.caption("Keep a single shared Streamlit session state. Do not initialize/reset the same player values separately in every module.")
