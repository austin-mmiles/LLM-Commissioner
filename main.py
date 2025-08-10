# main.py
import os
import config
from dotenv import load_dotenv
from espn_fetcher import get_matchup_starters
from gpt_summarizer import generate_recap

load_dotenv(dotenv_path='.env')

def main():
    #league_id = os.environ["LEAGUE_ID"]
    #league_id = os.getenv("LEAGUE_ID")
    #print(f"Sent emails for league {league_id}")
    #print(get_matchup_starters(league_id, 2021, 17, 11))
    recap = generate_recap(league_id=97124817, year=2024, week=1, team_id=7)
    print(recap)


if __name__ == "__main__":
    main()

