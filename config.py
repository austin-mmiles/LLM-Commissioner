import os
from dotenv import load_dotenv
load_dotenv()

LEAGUE_ID = os.getenv("LEAGUE_ID")
TEAM_ID = os.getenv("TEAM_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# requirements.txt
openai
streamlit
espn-api
python-dotenv

# .env (do NOT commit this)
OPENAI_API_KEY=your_openai_key_here
LEAGUE_ID=your_league_id_here
TEAM_ID=your_team_id_here
