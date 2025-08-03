import streamlit as st
from espn_fetcher import get_team_data
from gpt_summarizer import generate_recap, generate_preview

st.title("Fantasy Football AI Recap & Preview")

league_id = st.text_input("Enter ESPN League ID")
team_id = st.text_input("Enter Team ID")
week = st.number_input("Week Number", min_value=1, max_value=17, step=1)

if st.button("Generate Report"):
    team_data = get_team_data(league_id, team_id, week)
    recap = generate_recap(team_data)
    preview = generate_preview(team_data)

    st.subheader("Weekly Recap")
    st.write(recap)

    st.subheader("Matchup Preview")
    st.write(preview)