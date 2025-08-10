# gpt_summarizer.py
# Standalone: fetches matchup data from ESPN and generates an advanced recap via OpenAI.

import espn_fetcher
import os
from openai import OpenAI
from typing import Any, Dict, List
import hashlib
import streamlit as st

os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]

def generate_recap(league_id: int, year: int, week: int, team_id: int) -> str:
    """
    Fetch the matchup from ESPN and return a witty, advanced recap.

    Args:
        league_id: ESPN league ID
        year: season year
        week: week number
        team_id: ESPN team ID

    Returns:
        str: recap text
    """
    team_data = espn_fetcher.get_matchup_starters(league_id, year, week, team_id)

    prompt = _build_prompt(team_data)
    #client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    #client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

    resp = client.chat.completions.create(
        model="gpt-4o-mini",  # or your preferred model
        messages=[
            {"role": "system", "content": "You are a witty, insightful fantasy football beat writer."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.8,
        max_tokens=600
    )

    return resp.choices[0].message.content.strip()


# ---------------- Internals ----------------

def _build_prompt(team_data: Dict[str, Any]) -> str:
    m = team_data.get("matchup", {})
    home_starters = team_data.get("home_starters", [])
    away_starters = team_data.get("away_starters", [])

    return f"""
Write a creative, snarky, and intelligent fantasy football recap for this matchup.

Week: {team_data.get("week")}
Home: {m.get("home_team")} scored {m.get("home_score")} points
Away: {m.get("away_team")} scored {m.get("away_score")} points
Winner: {m.get("winner")}
Margin: {m.get("margin")}

Home starters:
{_format_players(home_starters)}

Away starters:
{_format_players(away_starters)}

Rules:
- Start with a strong lead sentence that hooks the reader.
- Include 2–3 short paragraphs mixing stats and colorful commentary.
- Mention standout players and key performances.
- End with a witty one-line kicker.
- Make it rated R, snarky, add insults.
- Limit to ~300 words.
    """.strip()


def _format_players(players: List[Dict[str, Any]]) -> str:
    return "\n".join(
        f"- {p.get('name')} ({p.get('slot')}): {p.get('points')} pts"
        for p in players
    )


# Optional: stable IDs if you need them later
def _stable_id(s: str) -> int:
    h = hashlib.sha1(s.encode("utf-8")).hexdigest()
    return int(h[-8:], 16)
