# app.py
import os
import traceback
import streamlit as st

# --- Streamlit fast reload settings (optional/safe defaults) ---
os.environ.setdefault("STREAMLIT_SERVER_FILE_WATCHER_TYPE", "poll")
os.environ.setdefault("STREAMLIT_SERVER_RUN_ON_SAVE", "false")

st.set_page_config(page_title="LLM Commissioner", page_icon="🏈", layout="wide")
st.title("Fantasy Football Commissioner – Recaps & Weekly Preview")

# -------------------- Secrets/env bootstrap --------------------
def _maybe_env_from_secrets(key: str):
    try:
        if key in st.secrets and not os.getenv(key):
            os.environ[key] = str(st.secrets[key])
    except Exception:
        pass  # st.secrets may not exist locally

for _k in ("OPENAI_API_KEY", "ESPN_S2", "ESPN_SWID"):
    _maybe_env_from_secrets(_k)

# -------------------- Lazy imports so recap-only failures don't kill the app --------------------
recap_import_error = None
try:
    from espn_fetcher import get_week_matchups
    from gpt_summarizer import generate_week_recap
except Exception as e:
    recap_import_error = e

# Preview is separate and should not be blocked by recap imports
preview_import_error = None
try:
    from preview.preview_generator import build_weekly_preview
except Exception as e:
    preview_import_error = e

# -------------------- Sidebar --------------------
with st.sidebar:
    st.header("Optional ESPN Credentials")
    st.caption("Set these only if your league is private. Public leagues usually work without them.")

    # Use session_state so values persist nicely between reruns
    s2_default = os.getenv("ESPN_S2", "")
    swid_default = os.getenv("ESPN_SWID", "")

    if "ESPN_S2" not in st.session_state:
        st.session_state.ESPN_S2 = s2_default
    if "ESPN_SWID" not in st.session_state:
        st.session_state.ESPN_SWID = swid_default

    s2 = st.text_input("ESPN_S2", value=st.session_state.ESPN_S2, type="password")
    swid = st.text_input("ESPN_SWID", value=st.session_state.ESPN_SWID, type="password")

    if st.button("Save ESPN Credentials"):
        st.session_state.ESPN_S2 = s2 or ""
        st.session_state.ESPN_SWID = swid or ""
        if s2:
            os.environ["ESPN_S2"] = s2
        if swid:
            os.environ["ESPN_SWID"] = swid
        st.success("Saved for this session.")

    with st.expander("Diagnostics"):
        st.write({
            "OPENAI_API_KEY set?": bool(os.getenv("OPENAI_API_KEY")),
            "ESPN_S2 set?": bool(os.getenv("ESPN_S2")),
            "ESPN_SWID set?": bool(os.getenv("ESPN_SWID")),
            "Recap import error?": repr(recap_import_error) if recap_import_error else "None",
            "Preview import error?": repr(preview_import_error) if preview_import_error else "None",
        })

# -------------------- Helpers --------------------
def _render(text: str):
    """Render Markdown unless it's clearly HTML."""
    if "<" in text and ">" in text and "</" in text:
        st.components.v1.html(text, height=900, scrolling=True)
    else:
        st.markdown(text)

def _need_openai() -> bool:
    if not os.getenv("OPENAI_API_KEY"):
        st.error("Missing **OPENAI_API_KEY** — add it in Streamlit Secrets or as an environment variable.")
        return True
    return False

@st.cache_data(show_spinner=False, ttl=60)
def _fetch_matchups_cached(_league_id: int, _year: int, _week: int):
    return get_week_matchups(_league_id, _year, _week)

@st.cache_data(show_spinner=False, ttl=60)
def _build_preview_cached(_league_id: int, _year: int, _week: int, _s2: str | None, _swid: str | None):
    # pass None if empty strings
    s2 = _s2 or None
    swid = _swid or None
    return build_weekly_preview(int(_league_id), int(_year), int(_week), espn_s2=s2, swid=swid)

# -------------------- Unified inputs (used by both tabs) --------------------
st.subheader("Inputs")
with st.form("inputs_form"):
    c1, c2, c3 = st.columns(3)
    with c1:
        league_id = st.number_input("League ID", min_value=1, step=1, format="%d")
    with c2:
        year = st.number_input("Season (year)", min_value=2015, max_value=2100, value=2025, step=1)
    with c3:
        week = st.number_input("Week", min_value=1, max_value=18, value=1, step=1)
    submitted_inputs = st.form_submit_button("Use these inputs")
if not submitted_inputs:
    st.info("Set inputs above, then switch to a tab and run an action.")
st.caption("We’ll summarize **every matchup** for the selected week. ESPN cookies are optional for public leagues.")

# Pull cookies from session/env
espn_s2 = os.getenv("ESPN_S2") or st.session_state.get("ESPN_S2") or None
espn_swid = os.getenv("ESPN_SWID") or st.session_state.get("ESPN_SWID") or None

# -------------------- Tabs: Recap & Preview --------------------
tab_recap, tab_preview = st.tabs(["📝 Recap", "🔮 Weekly Preview"])

with tab_recap:
    st.subheader("Generate Weekly Recap")
    recap_disabled = (recap_import_error is not None) or (not bool(os.getenv("OPENAI_API_KEY")))
    with st.form("recap_form", clear_on_submit=False):
        run_recap = st.form_submit_button("Generate Weekly Recap", type="primary", disabled=recap_disabled)

        if recap_disabled:
            msgs = []
            if recap_import_error is not None:
                msgs.append("module import failure")
            if not bool(os.getenv("OPENAI_API_KEY")):
                msgs.append("OPENAI_API_KEY missing")
            st.info("Button disabled: " + ", ".join(msgs))

        if run_recap:
            if recap_import_error:
                st.error("Import failure: could not load recap module(s).")
                with st.expander("Import error details"):
                    st.code("".join(traceback.format_exception(type(recap_import_error), recap_import_error, recap_import_error.__traceback__)))
                st.stop()

            if not league_id or not year or not week:
                st.error("Please fill in League ID, Year, and Week.")
                st.stop()

            if _need_openai():
                st.stop()

            if not (espn_s2 and espn_swid):
                st.warning("No ESPN cookies found — public leagues may work; private leagues will not.")

            with st.spinner("Pulling ESPN data and writing recaps…"):
                try:
                    matchups = _fetch_matchups_cached(int(league_id), int(year), int(week))
                except Exception as e:
                    st.error("Failed while fetching ESPN data.")
                    with st.expander("Error details"):
                        st.code("".join(traceback.format_exception(type(e), e, e.__traceback__)))
                    st.stop()

                if not matchups:
                    st.warning("No matchups found for that week. Double-check league/week inputs.")
                    st.stop()

                with st.expander("Show raw matchup data"):
                    st.write(matchups)

                try:
                    # Support either summarizer signature
                    try:
                        recap = generate_week_recap(matchups, league_id=int(league_id), year=int(year), week=int(week))
                    except TypeError:
                        recap = generate_week_recap(matchups)
                except Exception as e:
                    st.error("LLM recap generation failed.")
                    with st.expander("Error details"):
                        st.code("".join(traceback.format_exception(type(e), e, e.__traceback__)))
                    st.stop()

            st.success("Recap generated!")
            _render(recap)

            st.download_button(
                "Download Recap (Markdown)",
                data=(recap or "").encode("utf-8"),
                file_name=f"weekly_recap_{league_id}_{year}_w{week}.md",
                mime="text/markdown",
            )

with tab_preview:
    st.subheader("Build Weekly Preview")
    if preview_import_error:
        st.error("Import failure: could not load preview module.")
        with st.expander("Import error details"):
            st.code("".join(traceback.format_exception(type(preview_import_error), preview_import_error, preview_import_error.__traceback__)))
    else:
        with st.form("preview_form", clear_on_submit=False):
            run_preview = st.form_submit_button("Build Weekly Preview", type="secondary")
            if run_preview:
                if not league_id or not year or not week:
                    st.error("Please fill in League ID, Year, and Week.")
                    st.stop()

                if not (espn_s2 and espn_swid):
                    st.info("No ESPN cookies found — trying without them (public leagues only).")

                with st.spinner("Computing projections and assembling preview…"):
                    try:
                        cards = _build_preview_cached(int(league_id), int(year), int(week), espn_s2, espn_swid)
                    except Exception as e:
                        st.error("Preview failed while fetching data.")
                        with st.expander("Error details"):
                            st.code("".join(traceback.format_exception(type(e), e, e.__traceback__)))
                        st.stop()

                if not cards:
                    st.warning("No matchups found for this week.")
                else:
                    for card in cards:
                        m = card["matchup"]
                        c1, c2 = st.columns(2)
                        with c1:
                            if m["home"]["logo"]:
                                st.image(m["home"]["logo"], width=80)
                            st.subheader(f"{m['home']['team_name']} ({m['home']['record']})")
                            st.caption(f"Owner: {m['home']['owner']} • Streak: {m['home']['streak']}")
                            st.write(f"Projected: **{m['home']['proj']:.2f}**")
                            st.write(m["home"]["top_players"])
                            st.info(f"Quote: {card['quotes']['home']}")
                        with c2:
                            if m["away"]["logo"]:
                                st.image(m["away"]["logo"], width=80)
                            st.subheader(f"{m['away']['team_name']} ({m['away']['record']})")
                            st.caption(f"Owner: {m['away']['owner']} • Streak: {m['away']['streak']}")
                            st.write(f"Projected: **{m['away']['proj']:.2f}**")
                            st.write(m["away"]["top_players"])
                            st.info(f"Quote: {card['quotes']['away']}")
                        fav = m["favorite"]
                        edge = m["edge_points"]
                        if fav == "Pick'em" or edge == 0:
                            st.success("Headline: Pick'em")
                        else:
                            st.success(f"Headline: {fav} favored by {edge:.1f}")
                        st.write(card["blurb"])
                        st.divider()
