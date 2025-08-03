import openai
import os

def generate_recap(team_data):
    prompt = f"""
    Give a fun and insightful weekly recap for the following fantasy football team:
    Team: {team_data['team_name']}
    Players: {', '.join(team_data['roster'])}
    Scores: {team_data['scores']}
    """
    
    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

def generate_preview(team_data):
    prompt = f"""
    Predict next week's matchup and provide insights for this team:
    Team: {team_data['team_name']}
    Roster: {', '.join(team_data['roster'])}
    Opponent data: {team_data['matchup']}
    """
    
    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()
