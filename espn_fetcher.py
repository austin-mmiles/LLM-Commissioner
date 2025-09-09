from typing import List, Dict, Any
import os
from espn_api.football import League

def _get_env(name: str) -> str:
    """
    Reads from environment variables, or from Streamlit secrets if available.
    """
    try:
        import streamlit as st
        return os.getenv(name) or st.secrets.get(name, "")
    except Exception:
        return os.getenv(name, "")

def _load_league(league_id: int, year: int) -> League:
    """
    Load an ESPN fantasy league for the given year with required cookies.
    """
    espn_s2 = _get_env("ESPN_S2")
    swid = _get_env("SWID")

    if not espn_s2 or not swid:
        raise RuntimeError(
            "ESPN cookies are required for current-season data.\n"
            "Set env/secrets ESPN_S2 and SWID. (Copy them from browser DevTools → Cookies.)"
        )

    if not (swid.startswith("{") and swid.endswith("}")):
        raise RuntimeError("SWID must include braces, e.g. {ABCD-1234-...}.")

    return League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)

def get_week_matchups(league_id: int, year: int, week: int) -> List[Dict[str, Any]]:
    """
    Returns a list of matchup dicts for the given week:
    - matchup: home/away team names, scores, winner, margin
    - home_starters / away_starters: [{name, slot, points}, ...]
    """
    league = _load_league(league_id, year)

    # Guard against None or out-of-range weeks
    current = getattr(league, "current_week", None) or 1
    reg_weeks = getattr(getattr(league, "settings", None), "reg_season_count", 14) or 14
    safe_week = min(max(week or current, 1), reg_weeks)

    boxes = league.box_scores(safe_week)
    matchups: List[Dict[str, Any]] = []

    def starters(lineup):
        return [
            {"name": p.name, "slot": p.slot_position, "points": round(p.points or 0, 2)}
            for p in lineup
            if p.slot_position not in ("BE", "IR")
        ]

    for b in boxes:
        home = b.home_team
        away = b.away_team
        home_name = getattr(home, "team_name", "TBD")
        away_name = getattr(away, "team_name", "TBD")
        home_score = round(b.home_score or 0, 2)
        away_score = round(b.away_score or 0, 2)

        m = {
            "week": safe_week,
            "matchup": {
                "home_team": home_name,
                "home_score": home_score,
                "away_team": away_name,
                "away_score": away_score,
                "margin": round(home_score - away_score, 2),
            },
            "home_starters": starters(b.home_lineup),
            "away_starters": starters(b.away_lineup),
        }

        if home_score != away_score:
            m["matchup"]["winner"] = home_name if home_score > away_score else away_name

        matchups.append(m)

    return matchups
