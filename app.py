# app.py
import os
import traceback

# ⬇️ PREVIEW IMPORTS (OpenAI-driven preview)
from preview.preview_generator import (
    build_weekly_preview_cards,
    generate_week_preview,
)

os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "poll"
os.environ["STREAMLIT_SERVER_RUN_ON_SAVE"] = "false"

import streamlit as st

os.environ["STREAMLIT_SERVER_RUN_ON_SAVE"] = "false"
st.set_page_config(page_title="LLM Commissioner", page_icon="🏈", layout="wide")
st.title("Fantasy Football Commissioner – Weekly Recaps")
st.cache_data.clear()

# -------------------- Secrets/env bootstrap --------------------
def _maybe_env_from_secrets(key: str):
    try:
        if key in st.secrets and not os.getenv(key):
            os.environ[key] = str(st.secrets[key])
    except Exception:
        pass  # st.secrets may not exist locally

for _k in ("OPENAI_API_KEY", "ESPN_S2", "SWID"):
    _maybe_env_from_secrets(_k)

# -------------------- Lazy imports so import errors don't kill the app --------------------
_import_error = None
def _load_modules():
    global get_week_matchups, generate_week_recap
    try:
        from espn_fetcher import get_week_matchups
        from gpt_summarizer import generate_week_recap
        return None
    except Exception as e:
        return e

_import_error = _load_modules()

# -------------------- Sidebar (no OpenAI key field) --------------------
with st.sidebar:
    st.header("Optional ESPN Credentials")
    st.caption("Set these only if your league is private. For public leagues, you can leave them blank.")
    s2 = st.text_input("ESPN_S2", value=os.getenv("ESPN_S2", ""), type="password")
    swid = st.text_input("SWID", value=os.getenv("SWID", ""), type="password")
    if st.button("Save ESPN Credentials"):
        if s2:
            os.environ["ESPN_S2"] = s2
        if swid:
            os.environ["SWID"] = swid
        st.success("Saved for this session.")

    # Diagnostics (safe: shows flags, not values)
    with st.expander("Diagnostics"):
        st.write({
            "OPENAI_API_KEY set?": bool(os.getenv("OPENAI_API_KEY")),
            "ESPN_S2 set?": bool(os.getenv("ESPN_S2")),
            "SWID set?": bool(os.getenv("SWID")),
            "Import error?": str(_import_error) if _import_error else "None",
        })

# -------------------- Inputs --------------------
col1, col2, col3 = st.columns(3)
with col1:
    league_id = st.number_input("League ID", min_value=1, step=1, format="%d")
with col2:
    year = st.number_input("Season (year)", min_value=2015, max_value=2100, value=2024, step=1)
with col3:
    week = st.number_input("Week", min_value=1, max_value=18, value=1, step=1)

st.caption("We’ll summarize **every matchup** for the selected week. ESPN cookies are optional for public leagues.")

# -------------------- Helpers --------------------
def _need_openai() -> bool:
    if not os.getenv("OPENAI_API_KEY"):
        st.error("Missing **OPENAI_API_KEY** — add it in Streamlit Secrets (or as an environment variable).")
        return True
    return False

def _render(text: str):
    # Render HTML if present; otherwise Markdown
    if "<" in text and ">" in text and "</" in text:
        st.components.v1.html(text, height=900, scrolling=True)
    else:
        st.markdown(text)

@st.cache_data(show_spinner=False, ttl=1)
def _fetch_matchups_cached(_league_id: int, _year: int, _week: int):
    return get_week_matchups(_league_id, _year, _week)

# -------------------- Main Recap action (UNCHANGED) --------------------
disabled = _import_error is not None or not bool(os.getenv("OPENAI_API_KEY"))
if st.button("Generate Weekly Recap", type="primary", disabled=disabled):
    if _import_error:
        st.error("Import failure: could not load a module.")
        with st.expander("Import error details"):
            st.code("".join(traceback.format_exception(type(_import_error), _import_error, _import_error.__traceback__)))
        st.stop()

    if not league_id or not year or not week:
        st.error("Please fill in League ID, Year, and Week.")
        st.stop()

    if _need_openai():
        st.stop()

    if not os.getenv("ESPN_S2") or not os.getenv("SWID"):
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

# If the button is disabled, show why (without exposing secrets)
if disabled:
    msgs = []
    if _import_error is not None:
        msgs.append("module import failure")
    if not bool(os.getenv("OPENAI_API_KEY")):
        msgs.append("OPENAI_API_KEY missing")
    st.info("Generate button disabled: " + ", ".join(msgs))

# -------------------- Weekly Preview (LLM-driven; mirrors Recap UX) --------------------
st.header("Weekly Preview")

# Read cookies (keep recap's SWID naming; accept ESPN_SWID as fallback here)
espn_s2 = os.getenv("ESPN_S2", None)
swid = os.getenv("SWID", os.getenv("ESPN_SWID", None))

if st.button("Build Weekly Preview", type="secondary", disabled=not bool(os.getenv("OPENAI_API_KEY"))):
    if not league_id or not year or not week:
        st.error("Please fill in League ID, Year, and Week.")
        st.stop()

    if _need_openai():
        st.stop()

    if not (espn_s2 and swid):
        st.info("No ESPN cookies found — trying without them (public leagues only).")

    # 1) Pull raw preview cards (context passed to LLM)
    with st.spinner("Pulling ESPN data and computing projections…"):
        try:
            cards = build_weekly_preview_cards(int(league_id), int(year), int(week), espn_s2=espn_s2, swid=swid)
        except Exception as e:
            st.error("Preview failed while fetching data.")
            with st.expander("Error details"):
                st.code("".join(traceback.format_exception(type(e), e, e.__traceback__)))
            st.stop()

    if not cards:
        st.warning("No matchups found for this week.")
        st.stop()

    with st.expander("Show raw preview context"):
        st.write(cards)

    # 2) LLM generate (single doc, like recap)
    with st.spinner("Assembling Weekly Preview with LLM…"):
        try:
            preview_doc = generate_week_preview(int(league_id), int(year), int(week), espn_s2=espn_s2, swid=swid)
        except Exception as e:
            st.error("LLM preview generation failed.")
            with st.expander("Error details"):
                st.code("".join(traceback.format_exception(type(e), e, e.__traceback__)))
            st.stop()

    st.success("Weekly Preview generated!")
    _render(preview_doc)

    st.download_button(
        "Download Preview (Markdown)",
        data=(preview_doc or "").encode("utf-8"),
        file_name=f"weekly_preview_{league_id}_{year}_w{week}.md",
        mime="text/markdown",
    )
