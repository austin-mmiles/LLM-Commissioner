import streamlit as st
from espn_fetcher import get_matchup_starters
from gpt_summarizer import generate_recap

st.title("Fantasy Football AI Recap & Preview")

league_id = st.text_input("Enter ESPN League ID")
team_id = st.text_input("Enter Team ID")
week = st.number_input("Week Number", min_value=1, max_value=17, step=1)
year = st.number_input("Year", min_value=2000, max_value=2025, step=1, value=2024)

if st.button("Generate Report"):
    matchup_values = get_matchup_starters(league_id, year, week, team_id)
    recap = generate_recap(team_data)
    #preview = generate_preview(team_data)

    st.subheader("Weekly Recap")
    st.write(recap)

    #st.subheader("Matchup Preview")
    #st.write(preview)
