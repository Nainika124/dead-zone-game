# DEAD ZONE - Zombie Survival (Arcade Arenas) - integrated build

| Part | File | Owner |
|---|---|---|
| Main app + navigation + home page | `app.py` | integration |
| Survival dashboard, crafting, upgrades, daily ops | `survival.py` | Member 2 |
| Missions & scoring | `missions.py` | Member 3 |
| City exploration | `exploration.py`, `exploration_ui.py` | Member 4 |
| Home page | `home.py` (optional - used automatically if present) | Member 1 |

Run locally: `pip install -r requirements.txt` then `streamlit run app.py`
Tests: `python test_survival.py`, `python test_missions.py`, `python test_integration.py`

## Put it online (get the prototype link)

### Option A - Render (what your classmate used)
1. Create a GitHub repo and upload ALL files in this folder (drag & drop on github.com -> "Add file" -> "Upload files").
2. render.com -> New + -> **Web Service** -> connect the repo.
3. Runtime **Python 3**, Build command: `pip install -r requirements.txt`
4. Start command: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`
5. Instance type **Free** -> Create. After ~3-5 minutes you get `https://<name>.onrender.com`.
   (Free plan sleeps when idle: the first open can take about a minute. Open it once before submitting.)
(`render.yaml` is included, so "New + -> Blueprint" also works.)

### Option B - Streamlit Community Cloud (usually faster)
share.streamlit.io -> sign in with GitHub -> New app -> pick the repo, branch `main`, main file `app.py` -> Deploy.

## Notes
- Progress is per-visitor and lost on refresh; Survival Command -> "Stats & Save" has a save file.
- If Member 1's `home.py` has a function `render_home()` (or `show_home`, `home_page`, `main`, `app`) it replaces the built-in landing page.
