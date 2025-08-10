from espn_api.football import League

def get_matchup_starters(league_id: int, year: int, week: int, team_id: int):
    """
    Returns the matchup score plus starters (name, slot, points) for both teams
    in the specified team's matchup for the given week.
    """
    league_id = int(league_id)
    year = int(year)
    week = int(week)
    team_id = int(team_id)
    
    league = League(league_id=league_id, year=year)
    box_scores = league.box_scores(week=week)

    # find the box score that includes this team_id
    target = None
    for bx in box_scores:
        if bx.home_team.team_id == team_id or bx.away_team.team_id == team_id:
            target = bx
            break
    if target is None:
        raise ValueError(f"No matchup found for team_id {team_id} in week {week}.")

    # helper: filter to starters (exclude Bench/IR)
    def starters(lineup):
        return [
            {
                "name": p.name,
                "slot": p.slot_position,  # e.g., QB/RB/WR/TE/FLEX/DST/K
                "points": round(float(getattr(p, "points", 0) or 0), 2),
            }
            for p in lineup
            if str(p.slot_position).lower() not in ("bench", "ir")
        ]

    home = target.home_team
    away = target.away_team

    home_starters = starters(target.home_lineup)
    away_starters = starters(target.away_lineup)

    home_score = round(float(target.home_score or 0), 2)
    away_score = round(float(target.away_score or 0), 2)

    return {
        "week": week,
        "matchup": {
            "home_team": home.team_name,
            "home_score": home_score,
            "away_team": away.team_name,
            "away_score": away_score,
            "margin": round(home_score - away_score, 2),
            "winner": (
                home.team_name if home_score > away_score
                else away.team_name if away_score > home_score
                else "Tie"
            ),
        },
        "home_starters": home_starters,
        "away_starters": away_starters,
    }

