
from espn_api.football import League
import sqlite3
import os

# === CONFIGURATION ===
LEAGUE_ID = 97124817  # Replace with your league ID
START_YEAR = 2020   # Replace with the earliest year you want
END_YEAR = 2024     # Replace with the latest year you want
SWID = os.getenv("ESPN_SWID")  # ESPN SWID cookie
ESPN_S2 = os.getenv("ESPN_S2")  # ESPN S2 cookie

# === DATABASE CONNECTION ===
conn = sqlite3.connect("fantasy_league.db")
cursor = conn.cursor()

# === MAIN IMPORT FUNCTION ===
def import_league_data(year):
    print(f"Importing data for {year}...")
    league = League(league_id=LEAGUE_ID, year=year, swid=SWID, espn_s2=ESPN_S2)

    # Insert league record
    cursor.execute("INSERT OR IGNORE INTO leagues (id, year, name) VALUES (?, ?, ?)",
                   (LEAGUE_ID, year, f"League {year}"))

    
    # Insert teams
    for team in league.teams:
        #print(dir(team))
        cursor.execute("INSERT OR IGNORE INTO teams (id, name, owner, league_id) VALUES (?, ?, ?, ?)",
                       (team.team_id, team.team_name, str(team.owners), LEAGUE_ID))

    # Insert weekly matchups and player scores
    for week in range(1, 18):  # Max 17 regular season weeks
        scoreboard = league.scoreboard(week=week)
        standings = league.standings()

        for match in scoreboard:
            team_a = match.home_team
            team_b = match.away_team
            score_a = match.home_score
            score_b = match.away_score
            winner = team_a if score_a > score_b else team_b

            cursor.execute("""
            INSERT INTO matchups (week, team_a_id, team_b_id, score_a, score_b, winner_id, league_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (week, team_a.team_id, team_b.team_id, score_a, score_b, winner.team_id, LEAGUE_ID))

            # Player scores
            print(team_a.roster)
            for player, stats in team_a.roster():
                cursor.execute("""
                INSERT INTO player_scores (player_name, player_id, team_id, fantasy_team_id, week, points, position, league_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (player.name, player.playerId, player.proTeam, team_a.team_id, week, stats['points'], player.position, LEAGUE_ID))

            for player, stats in team_b.roster():
                cursor.execute("""
                INSERT INTO player_scores (player_name, player_id, team_id, fantasy_team_id, week, points, position, league_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (player.name, player.playerId, player.proTeam, team_b.team_id, week, stats['points'], player.position, LEAGUE_ID))

        # Insert standings
        for standing in standings:
            cursor.execute("""
            INSERT INTO standings (team_id, week, wins, losses, ties, points_for, points_against, rank, league_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (standing.team_id, week, standing.wins, standing.losses, standing.ties,
             standing.points_for, standing.points_against, standing.rank, LEAGUE_ID))

# === RUN IMPORT FOR ALL YEARS ===
for year in range(START_YEAR, END_YEAR + 1):
    try:
        import_league_data(year)
        conn.commit()
    except Exception as e:
        print(f"Failed to import {year}: {e}")

conn.close()
