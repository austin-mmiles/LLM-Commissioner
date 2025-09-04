# preview/preview_generator.py
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Tuple, Any

# Data fetch
from espn_api.football import League


# ===============================
# Data types (no owner fields)
# ===============================
@dataclass
class TeamMeta:
    team_id: int
    team_name: str
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
    logo_url: str
    projected_points: float  # SUM OF STARTERS ONLY (internal; not displayed)
    top_players: List[PlayerProj]  # STARTERS ONLY
    meta: TeamMeta


# ===============================
# ESPN helpers
# ===============================
def _load_league(league_id: int, year: int, espn_s2: str | None, swid: str | None) -> League:
    return League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)

def _get_team_meta(league: League) -> Dict[int, TeamMeta]:
    meta: Dict[int, TeamMeta] = {}
    for t in league.teams:
        record = f"{t.wins}-{t.losses}{('-' + str(t.ties)) if getattr(t, 'ties', 0) else ''}"
        meta[t.team_id] = TeamMeta(
            team_id=t.team_id,
            team_name=str(t.team_name),
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
    """
    Build a team projection for THIS WEEK from STARTERS ONLY.
    - Sum projected points for starters only (bench excluded)
    - Top players = starters sorted by projected points desc
    """
    box_scores = league.box_scores(week=week)
    projected_points = 0.0
    starters: List[PlayerProj] = []

    for box in box_scores:
        lineup = None
        if getattr(box.home_team, "team_id", None) == team_id:
            lineup = box.home_lineup
        elif getattr(box.away_team, "team_id", None) == team_id:
            lineup = box.away_lineup
        if lineup is None:
            continue

        for p in lineup:
            proj = getattr(p, "projected_points", None)
            if proj is None:
                continue
            is_starter = not getattr(p, "bench", False)
            if not is_starter:
                # 🚫 BENCH EXCLUDED COMPLETELY
                continue
            pos = getattr(p, "slot_position", getattr(p, "position", ""))
            starters.append(PlayerProj(
                player_id=str(getattr(p, "playerId", getattr(p, "id", "")) or ""),
                name=str(getattr(p, "name", "Player")),
                position=str(pos),
                projected_points=float(proj),
                is_starter=True,
            ))
            projected_points += float(proj)

    starters.sort(key=lambda x: -x.projected_points)
    top_players = starters[:3]
    tm = meta[team_id]
    return TeamWeekProjection(
        team_id=team_id,
        team_name=tm.team_name,
        logo_url=tm.logo_url,
        projected_points=round(projected_points, 2),  # internal only
        top_players=top_players,
        meta=tm,
    )


# ===============================
# Build "cards" for UI + LLM (no owner fields)
# ===============================
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

        # Edge & combined are strictly from STARTERS ONLY
        margin = round(h.projected_points - a.projected_points, 2)
        favorite = h if margin >= 0 else a
        edge = abs(margin)
        combined = round(h.projected_points + a.projected_points, 2)

        def players_list(t: TeamWeekProjection) -> List[Dict[str, Any]]:
            # starters only
            return [
                {"name": p.name, "position": p.position, "proj": round(p.projected_points, 1)}
                for p in t.top_players
            ]

        cards.append({
            "matchup": {
                "favorite": favorite.team_name if edge != 0 else "Pick'em",
                "edge_points": edge,                     # numeric; OK to display
                "combined_proj_starters": combined,      # internal only (for featured)
                "home": {
                    "team_name": h.team_name,            # no abbreviations
                    "logo": h.logo_url,
                    "record": h.meta.record,
                    "streak": h.meta.streak,
                    "top_players_list": players_list(h),
                },
                "away": {
                    "team_name": a.team_name,
                    "logo": a.logo_url,
                    "record": a.meta.record,
                    "streak": a.meta.streak,
                    "top_players_list": players_list(a),
                },
            }
        })

    # Flag the Matchup of the Week: highest combined starters projection
    if cards:
        best_idx = max(
            range(len(cards)),
            key=lambda i: cards[i]["matchup"].get("combined_proj_starters", 0.0)
        )
        cards[best_idx]["matchup"]["is_featured"] = True
    return cards


# ===============================
# LLM: OpenAI
# ===============================
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
    # Cosmetic label to match your league vibe (e.g., "Fantasy Sharks", "ESPN")
    return os.getenv("PREVIEW_PROJECTION_SOURCE", "ESPN")


def _preview_prompt(league_id: int, year: int, week: int, cards: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Output style modeled after the user's example, WITHOUT owner names:

    For the featured matchup (highest combined starters), then each remaining matchup:

    ## Matchup: Team A (Record A) vs Team B (Record B)
    Based on projections from {SOURCE}, Team A can expect a <POINTS> point effort from <Top Player> in week <W>, with a nod to 1–2 other key players.
    "<short, realistic pre-game quote>," the Team A coach said.

    Based on projections from {SOURCE}, Team B can expect a <POINTS> point effort from <Top Player> in week <W>, with a nod to 1–2 other key players.
    "<short, realistic pre-game quote>," the Team B coach said.

    Finish with one short hype sentence. Do NOT invent schedules/history details you were not given.

    Rules:
    - Use ONLY data provided (team names/records, top players with their individual projections, edge label).
    - Mention 1–2 key players (prioritize the highest projected "headliner" and optionally one more).
    - NEVER use owner names or any personal names.
    - Do not display any team total projection.
    - Keep it fun, punchy, and readable.
    """
    import json

    source = _projection_source()

    # Split featured vs others (combined used upstream; we don't include combined in text)
    featured = None
    others: List[Dict[str, Any]] = []

    for c in cards:
        m = c["matchup"]

        def headliner(lst: List[Dict[str, Any]]) -> Dict[str, Any] | None:
            return lst[0] if (isinstance(lst, list) and len(lst) > 0) else None

        home_tp = m["home"].get("top_players_list", [])
        away_tp = m["away"].get("top_players_list", [])

        item = {
            "favorite": m["favorite"],
            "edge_points": m["edge_points"],  # may be used in phrasing "edge: X"
            "home": {
                "team": m["home"]["team_name"],
                "record": m["home"]["record"],
                "streak": m["home"]["streak"],
                "top_players": home_tp,
                "headliner": headliner(home_tp),
            },
            "away": {
                "team": m["away"]["team_name"],
                "record": m["away"]["record"],
                "streak": m["away"]["streak"],
                "top_players": away_tp,
                "headliner": headliner(away_tp),
            }
        }

        if m.get("is_featured"):
            featured = item
        else:
            others.append(item)

    payload = {
        "league_id": league_id,
        "season": year,
        "week": week,
        "projection_source": source,
        "featured_matchup": featured,
        "other_matchups": others,
    }

    system = (
        "You are LLM-Commissioner, writing WEEKLY PREVIEWS in lively, fan-friendly prose. "
        "No owner names; refer to 'the Team X coach' generically in quotes attribution. "
        "Do not invent facts beyond the input. Keep paragraphs tight and exciting."
    )

    user = {
        "instructions": "Generate the Markdown preview using the format and constraints above.",
        "data": payload
    }

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False)}
    ]


# ===============================
# LLM generation
# ===============================
def generate_week_preview_from_cards(
    cards: List[Dict[str, Any]],
    league_id: int,
    year: int,
    week: int,
    temperature: float = 0.9,
    max_tokens: int = 2200,
    presence_penalty: float = 0.2,
    frequency_penalty: float = 0.1,
) -> str:
    """
    Create a single Markdown preview with:
    - ⭐ Featured matchup first (highest combined starters)
    - Two team paragraphs per matchup, each with a coach quote (no names)
    - Mentions of 1–2 top players with their projection numbers
    - No combined totals displayed
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
    max_tokens: int = 2200,
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
