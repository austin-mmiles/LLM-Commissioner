import os
from dotenv import load_dotenv
load_dotenv(dotenv_path='/full/path/to/.env')

LEAGUE_ID = os.getenv("LEAGUE_ID")
TEAM_ID = os.getenv("TEAM_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
