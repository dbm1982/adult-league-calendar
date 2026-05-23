import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime, timedelta
import re
from zoneinfo import ZoneInfo

URL = "https://southshoreadultsoccer.com/schedule-union-point-weymouth/"
YOUR_TEAM_KEYWORD = "gray"
YEAR = 2026

# Real America/New_York timezone (correct fix)
ET = ZoneInfo("America/New_York")

WEEKDAYS = {
    "monday","tuesday","wednesday","thursday",
    "friday","saturday","sunday"
}

def fetch_html(url):
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.text

def parse_schedule(html):
    soup = BeautifulSoup(html, "html.parser")
    lines = [l.strip() for l in soup.get_text("\n").split("\n")]
    lines = [l for l in lines if l]

    games = []
    i = 0

    date_pattern = re.compile(r"^\d{1,2}/\d{1,2}$")
    time_pattern = re.compile(r"^\d{1,2}:\d{2}$")

    while i < len(lines):
        line = lines[i]

        if date_pattern.match(line):
            current_date = line
            i += 1

            # Matchups
            matchups = []
            while i < len(lines) and "vs" in lines[i].lower():
                matchups.append(lines[i])
                i += 1

            num_games = len(matchups)
            if num_games == 0:
                continue

            # Skip weekday
            while i < len(lines) and lines[i].lower() in WEEKDAYS:
                i += 1

            # Fields
            fields = []
            while i < len(lines) and lines[i].lower().startswith("field"):
                fields.append(lines[i])
                i += 1

            # Times
            times = []
            while i < len(lines) and time_pattern.match(lines[i]):
                times.append(lines[i])
                i += 1

            # Refs
            refs = []
            while i < len(lines) and lines[i].lower().startswith("ref"):
                refs.append(lines[i])
                i += 1

            # Build games
            for idx in range(num_games):
                matchup = matchups[idx]
                field = fields[idx] if idx < len(fields) else None
                time = times[idx] if idx < len(times) else None
                ref = refs[idx] if idx < len(refs) else None

                home, away = [t.strip() for t in matchup.split("vs", 1)]

                if time:
                    dt = datetime.strptime(
                        f"{YEAR} {current_date} {time} PM",
                        "%Y %m/%d %I:%M %p"
                    )
                else:
                    dt = datetime.strptime(
                        f"{YEAR} {current_date} 00:00",
                        "%Y %m/%d %H:%M"
                    )

                # Attach REAL America/New_York timezone
                dt = dt.replace(tzinfo=ET)

                games.append({
                    "date": current_date,
                    "time": time,
                    "datetime": dt,
                    "field": field,
                    "ref": ref,
                    "home": home,
                    "away": away
                })

            continue

        i += 1

    return games

def filter_for_team(games, keyword):
    keyword = keyword.lower()
    return [
        g for g in games
        if keyword in g["home"].lower() or keyword in g["away"].lower()
    ]

def create_ics(games, filename):
    cal = Calendar()

    for g in games:
        event = Event()

        title = f"{g['home'].title()} vs {g['away'].title()}"
        event.name = f"Adult Soccer Game: {title}"

        # Use timezone-aware datetimes (zoneinfo)
        event.begin = g["datetime"]
        event.end = g["datetime"] + timedelta(minutes=90)

        # FIXED: Always use the full address as the location
        event.location = "170 Memorial Grove Ave, Weymouth, MA 02190"

        # Notes now include the field number instead of location
        ref_clean = g["ref"].replace("ref –", "").strip().title() if g["ref"] else "TBD"
        field_clean = g["field"].title() if g["field"] else "TBD"

        event.description = (
            f"Field: {field_clean}\n"
            f"Referee: {ref_clean}"
        )

        cal.events.add(event)

    with open(filename, "w") as f:
        f.writelines(cal)



def build_team_game_rows(games):
    """
    Sorts games chronologically, assigns game_id in true date order,
    and expands each game into two rows (one per team).
    """

    # Sort by datetime
    games_sorted = sorted(games, key=lambda g: g["datetime"])

    rows = []
    game_counter = 1

    for g in games_sorted:
        game_id = f"G{game_counter}"

        date_str = g["datetime"].strftime("%Y-%m-%d")
        time_str = g["datetime"].strftime("%I:%M %p")
        field_clean = g["field"].title() if g["field"] else "TBD"

        # Home team row
        rows.append({
            "game_id": game_id,
            "team_id": g["home"].title(),
            "date": date_str,
            "time": time_str,
            "opponent": g["away"].title(),
            "field": field_clean
        })

        # Away team row
        rows.append({
            "game_id": game_id,
            "team_id": g["away"].title(),
            "date": date_str,
            "time": time_str,
            "opponent": g["home"].title(),
            "field": field_clean
        })

        game_counter += 1

    return rows



def write_team_games_file(rows, filename="all_team_games.tsv"):
    with open(filename, "w") as f:
        f.write("game_id\tteam_id\tdate\ttime\topponent\tfield\n")
        for r in rows:
            f.write(
                f"{r['game_id']}\t{r['team_id']}\t{r['date']}\t"
                f"{r['time']}\t{r['opponent']}\t{r['field']}\n"
            )



def extract_all_team_keywords(games):
    """
    Returns a sorted list of unique team keywords (colors).
    Example: ['gray', 'purple', 'navy', 'yellow']
    """
    keywords = set()

    for g in games:
        for side in (g["home"], g["away"]):
            parts = side.lower().split()
            for p in parts:
                if p.isalpha():   # keep simple words only
                    keywords.add(p)

    return sorted(keywords)


def main():
    html = fetch_html(URL)
    games = parse_schedule(html)

    # Identify all team keywords (colors)
    all_keywords = extract_all_team_keywords(games)
    print("Detected team keywords:", all_keywords)

    # Build ICS for each team
    for keyword in all_keywords:
        team_games = filter_for_team(games, keyword)

        if not team_games:
            continue

        filename = f"team_{keyword}.ics"
        create_ics(team_games, filename)
        print(f"Created {filename} with {len(team_games)} games.")

    # Also produce teams.json for reference
    import json
    with open("teams.json", "w") as f:
        json.dump(all_keywords, f, indent=2)

    print("All team schedules generated.")
    
        # Build the full team-centric schedule file
    team_rows = build_team_game_rows(games)
    write_team_games_file(team_rows)
    print(f"Wrote {len(team_rows)} team-game rows to all_team_games.tsv")



if __name__ == "__main__":
    main()

