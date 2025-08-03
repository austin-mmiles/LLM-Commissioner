from espn_api.football import League

def get_team_data(league_id, team_id, week):
    league = League(league_id=league_id, year=2025)
    team = next(t for t in league.teams if t.team_id == int(team_id))
    matchups = league.scoreboard(week)
    return {
        "team_name": team.team_name,
        "roster": [player.name for player in team.roster],
        "scores": team.scores,
        "matchup": next((m for m in matchups if m.home_team == team or m.away_team == team), None),
    }