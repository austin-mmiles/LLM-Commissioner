# preview/preview_generator.py
from __future__ import annotations

import os
import json
import re
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
    record: str
    logo_url: str  # kept for compatibility, not used in output
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
    projected_points: float  # SUM OF STARTERS ONLY (internal; not displayed)
    top_players: List[PlayerProj]  # STARTERS ONLY (top 4)
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
            record=record,
            logo_url=str(getattr(t, "logo_url", "") or ""),
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

def _is_starter_slot(slot_value: Any) -> bool:
    """
    Treat only 'BE' (bench) as non-starter.
    Everything else (including FLEX/IR/etc.) counts as starting for projections.
    """
    try:
        return str(slot_value).upper() != "BE"
    except Exception:
        return True  # fallback to True unless we can prove it's bench

def _get_team_week_projection(league: League, week: int, team_id: int, meta: Dict[int, TeamMeta]) -> TeamWeekProjection:
    """
    Build a team projection for THIS WEEK from STARTERS ONLY.
    - Sum projected points for starters only (bench excluded)
    - Top players = top 4 starters by projected points
    """
    box_scores = league.box_scores(week=week)
    projected_points = 0.0
    starters: List[PlayerProj] = []

    for box in box_scores:
        lineup = None
        if getattr(box, "home_team", None) and getattr(box.home_team, "team_id", None) == team_id:
            lineup = getattr(box, "home_lineup", None)
        elif getattr(box, "away_team", None) and getattr(box.away_team, "team_id", None) == team_id:
            lineup = getattr(box, "away_lineup", None)
        if lineup is None:
            continue

        for p in lineup:
            proj = getattr(p, "projected_points", None)
            if proj is None:
                continue

            slot = getattr(p, "slot_position", getattr(p, "position", ""))
            if not _is_starter_slot(slot):
                continue  # 🚫 BENCH EXCLUDED COMPLETELY

            starters.append(PlayerProj(
                player_id=str(getattr(p, "playerId", getattr(p, "id", "")) or ""),
                name=str(getattr(p, "name", "Player")),
                position=str(slot),
                projected_points=float(proj),
                is_starter=True,
            ))
            projected_points += float(proj)

    starters.sort(key=lambda x: -x.projected_points)
    top_players = starters[:4]  # ⬅️ top 4 starters
    tm = meta[team_id]
    return TeamWeekProjection(
        team_id=team_id,
        team_name=tm.team_name,
        projected_points=round(projected_points, 2),  # internal only
        top_players=top_players,
        meta=tm,
    )


# ===============================
# Build "cards" for UI + quotes
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

        # ✅ Edge & featured strictly from STARTERS ONLY
        margin = round(h.projected_points - a.projected_points, 2)
        favorite = h if margin >= 0 else a
        edge = abs(margin)
        combined = round(h.projected_points + a.projected_points, 2)

        def players_list(t: TeamWeekProjection) -> List[Dict[str, Any]]:
            return [
                {"name": p.name, "position": p.position, "proj": round(p.projected_points, 1)}
                for p in t.top_players
            ]

        cards.append({
            "matchup": {
                "favorite": favorite.team_name if edge != 0 else "Pick'em",
                "edge_points": edge,                     # numeric spread (starters-only)
                "combined_proj_starters": combined,      # internal only (for featured pick)
                "home": {
                    "team_name": h.team_name,
                    "record": h.meta.record,
                    "streak": h.meta.streak,
                    "top_players_list": players_list(h),  # top 4 starters
                },
                "away": {
                    "team_name": a.team_name,
                    "record": a.meta.record,
                    "streak": a.meta.streak,
                    "top_players_list": players_list(a),  # top 4 starters
                },
            }
        })

    # ⭐ Featured = highest combined starters projection (not displayed)
    if cards:
        best_idx = max(
            range(len(cards)),
            key=lambda i: cards[i]["matchup"].get("combined_proj_starters", 0.0)
        )
        cards[best_idx]["matchup"]["is_featured"] = True
    return cards


# ===============================
# OpenAI client (quotes only)
# ===============================
def _openai_client():
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    return OpenAI(api_key=api_key)

def _default_model() -> str:
    # Small/fast; we only need short quotes + a closer.
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")

def _projection_source() -> str:
    return os.getenv("PREVIEW_PROJECTION_SOURCE", "ESPN")


# ===============================
# Fallback quote pool (TEXT ONLY — no attribution/punctuation)
# ===============================
_FALLBACK_QUOTES = [
    "We just need clean execution and a next-play mindset",
    "Control the line, protect the rock, finish the drive",
    "Eyes up, hands strong, and we’ll let the scoreboard do the talking",
    "Respect every snap and keep the pedal down",
    "Fast start, clean finish — that’s the recipe",
    "Trust the read, trust the teammate, trust the plan",
    "Play smart, play physical, play together",
    "Win situations — third down, red zone, two-minute — and you win the game",
    "Stack good plays, stack good quarters, stack a win",
    "No hero ball — just do your job and the big plays come",
    "Tempo, toughness, and takeaways — that’s our identity",
    "Be the hammer, not the nail",
    "Details matter — ball security and discipline travel",
    "We want to be the last team still swinging",
]

def _fallback_quote_for(team: str, salt: int) -> str:
    idx = (abs(hash(team)) + salt) % len(_FALLBACK_QUOTES)
    return _FALLBACK_QUOTES[idx]


# ===============================
# LLM: generate quotes + closers ONLY (JSON)
# ===============================
def _quotes_prompt_payload(league_id: int, year: int, week: int, cards: List[Dict[str, Any]]) -> dict:
    items = []
    for c in cards:
        m = c["matchup"]
        items.append({
            "home_team": m["home"]["team_name"],
            "away_team": m["away"]["team_name"],
            "favorite": m["favorite"],
            "edge_points": m["edge_points"],
        })
    return {
        "league_id": league_id,
        "season": year,
        "week": week,
        "items": items,
        "style_rules": [
            'Return STRICT JSON: a list where each element has keys: "home_team","away_team","home_quote","away_quote","closer".',
            'The "home_quote" and "away_quote" MUST be the quote TEXT ONLY (no quotes, no commas, no attribution).',
            'We will add the formatting like `"text ," The Team coach says.` ourselves.',
            "Make home and away quotes clearly different in tone/wording (vary metaphors: weather, chess, racing, construction, boxing, cooking, etc.).",
            "Quotes must be short, punchy, clean. No profanity. No owners or real-person names.",
            "Closers: one short hype sentence (pun welcome), no invented history.",
        ]
    }

def _force_json(text: str) -> Any:
    """Parse JSON even if the model wraps it in ```json fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].lstrip()
    return json.loads(cleaned)

def _strip_existing_attrib(q: str, team: str) -> str:
    """
    Remove any trailing attribution like: ,\" The <Team> coach says. (case-insensitive)
    Also strips any wrapping quotes and trailing punctuation we will re-add.
    """
    s = q.strip().strip('"').strip("“”").strip()
    # remove things like: , The Team coach says.  or ," The Team coach says.
    patterns = [
        rf'\s*,?\s*["“”]?\s*,?\s*The\s+{re.escape(team)}\s+coach\s+says\.?$',  # The Team coach says.
        r'\s*,?\s*The\s+coach\s+says\.?$',                                     # The coach says.
        r'\s*,?\s*coach\s+says\.?$',                                           # coach says.
    ]
    for pat in patterns:
        s = re.sub(pat, '', s, flags=re.IGNORECASE)
    return s.strip()

def _ensure_distinct(q_home: str, q_away: str, home_team: str, away_team: str) -> tuple[str, str]:
    """
    If quotes are identical or too similar, replace away with a different fallback.
    """
    def _norm(s: str) -> str:
        return " ".join(s.lower().split())
    if _norm(q_home) == _norm(q_away):
        q_away = _fallback_quote_for(away_team, salt=7)
    return q_home, q_away

def _format_quote_text(text: str, team: str) -> str:
    """
    Format the final line EXACTLY as:
      "<text> ," The <Team> coach says.
    Ensures a space before the comma inside the quotes and no duplicate attributions.
    """
    base = _strip_existing_attrib(text or "", team)
    if not base:
        base = "Play fast, play smart, finish"
    # ensure internal trailing ' ,'
    base = base.rstrip(' ,')
    base = base + " ,"
    return f"\"{base}\" The {team} coach says."

def _get_quotes_for_matchups(
    cards: List[Dict[str, Any]],
    league_id: int,
    year: int,
    week: int,
    temperature: float = 0.7,
    max_tokens: int = 1000,
) -> List[Dict[str, str]]:
    """
    Ask the LLM for quotes + closers only, as JSON aligned with the order of `cards`.
    Ensures distinct quotes and formats attribution exactly once.
    """
    client = _openai_client()
    model = _default_model()

    payload = _quotes_prompt_payload(league_id, year, week, cards)
    messages = [
        {"role": "system", "content": (
            "You are LLM-Commissioner. "
            "Reply with STRICT JSON ONLY. No preamble, no code fences unless necessary for JSON validity."
        )},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
    ]

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = resp.choices[0].message.content
        data = _force_json(content)
        if not isinstance(data, list):
            raise ValueError("Expected a JSON list.")
    except Exception:
        # Fallback: build quotes from pool
        data = []
        for c in cards:
            h = c["matchup"]["home"]["team_name"]
            a = c["matchup"]["away"]["team_name"]
            data.append({
                "home_team": h,
                "away_team": a,
                "home_quote": _fallback_quote_for(h, salt=1),
                "away_quote": _fallback_quote_for(a, salt=2),
                "closer": "This one could turn into a fireworks show — bring popcorn! 🍿",
            })

    # Enforce distinctness & final formatting
    cleaned: List[Dict[str, str]] = []
    for i, c in enumerate(cards):
        m = c["matchup"]
        h = m["home"]["team_name"]
        a = m["away"]["team_name"]
        rec = data[i] if i < len(data) else {}

        hq_raw = rec.get("home_quote") or _fallback_quote_for(h, salt=3)
        aq_raw = rec.get("away_quote") or _fallback_quote_for(a, salt=4)
        closer = rec.get("closer") or "Whistles ready — this has the makings of a highlight reel. 🎬"

        hq_raw, aq_raw = _ensure_distinct(hq_raw, aq_raw, h, a)
        hq = _format_quote_text(hq_raw, h)
        aq = _format_quote_text(aq_raw, a)

        cleaned.append({
            "home_team": h,
            "away_team": a,
            "home_quote": hq,
            "away_quote": aq,
            "closer": closer,
        })
    return cleaned


# ===============================
# Render helpers
# ===============================
def _fmt_players_inline(players: List[Dict[str, Any]]) -> str:
    """Format: Name (Pos, Pts) joined by commas."""
    parts = []
    for p in players[:4]:
        nm = p.get("name", "Player")
        pos = p.get("position", "")
        pts = p.get("proj", 0)
        parts.append(f"{nm} ({pos}, {pts})")
    return ", ".join(parts)

def _edge_line(favorite: str, edge: float) -> str:
    if favorite == "Pick'em" or edge == 0:
        return "_Edge:_ **Pick'em**"
    return f"_Edge:_ **{favorite} by {edge}**"


# ===============================
# Build final preview (deterministic structure; NO LOGOS)
# ===============================
def generate_week_preview(
    league_id: int,
    year: int,
    week: int,
    espn_s2: str | None = None,
    swid: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 1000,
) -> str:
    """
    Deterministic structure (records/top-4/edge) + LLM quotes/closers.
    Returns a single Markdown document. No logos are displayed.
    """
    cards = build_weekly_preview_cards(league_id, year, week, espn_s2=espn_s2, swid=swid)
    if not cards:
        return f"# Weekly Preview (Week {week})\n\n_No matchups found for this week._"

    # Get quotes/closers in the same order
    quotes = _get_quotes_for_matchups(cards, league_id, year, week, temperature=temperature, max_tokens=max_tokens)

    # Reorder so featured appears first
    featured = [c for c in cards if c["matchup"].get("is_featured")]
    others = [c for c in cards if not c["matchup"].get("is_featured")]
    ordered = featured + others

    # Map quotes by (home,away)
    qmap: Dict[Tuple[str, str], Dict[str, str]] = {}
    for q in quotes:
        qmap[(q["home_team"], q["away_team"])] = q

    source = _projection_source()

    lines: List[str] = []
    lines.append(f"# WEEK {week} PREVIEW: LET'S RUMBLE! 🏈🔥")
    lines.append("")

    if featured:
        lines.append("## ⭐ Matchup of the Week")
        lines.append("")

    # Render each matchup (featured first)
    for c in ordered:
        m = c["matchup"]
        home = m["home"]; away = m["away"]
        key = (home["team_name"], away["team_name"])
        q = qmap.get(key, {
            "home_quote": _format_quote_text("Win the down, win the day", home["team_name"]),
            "away_quote": _format_quote_text("Play fast, play smart, finish", away["team_name"]),
            "closer": "This one could turn into a fireworks show — bring popcorn! 🍿"
        })

        # Header WITHOUT logos; include records next to team names
        lines.append(
            f"## {'⭐ ' if m.get('is_featured') else ''}Matchup: "
            f"{home['team_name']} ({home['record']}) vs {away['team_name']} ({away['record']})"
        )
        lines.append(_edge_line(m['favorite'], m['edge_points']))
        lines.append("")

        # Separate top-starters lines for each team
        lines.append(f"**Top starters — {home['team_name']}:** {_fmt_players_inline(home['top_players_list'])}")
        lines.append(f"**Top starters — {away['team_name']}:** {_fmt_players_inline(away['top_players_list'])}")
        lines.append("")

        # Flavor paragraphs mentioning each side's top projected starter if present
        h_top = home['top_players_list'][0] if home['top_players_list'] else None
        a_top = away['top_players_list'][0] if away['top_players_list'] else None
        if h_top:
            lines.append(
                f"Based on projections from {source}, {home['team_name']} can expect a **{h_top['proj']}** point spark from "
                f"**{h_top['name']}** ({h_top['position']}) — if they keep the chains moving, "
                f"the scoreboard might light up like a pinball machine. ⚡️📈"
            )
        else:
            lines.append(f"Based on projections from {source}, {home['team_name']} will lean on their starters to set the tone. ⚡️")
        lines.append(q["home_quote"])
        lines.append("")

        if a_top:
            lines.append(
                f"Based on projections from {source}, {away['team_name']} can expect **{a_top['proj']}** shiny points from "
                f"**{a_top['name']}** ({a_top['position']}) — clean pockets and crisp routes could turn drives into paydirt. 🔥🚀"
            )
        else:
            lines.append(f"Based on projections from {source}, {away['team_name']} needs rhythm early to stay on schedule. 🔥")
        lines.append(q["away_quote"])

        # Closer
        lines.append("")
        lines.append(f"*Final whistle:* {q['closer']}")
        lines.append("")

    return "\n".join(lines)


# (Optional) Compatibility shim if other code calls this name:
def generate_week_preview_from_cards(
    cards: List[Dict[str, Any]],
    league_id: int,
    year: int,
    week: int,
    temperature: float = 0.7,
    max_tokens: int = 1000,
    presence_penalty: float = 0.0,
    frequency_penalty: float = 0.0,
) -> str:
    # Render through the single entry point to ensure consistent layout.
    return generate_week_preview(league_id, year, week, temperature=temperature, max_tokens=max_tokens)
