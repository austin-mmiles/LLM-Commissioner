from typing import List, Dict, Any
from espn_api.football import League

def get_week_matchups(league_id: int, year: int, week: int) -> List[Dict[str, Any]]:
    """
    Returns a list of matchup dicts for the given week:
    - matchup: home/away team names, scores, winner, margin
    - home_starters / away_starters: [{name, slot, points}, ...]
    NOTE: This version does NOT require ESPN_S2 or SWID. It will only work for
    leagues that are public or otherwise readable without auth.
    """
    league = League(league_id=league_id, year=year)

    boxes = league.box_scores(week)
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
            "week": week,
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
