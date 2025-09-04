# preview/preview_generator.py
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Tuple, Any

# Data fetch
from espn_api.football import League

# -------------------------------
# Data types
# -------------------------------
@dataclass
class TeamMeta:
    team_id: int
    team_name: str
    owner_name: str
    logo_url: str
    record: str
    points_for: float
    points_against: float
    streak: str

@dataclass
class PlayerProj:
    player_id: str
    name: str
    position: str
    projected_points: float
    is_starter: bool

@dataclass
class TeamWeekProjection:
    team_id: int
    team_name: str
    owner_name: str
    logo_url: str
    projected_points: float
    top_players: List[PlayerProj]
    meta: TeamMeta


# -------------------------------
# ESPN fetch helpers
# -------------------------------
def _load_league(league_id: int, year: int, espn_s2: str | None, swid: str | None) -> League:
    return League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)

def _safe_owner_name(t) -> str:
    # espn_api sometimes exposes t.owner as a string; sometimes an object; sometimes None.
    owner = getattr(t, "owner", None)
    if isinstance(owner, str) and owner.strip():
        return owner.strip()
    # Avoid team abbreviations entirely.
    return "Unknown Coach"

def _get_team_meta(league: League) -> Dict[int, TeamMeta]:
    meta: Dict[int, TeamMeta] = {}
    for t in league.teams:
        record = f"{t.wins}-{t.losses}{('-' + str(t.ties)) if getattr(t, 'ties', 0) else ''}"
        meta[t.team_id] = TeamMeta(
            team_id=t.team_id,
            team_name=str(t.team_name),
            owner_name=_safe_owner_name(t),
            logo_url=str(getattr(t, "logo_url", "") or ""),
            record=record,
            points_for=float(getattr(t, "points_for", 0.0) or 0.0),
            points_against=float(getattr(t, "points_against", 0.0) or 0.0),
            streak=f"{getattr(t, 'streak_type', 'NONE')} {getattr(t, 'streak_length', 0)}",
        )
    return meta

def _get_week_pairs(league: League, week: int) -> List[Tuple[int, int]]:
    pairs: List[Tuple[int, int]] = []
    for m in league.scoreboard(week=week):
        if not (hasattr(m, "home_team") and hasattr(m, "away_team")):
            continue
        pairs.append((m.home_team.team_id, m.away_team.team_id))
    return pairs

def _get_team_week_projection(league: League, week: int, team_id: int, meta: Dict[int, TeamMeta]) -> TeamWeekProjection:
    box_scores = league.box_scores(week=week)
    projected_points = 0.0
    players: List[PlayerProj] = []

    for box in box_scores:
        if getattr(box.home_team, "team_id", None) == team_id:
            lineup = box.home_lineup
        elif getattr(box.away_team, "team_id", None) == team_id:
            lineup = box.away_lineup
        else:
            continue

        for p in lineup:
            proj = getattr(p, "projected_points", None)
            if proj is None:
                continue
            pos = getattr(p, "slot_position", getattr(p, "position", ""))
            is_starter = not getattr(p, "bench", False)
            if is_starter:
                projected_points += float(proj)
            players.append(PlayerProj(
                player_id=str(getattr(p, "playerId", getattr(p, "id", "")) or ""),
                name=str(getattr(p, "name", "Player")),
                position=str(pos),
                projected_points=float(proj),
                is_starter=bool(is_starter),
            ))

    # Prioritize starters & higher projections
    players.sort(key=lambda x: (not x.is_starter, -x.projected_points))
    top_players = players[:3]
    tm = meta[team_id]
    return TeamWeekProjection(
        team_id=team_id,
        team_name=tm.team_name,
        owner_name=tm.owner_name,
        logo_url=tm.logo_url,
        projected_points=round(projected_points, 2),
        top_players=top_players,
        meta=tm,
    )


# -------------------------------
# Public: build "cards" used by the UI and LLM
# -------------------------------
def build_weekly_preview_cards(
    league_id: int,
    year: int,
    week: int,
    espn_s2: str | None = None,
    swid: str | None = None
) -> List[Dict[str, Any]]:
    league = _load_league(league_id, year, espn_s2, swid)
    meta = _get_team_meta(league)
    pairs = _get_week_pairs(league, week)

    cards: List[Dict[str, Any]] = []
    for home_id, away_id in pairs:
        h = _get_team_week_projection(league, week, home_id, meta)
        a = _get_team_week_projection(league, week, away_id, meta)

        margin = round(h.projected_points - a.projected_points, 2)
        favorite = h if margin >= 0 else a
        edge = abs(margin)

        def players_list(t: TeamWeekProjection) -> List[Dict[str, Any]]:
            return [
                {"name": p.name, "position": p.position, "proj": round(p.projected_points, 1)}
                for p in t.top_players
            ]

        cards.append({
            "matchup": {
                "favorite": favorite.team_name if edge != 0 else "Pick'em",
                "edge_points": edge,
                "home": {
                    "team_name": h.team_name,          # no abbreviations
                    "owner": h.owner_name,
                    "logo": h.logo_url,
                    "proj": h.projected_points,
                    "record": h.meta.record,
                    "streak": h.meta.streak,
                    "top_players_list": players_list(h),
                },
                "away": {
                    "team_name": a.team_name,
                    "owner": a.owner_name,
                    "logo": a.logo_url,
                    "proj": a.projected_points,
                    "record": a.meta.record,
                    "streak": a.meta.streak,
                    "top_players_list": players_list(a),
                },
            }
        })
    return cards


# -------------------------------
# LLM: OpenAI client & prompt
# -------------------------------
def _openai_client():
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    return OpenAI(api_key=api_key)

def _default_model() -> str:
    # Let users override to match their recap model
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")

def _projection_source() -> str:
    # Cosmetic label to match your league vibe (e.g., "Fantasy Sharks")
    return os.getenv("PREVIEW_PROJECTION_SOURCE", "ESPN")

def _preview_prompt(league_id: int, year: int, week: int, cards: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Style: energetic, pun-friendly, readable.
    Output for EACH matchup:
      ## Matchup: Team A vs Team B
      **Edge:** <Favorite or Pick'em> by <edge> (if edge=0, say Pick'em)
      Team A paragraph:
        - Start with: "Based on projections from {SOURCE}, <Team A> can expect a <POINTS> point effort from <Top Player> in week <W> ..."
        - Include a short 1–2 line coach-style quote in *italics*, attributed like: — <Team A> coach <Owner Name>
        - 1–3 sentences. Playful puns/phrases; easy to scan.
      Team B paragraph: same pattern.
      One-line closer: hype the matchup; do NOT invent history.
    Constraints:
      - Only use the provided data (teams, owners, records, streaks, projections, top players list, favorite/edge).
      - Do NOT fabricate stats, injuries, past meetings, or schedules.
      - Never use team abbreviations; always use full team and owner names.
      - Quotes must sound like realistic post-practice interview lines (focus, execution, next play, etc.). No profanity.
    """
    import json

    source = _projection_source()

    payload = {
        "league_id": league_id,
        "season": year,
        "week": week,
        "projection_source": source,
        "matchups": []
    }

    for c in cards:
        m = c["matchup"]

        def headliner(lst: List[Dict[str, Any]]) -> Dict[str, Any] | None:
            return lst[0] if (isinstance(lst, list) and len(lst) > 0) else None

        home_tp = m["home"].get("top_players_list", [])
        away_tp = m["away"].get("top_players_list", [])

        payload["matchups"].append({
            "favorite": m["favorite"],
            "edge": m["edge_points"],
            "home": {
                "team": m["home"]["team_name"],
                "owner": m["home"]["owner"],
                "record": m["home"]["record"],
                "streak": m["home"]["streak"],
                "proj": m["home"]["proj"],
                "top_players": home_tp,
                "headliner": headliner(home_tp),
            },
            "away": {
                "team": m["away"]["team_name"],
                "owner": m["away"]["owner"],
                "record": m["away"]["record"],
                "streak": m["away"]["streak"],
                "proj": m["away"]["proj"],
                "top_players": away_tp,
                "headliner": headliner(away_tp),
            }
        })

    system = (
        "You are LLM-Commissioner, a witty sports writer crafting a WEEKLY PREVIEW for a fantasy football league. "
        "Write with energy, humor, and playful puns while staying league-safe. "
        "Be concise and highly readable: short paragraphs, bold key numbers, and clear edges. "
        "Quotes must sound like realistic coach/player interview lines (no profanity or insults). "
        "Never invent facts beyond the provided data."
    )

    user = {
        "instructions": "Generate a Markdown preview for each matchup using the specified format and constraints.",
        "format": {
            "section_header": "## Matchup: <Team A> vs <Team B>",
            "edge_line": "**Edge:** <Favorite or Pick'em> by <edge>",
            "team_paragraphs": 2,
            "closer_line": "1 short hype sentence; no invented history."
        },
        "data": payload
    }

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False)}
    ]


# -------------------------------
# LLM generation
# -------------------------------
def generate_week_preview_from_cards(
    cards: List[Dict[str, Any]],
    league_id: int,
    year: int,
    week: int,
    temperature: float = 0.9,
    max_tokens: int = 2000,
    presence_penalty: float = 0.2,
    frequency_penalty: float = 0.1,
) -> str:
    """
    Create a single Markdown preview document with lively, punny copy and realistic coach quotes.
    """
    client = _openai_client()
    model = _default_model()
    messages = _preview_prompt(league_id, year, week, cards)

    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        presence_penalty=presence_penalty,
        frequency_penalty=frequency_penalty,
    )
    return resp.choices[0].message.content.strip()

def generate_week_preview(
    league_id: int,
    year: int,
    week: int,
    espn_s2: str | None = None,
    swid: str | None = None,
    temperature: float = 0.9,
    max_tokens: int = 2000,
) -> str:
    """
    One-call convenience for the Streamlit app: fetch → LLM → Markdown.
    """
    cards = build_weekly_preview_cards(league_id, year, week, espn_s2=espn_s2, swid=swid)
    if not cards:
        return f"# Weekly Preview (Week {week})\n\n_No matchups found for this week._"
    return generate_week_preview_from_cards(
        cards, league_id, year, week, temperature=temperature, max_tokens=max_tokens
    )
