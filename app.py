import streamlit as st
from espn_fetcher import get_week_matchups
from gpt_summarizer import generate_week_recap

st.set_page_config(page_title="LLM Commissioner", page_icon="🏈", layout="wide")
st.title("LLM Commissioner – Weekly Recaps")

col1, col2, col3 = st.columns(3)
with col1:
    league_id = st.number_input("League ID", min_value=1, step=1, format="%d")
with col2:
    year = st.number_input("Season (year)", min_value=2015, max_value=2100, value=2024, step=1)
with col3:
    week = st.number_input("Week", min_value=1, max_value=18, value=1, step=1)

st.caption("No team selection needed — we’ll summarize every matchup this week.")

if st.button("Generate Weekly Recap"):
    if not league_id or not year or not week:
        st.error("Please fill in League ID, Year, and Week.")
    else:
        with st.spinner("Pulling ESPN data and writing recaps…"):
            try:
                matchups = get_week_matchups(int(league_id), int(year), int(week))
            except Exception as e:
                st.exception(e)
                st.stop()

            if not matchups:
                st.warning("No matchups found for that week.")
            else:
                recap_md = generate_week_recap(matchups, league_id=int(league_id), year=int(year), week=int(week))
                st.markdown(recap_md)
                st.download_button(
                    "Download Recap (Markdown)",
                    data=recap_md.encode("utf-8"),
                    file_name=f"weekly_recap_{league_id}_{year}_w{week}.md",
                    mime="text/markdown",
                )
