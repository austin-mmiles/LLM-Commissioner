# main.py
import os

def main():
    league_id = os.environ["LEAGUE_ID"]
    # ... pull data, generate copy, send email ...
    print(f"Sent emails for league {league_id}")

if __name__ == "__main__":
    main()
