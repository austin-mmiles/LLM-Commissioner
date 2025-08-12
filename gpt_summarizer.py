# gpt_summarizer.py
import os
import random
from typing import List, Dict, Any
from openai import OpenAI

# ====== Model / Client ======
MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ====== Style Configuration ======
COMEDY_PERSONAS = [
    "Shane Gillis-style barstool riffing (blue-collar, deadpan, confident)",
    "Theo Von-style tall tales and odd metaphors (Southern porch energy)",
    "Trevor Wallace-style internet-native roast (fast, punchy, meme-aware)",
]

STYLE_PRIMER = f"""
You are a seasoned fantasy-football humor columnist. Blend sharp analysis with
stand-up-comedy delivery. Think: {', '.join(COMEDY_PERSONAS)}.

Voice & Rhythm:
- Cold open: one-liner hook or quick roast.
- Micro-headings: "Turning Point", "Studs & Duds", "Takeaway".
- Use 1–2 vivid analogies/metaphors. Sprinkle 1 pop-culture riff if apt.
- Name/Team Puns: weave 1–3 tasteful puns on player/team names.
- Be specific: cite player lines or key moments that swung the matchup.
- Tight ending: single-line takeaway with a wink.

Length:
- ~150–220 words per recap.

Formatting:
- Use markdown with short sections, list bullets when helpful.
"""

# ====== Lightweight Name/Team Puns ======
# Seed dictionary for common/funny transforms; you can expand this over time.
PUN_SEEDS = {
    "Patrick Mahomes": ["Mahomes Alone", "Patty Ice", "Ma-thrones"],
    "Travis Kelce": ["Kelce Grammer", "Travvy Patty"],
    "Lamar Jackson": ["LaMario Kart", "Action Jackson"],
    "Jalen Hurts": ["Hurts So Good", "Jalen and the Argonauts"],
    "Tua Tagovailoa": ["Tua Legit to Quit", "Tua Infinity and Beyond"],
    "Josh Allen": ["Allen Wrench", "The Joshwash"],
    "Justin Jefferson": ["Jet Fuel", "JJ the Jet Plane"],
    "Amon-Ra St. Brown": ["The Sun God Tax", "Saint Touchdown"],
    "Christian McCaffrey": ["CMC Hammer", "Run CMC"],
    "Tyreek Hill": ["TyFreak", "Cheetah Speed"],
    "Dak Prescott": ["Dakstreet Boys", "Dak Attack"],
    "Joe Burrow": ["Joe Shiesty", "Brrr-row"],
    "Brock Purdy": ["Mr. Irrelevant No More", "Brock & Roll"],
    "Bijan Robinson": ["Bijan Mustardson", "Bijan Bistro"],
    "Cooper Kupp": ["Red Zone Barista", "Kupp Runneth Over"],
    "Stefon Diggs": ["Diggs Dug", "Stefon the Gas"],
    "Derrick Henry": ["King Henry", "The Heisman Truck"],
    "CeeDee Lamb": ["Seedy Business", "Rack of Lamb"],
    "Deebo Samuel": ["Deebo Bike", "Debozer"],
}

TEAM_PUN_SUFFIXES = ["Nation", "Industrial Complex", "Appreciation Club", "Support Group", "Rehabilitation Center"]

POP_CULTURE_BANK = [
    "a Barbenheimer double feature",
    "a Fortnite kid cranking 90s",
    "a Netflix password crackdown",
    "a crypto rugpull at 3 AM",
    "a surprise Taylor Swift album drop",
    "a ChatGPT prompt spiral",
    "Mario Kart’s blue shell on lap 3",
    "a Costco sample stampede",
    "an Apple keynote ‘one more thing’",
]

def _maybe_pun_name(name: str) -> str:
    base = name.strip()
    if not base:
        return name

    # If we have a seed pun, pick one ~60% of the time.
    if base in PUN_SEEDS and random.random() < 0.6:
        return random.choice(PUN_SEEDS[base])

    parts = base.split()
    first = parts[0]
    last = parts[-1] if len(parts) > 1 else ""

    nick_bank = ["Nuke", "Engine", "Magnet", "Menace", "Metronome"]

    options = [
        # e.g., "Patrick 'The Nuke' Mahomes" (last may be empty for single names)
        f"{first} 'The {random.choice(nick_bank)}' {last}".strip(),
        # e.g., "PatrickM-zilla" when last exists
        f"{first}{(last[0] if last else '')}-zilla",
        f"{first}-nator",
    ]
    return random.choice(options)

def _team_pun(name: str) -> str:
    name = name or "Team"
    if random.random() < 0.5:
        return f"{name} {random.choice(TEAM_PUN_SUFFIXES)}"
    return name

def _pick_pop_culture_ref() -> str:
    return random.choice(POP_CULTURE_BANK)

def _top_three(starters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Sort by points descending and take top 3
    return sorted(starters, key=lambda x: (x.get("points") or 0), reverse=True)[:3]

def _format_player_list(players: List[Dict[str, Any]]) -> str:
    out = []
    for p in players:
        name = p.get("name", "Unknown")
        slot = p.get("slot", "")
        pts = p.get("points", 0)
        out.append(f"- {name} ({slot}) — {pts} pts")
    return "\n".join(out) if out else "- (no notable starters found)"

def _craft_prompt(matchup: Dict[str, Any]) -> str:
    m = matchup["matchup"]
    home = m["home_team"]
    away = m["away_team"]
    home_score = m["home_score"]
    away_score = m["away_score"]
    winner = m.get("winner", "TBD")
    margin = m.get("margin", 0)

    home_pun = _team_pun(home)
    away_pun = _team_pun(away)

    top_home = _top_three(matchup.get("home_starters", []))
    top_away = _top_three(matchup.get("away_starters", []))

    # Pun some names inline for flavor (don’t overdo it)
    def enrich(players):
        enriched = []
        for p in players:
            newp = dict(p)
            if random.random() < 0.5:
                newp["alt"] = _maybe_pun_name(p.get("name", ""))
            enriched.append(newp)
        return enriched

    top_home = enrich(top_home)
    top_away = enrich(top_away)

    home_top_md = _format_player_list(top_home)
    away_top_md = _format_player_list(top_away)

    culture = _pick_pop_culture_ref()
    persona = random.choice(COMEDY_PERSONAS)

    # Provide structured facts + comedic levers to the model
    user_content = f"""
FACTS:
- Matchup: {home} vs {away}
- Scores: {home} {home_score} — {away} {away_score}
- Winner: {winner}
- Margin: {margin}

HOME TOP STARTERS (flair may include alt pun names):
{home_top_md}

AWAY TOP STARTERS (flair may include alt pun names):
{away_top_md}

Creative levers you can use:
- Persona flavor: {persona}
- One pop-culture nod: {culture}
- Use 1–3 playful puns on team/player names (from the lists above, or invent tasteful ones).
- Keep it specific: reference at least one decisive play or performance from the lists.

Now write a markdown recap with:
- A quick cold-open zinger (1 sentence).
- **Turning Point**: one short paragraph (1–3 sentences).
- **Studs & Duds**: 3–6 bullets total (mix of praise/roast).
- **Takeaway**: one single-line verdict.
- ~150–220 words total.
"""

    return user_content

# ====== Public API ======

def generate_matchup_recap(matchup_dict: Dict[str, Any]) -> str:
    """
    Returns a single spicy, funny, insightful recap in markdown (~150–220 words).
    """
    messages = [
        {"role": "system", "content": STYLE_PRIMER},
        {"role": "user", "content": _craft_prompt(matchup_dict)},
    ]

    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.95,     # let it cook
        top_p=0.9,
        frequency_penalty=0.3,
        presence_penalty=0.2,
    )
    return resp.choices[0].message.content.strip()

def generate_week_recap(matchups: List[Dict[str, Any]], *, league_id: int, year: int, week: int) -> str:
    """
    Builds a single markdown doc for all matchups in a week.
    """
    parts = [f"# Weekly Recap – League {league_id}, {year} Week {week}\n"]
    random.seed(f"{league_id}-{year}-{week}")  # stable-ish jokes per run
    for i, m in enumerate(matchups, start=1):
        title = f"## Matchup {i}: {m['matchup']['home_team']} vs {m['matchup']['away_team']}"
        body = generate_matchup_recap(m)
        parts.append(f"{title}\n\n{body}\n")
    return "\n---\n".join(parts)
