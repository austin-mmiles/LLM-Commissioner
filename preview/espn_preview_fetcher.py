# preview/espn_preview_fetcher.py
from dataclasses import dataclass
from typing import Dict, List, Tuple
from espn_api.football import League

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

def load_league(league_id: int, year: int, espn_s2: str | None = None, swid: str | None = None) -> League:
    return League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)

def get_team_meta(league: League) -> Dict[int, TeamMeta]:
    meta: Dict[int, TeamMeta] = {}
    for t in league.teams:
        # owner name can vary depending on espn_api version/league privacy
        owner_name = getattr(t, "owner", None)
        if isinstance(owner_name, str) and owner_name:
            oname = owner_name
        else:
            # fallback to something stable
            oname = getattr(t, "team_abbrev", None) or "Owner"

        record = f"{t.wins}-{t.losses}{('-'+str(t.ties)) if getattr(t, 'ties', 0) else ''}"
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

def get_week_pairs(league: League, week: int) -> List[Tuple[int, int]]:
    pairs: List[Tuple[int, int]] = []
    for m in league.scoreboard(week=week):
        pairs.append((m.home_team.team_id, m.away_team.team_id))
    return pairs

def get_team_week_projection(league: League, week: int, team_id: int, meta: Dict[int, TeamMeta]) -> TeamWeekProjection:
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
                projected_points += proj
            players.append(PlayerProj(
                player_id=str(getattr(p, "playerId", getattr(p, "id", ""))),
                name=getattr(p, "name", "Player"),
                position=pos,
                projected_points=float(proj),
                is_starter=is_starter
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
