# preview/preview_generator.py
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Tuple, Any

from espn_api.football import League

# ---- Data types (same shape your UI used before) ----
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

# ----------------- ESPN fetch helpers -----------------
def _load_league(league_id: int, year: int, espn_s2: str | None, swid: str | None) -> League:
    return League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)

def _get_team_meta(league: League) -> Dict[int, TeamMeta]:
    meta: Dict[int, TeamMeta] = {}
    for t in league.teams:
        # owner_name can vary by espn_api version; fallbacks
        owner_name = getattr(t, "owner", None)
        if isinstance(owner_name, str) and owner_name:
            oname = owner_name
        else:
            oname = getattr(t, "team_abbrev", "") or "Owner"

        record = f"{t.wins}-{t.losses}{('-' + str(t.ties)) if getattr(t, 'ties', 0) else ''}"
        meta[t.team_id] = TeamMeta(
            team_id=t.team_id,
            team_name=t.team_name,
            owner_name=oname,
            logo_url=t.logo_url,
            record=record,
            points_for=getattr(t, "points_for", 0.0),
            points_against=getattr(t, "points_against", 0.0),
            streak=f"{getattr(t, 'streak_type', 'NONE')} {getattr(t, 'streak_length', 0)}",
        )
    return meta

def _get_week_pairs(league: League, week: int) -> List[Tuple[int, int]]:
    pairs: List[Tuple[int, int]] = []
    for m in league.scoreboard(week=week):
        pairs.append((m.home_team.team_id, m.away_team.team_id))
    return pairs

def _get_team_week_projection(league: League, week: int, team_id: int, meta: Dict[int, TeamMeta]) -> TeamWeekProjection:
    box_scores = league.box_scores(week=week)
    projected_points = 0.0
    players: List[PlayerProj] = []

    for box in box_scores:
        if box.home_team.team_id == team_id:
            lineup = box.home_lineup
        elif box.away_team.team_id == team_id:
            lineup = box.away_lineup
        else:
            continue

        for p in lineup:
            proj = getattr(p, "projected_points", None)
            pos = getattr(p, "slot_position", getattr(p, "position", ""))
            is_starter = not getattr(p, "bench", False)
            if proj is None:
                continue
            if is_starter:
                projected_points += float(proj)
            players.append(PlayerProj(
                player_id=str(getattr(p, "playerId", getattr(p, "id", ""))),
                name=getattr(p, "name", "Player"),
                position=pos,
                projected_points=float(proj),
                is_starter=bool(is_starter),
            ))

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

# Public: return raw “cards” (for debugging / raw expander)
def build_weekly_preview_cards(league_id: int, year: int, week: int, espn_s2: str | None = None, swid: str | None = None) -> List[Dict[str, Any]]:
    league = _load_league(league_id, year, espn_s2, swid)
    meta = _get_team_meta(league)
    pairs = _get_week_pairs(league, week)

    cards: List[Dict[str, Any]] = []
    for home_id, away_id in pairs:
        h = _get_team_week_projection(league, week, home_id, meta)
        a = _get_team_week_projection(league, week, away_id, meta)

        margin = round(h.projected_points - a.projected_points, 2)
        favorite = h if margin >= 0 else a
        underdog = a if margin >= 0 else h
        edge = abs(margin)

        def players_blurb(t: TeamWeekProjection) -> str:
            return ", ".join([f"{p.name} ({p.position} {p.projected_points:.1f})" for p in t.top_players])

        # lightweight deterministic quotes (final copy comes from LLM)
        home_quote = f"{h.owner_name}: 'Spreadsheet says dub.'"
        away_quote = f"{a.owner_name}: 'Receipts get cashed this week.'"

        cards.append({
            "matchup": {
                "favorite": favorite.team_name if edge != 0 else "Pick'em",
                "edge_points": edge,
                "home": {
                    "team_id": h.team_id,
                    "team_name": h.team_name,
                    "owner": h.owner_name,
                    "logo": h.logo_url,
                    "proj": h.projected_points,
                    "top_players": players_blurb(h),
                    "record": h.meta.record,
                    "streak": h.meta.streak,
                },
                "away": {
                    "team_id": a.team_id,
                    "team_name": a.team_name,
                    "owner": a.owner_name,
                    "logo": a.logo_url,
                    "proj": a.projected_points,
                    "top_players": players_blurb(a),
                    "record": a.meta.record,
                    "streak": a.meta.streak,
                },
            },
            "quotes": {"home": home_quote, "away": away_quote},
        })
    return cards

# ----------------- LLM: generate weekly preview text -----------------
def _openai_client():
    # mirror gpt_summarizer.py pattern (env-based)
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    return OpenAI(api_key=api_key)

def _default_model() -> str:
    # let users override via env to match your summarizer style
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")

def _preview_prompt(league_id: int, year: int, week: int, cards: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Return messages for chat.completions; structured similarly to your recap prompting:
    - system: voice & rules
    - user: compact JSON of matchups with projections + meta
    """
    import json

    system = (
        "You are LLM-Commissioner, writing a concise, witty WEEKLY PREVIEW for a fantasy football league. "
        "Tone: playful but league-safe (no insults to protected classes), clever puns ok. "
        "Goal: 1 paragraph per matchup with: clear favorite/edge, key projected players, "
        "and a short 1–2 line quote attributed to an owner or star player. "
        "Output in GitHub-flavored Markdown. Use section headers like '## Matchup: Team A vs Team B'. "
        "Do NOT invent stats—only use provided projections/records/streaks."
    )
    # minimize token use: pass only the essentials
    minimal_cards = []
    for c in cards:
        m = c["matchup"]
        minimal_cards.append({
            "home": {
                "team": m["home"]["team_name"],
                "owner": m["home"]["owner"],
                "record": m["home"]["record"],
                "streak": m["home"]["streak"],
                "proj": m["home"]["proj"],
                "top_players": m["home"]["top_players"],
            },
            "away": {
                "team": m["away"]["team_name"],
                "owner": m["away"]["owner"],
                "record": m["away"]["record"],
                "streak": m["away"]["streak"],
                "proj": m["away"]["proj"],
                "top_players": m["away"]["top_players"],
            },
            "favorite": m["favorite"],
            "edge": m["edge_points"],
            "quotes": c.get("quotes", {}),
        })

    user = {
        "league_id": league_id,
        "season": year,
        "week": week,
        "matchups": minimal_cards
    }

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False)}
    ]

def generate_week_preview_from_cards(cards: List[Dict[str, Any]], league_id: int, year: int, week: int,
                                     temperature: float = 0.7, max_tokens: int = 1800) -> str:
    """
    Generate a single Markdown/HTML preview document from prepared preview cards.
    Mirrors the LLM flow used by gpt_summarizer.py (env-based client/model).
    """
    client = _openai_client()
    model = _default_model()
    messages = _preview_prompt(league_id, year, week, cards)

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        # Bubble up—app shows details in expander
        raise

def generate_week_preview(league_id: int, year: int, week: int, espn_s2: str | None = None, swid: str | None = None,
                          temperature: float = 0.7, max_tokens: int = 1800) -> str:
    """
    One-call convenience: fetch projections -> LLM -> Markdown.
    Kept separate from build_weekly_preview_cards so the app can still show raw data.
    """
    cards = build_weekly_preview_cards(league_id, year, week, espn_s2=espn_s2, swid=swid)
    if not cards:
        return "# Weekly Preview\n\n_No matchups found for this week._"
    return generate_week_preview_from_cards(cards, league_id, year, week, temperature=temperature, max_tokens=max_tokens)
