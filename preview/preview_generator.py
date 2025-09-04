# preview/preview_generator.py
from typing import Dict, Any, List
from .espn_preview_fetcher import (
    load_league, get_team_meta, get_week_pairs, get_team_week_projection
)

def _pick_quote(team_name: str, owner_name: str, top_player: str) -> str:
    templates = [
        f"{owner_name}: 'This is the week {team_name} cashes receipts.'",
        f"{top_player}: 'Targets? I ordered the sampler.'",
        f"{owner_name}: 'Spreadsheet says dub.'",
        f"{top_player}: 'I’m him.'",
    ]
    idx = (hash(team_name) + hash(owner_name)) % len(templates)
    return templates[idx]

def _players_blurb(twp) -> str:
    names = [f"{p.name} ({p.position} {p.projected_points:.1f})" for p in twp.top_players]
    return ", ".join(names)

def _format_card(home, away) -> Dict[str, Any]:
    margin = round(home.projected_points - away.projected_points, 2)
    favorite = home if margin >= 0 else away
    underdog = away if margin >= 0 else home
    edge = abs(margin)

    home_quote = _pick_quote(home.team_name, home.owner_name, home.top_players[0].name if home.top_players else home.team_name)
    away_quote = _pick_quote(away.team_name, away.owner_name, away.top_players[0].name if away.top_players else away.team_name)

    return {
        "matchup": {
            "favorite": favorite.team_name if edge != 0 else "Pick'em",
            "edge_points": edge,
            "home": {
                "team_id": home.team_id,
                "team_name": home.team_name,
                "owner": home.owner_name,
                "logo": home.logo_url,
                "proj": home.projected_points,
                "top_players": _players_blurb(home),
                "record": home.meta.record,
                "streak": home.meta.streak,
            },
            "away": {
                "team_id": away.team_id,
                "team_name": away.team_name,
                "owner": away.owner_name,
                "logo": away.logo_url,
                "proj": away.projected_points,
                "top_players": _players_blurb(away),
                "record": away.meta.record,
                "streak": away.meta.streak,
            },
        },
        "quotes": {"home": home_quote, "away": away_quote},
        "headline": f"{favorite.team_name} favored by {edge:.1f} vs {underdog.team_name}" if edge != 0 else "Pick'em",
        "blurb": f"{favorite.team_name} leans on {favorite.top_players[0].name if favorite.top_players else 'their stars'}; "
                 f"{underdog.team_name} needs fireworks from {underdog.top_players[0].name if underdog.top_players else 'somebody'}.",
    }

def build_weekly_preview(league_id: int, year: int, week: int, espn_s2: str | None = None, swid: str | None = None) -> List[Dict[str, Any]]:
    league = load_league(league_id, year, espn_s2, swid)
    meta = get_team_meta(league)
    pairs = get_week_pairs(league, week)
    cards: List[Dict[str, Any]] = []
    for home_id, away_id in pairs:
        h = get_team_week_projection(league, week, home_id, meta)
        a = get_team_week_projection(league, week, away_id, meta)
        cards.append(_format_card(h, a))
    return cards
