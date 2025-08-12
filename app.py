# app.py
import os
import traceback
import streamlit as st
from espn_fetcher import get_week_matchups
from gpt_summarizer import generate_week_recap

# -------------------- Secrets/env bootstrap --------------------
def _maybe_env_from_secrets(key: str):
    try:
        if key in st.secrets and not os.getenv(key):
            os.environ[key] = str(st.secrets[key])
    except Exception:
        pass  # st.secrets may not exist locally

# Always try loading secrets into env first
for _k in ("OPENAI_API_KEY", "ESPN_S2", "SWID"):
    _maybe_env_from_secrets(_k)

# -------------------- Page --------------------
st.set_page_config(page_title="LLM Commissioner", page_icon="🏈", layout="wide")
st.title("LLM Commissioner – Weekly Recaps")

with st.sidebar:
    st.header("Optional ESPN Credentials")
    st.caption("Set these if your league is private. For public leagues, leave blank.")
    s2 = st.text_input("ESPN_S2", value=os.getenv("ESPN_S2", ""), type="password")
    swid = st.text_input("SWID", value=os.getenv("SWID", ""), type="password")
    if st.button("Save ESPN Credentials"):
        if s2:
            os.environ["ESPN_S2"] = s2
        if swid:
            os.environ["SWID"] = swid
        st.success("Saved for this session.")

def _need_openai() -> bool:
    if not os.getenv("OPENAI_API_KEY"):
        st.error("Missing **OPENAI_API_KEY** — add it in Streamlit Secrets or as an environment variable.")
        return True
    return False

col1, col2, col3 = st.columns(3)
with col1:
    league_id = st.number_input("League ID", min_value=1, step=1, format="%d")
with col2:
    year = st.number_input("Season (year)", min_value=2015, max_value=2100, value=2024, step=1)
with col3:
    week = st.number_input("Week", min_value=1, max_value=18, value=1, step=1)

st.caption("We’ll summarize **every matchup** for the selected week. ESPN cookies are optional for public leagues.")

def _render(text: str):
    if "<" in text and ">" in text:
        st.components.v1.html(text, height=900, scrolling=True)
    else:
        st.markdown(text)

if st.button("Generate Weekly Recap", type="primary"):
    if not league_id or not year or not week:
        st.error("Please fill in League ID, Year, and Week.")
        st.stop()

    if _need_openai():
        st.stop()

    if not os.getenv("ESPN_S2") or not os.getenv("SWID"):
        st.warning("No ESPN cookies found — public leagues may work, private leagues will not.")

    with st.spinner("Pulling ESPN data and writing recaps…"):
        try:
            matchups = get_week_matchups(int(league_id), int(year), int(week))
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
        file_name=f"weekly_recap_{league_id}_{year}_w{week}.m
