# app.py
import os
import traceback
import streamlit as st
from espn_fetcher import get_week_matchups
from gpt_summarizer import generate_week_recap

# ---------- Page ----------
st.set_page_config(page_title="LLM Commissioner", page_icon="🏈", layout="wide")
st.title("LLM Commissioner – Weekly Recaps")

with st.sidebar:
    st.header("Credentials")
    st.caption("Set these if not already provided via Environment or Streamlit Secrets.")
    _openai = st.text_input("OPENAI_API_KEY", value=os.getenv("OPENAI_API_KEY", ""), type="password")
    
    if st.button("Save Credentials"):
        if _openai:
            os.environ["OPENAI_API_KEY"] = _openai
        st.success("Saved for this session.")

def _check_prereqs() -> bool:
    if not os.getenv("OPENAI_API_KEY"):
        st.error("Missing **OPENAI_API_KEY** — add it in the sidebar or Streamlit Secrets.")
        return False

    if not os.getenv("ESPN_S2") or not os.getenv("SWID"):
        st.warning(
            "ESPN_S2 and/or SWID are missing — public leagues may still work, "
            "but private leagues will fail to fetch data."
        )
    return True

col1, col2, col3 = st.columns(3)
with col1:
    league_id = st.number_input("League ID", min_value=1, step=1, format="%d")
with col2:
    year = st.number_input("Season (year)", min_value=2015, max_value=2100, value=2024, step=1)
with col3:
    week = st.number_input("Week", min_value=1, max_value=18, value=1, step=1)

st.caption("No team selection needed — we’ll summarize every matchup this week.")

def _render(text: str):
    if "<" in text and ">" in text:
        st.components.v1.html(text, height=900, scrolling=True)
    else:
        st.markdown(text)

if st.button("Generate Weekly Recap", type="primary"):
    if not league_id or not year or not week:
        st.error("Please fill in League ID, Year, and Week.")
        st.stop()

    if not _check_prereqs():
        st.stop()

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

        try:
            try:
                recap_md = generate_week_recap(
                    matchups, league_id=int(league_id), year=int(year), week=int(week)
                )
            except TypeError:
                recap_md = generate_week_recap(matchups)
        except Exception as e:
            st.error("LLM recap generation failed.")
            with st.expander("Error details"):
                st.code("".join(traceback.format_exception(type(e), e, e.__traceback__)))
            st.stop()

    st.success("Recap generated!")
    _render(recap_md)

    st.download_button(
        "Download Recap (Markdown)",
        data=(recap_md or "").encode("utf-8"),
        file_name=f"weekly_recap_{league_id}_{year}_w{week}.md",
        mime="text/markdown",
    )
