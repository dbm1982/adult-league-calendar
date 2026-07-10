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

    # The schedule is inside a single big <table>
    table = soup.find("table")
    if not table:
        raise ValueError("No schedule table found")

    games = []

    # Each date block is a group of 4 rows:
    # Row 1: date + matchups (multiple columns)
    # Row 2: weekday + fields (multiple columns)
    # Row 3: times (multiple columns)
    # Row 4: refs (multiple columns)
    #
    # Example:
    # <tr> 5/29 | red vs white | orange vs beige | ... </tr>
    # <tr> week 1 | field 2 | field 3 | ... </tr>
    # <tr> 8:15 | 8:15 | 10:00 | ... </tr>
    # <tr> ref – matt | ref – rob | ... </tr>

    rows = table.find_all("tr")

    i = 0
    while i < len(rows):
        cells = [c.get_text(strip=True) for c in rows[i].find_all("td")]
        if not cells:
            i += 1
            continue

        # Detect date row: first cell is mm/dd
        if re.match(r"^\d{1,2}/\d{1,2}$", cells[0]):
            date_str = cells[0]
            matchups = cells[1:]  # columns 1..N

            # Next row: fields
            fields_row = rows[i+1]
            fields = [c.get_text(strip=True) for c in fields_row.find_all("td")][1:]

            # Next row: times
            times_row = rows[i+2]
            raw_times = [c.get_text(strip=True) for c in times_row.find_all("td")][1:]

            # Next row: refs
            refs_row = rows[i+3]
            refs = [c.get_text(strip=True) for c in refs_row.find_all("td")][1:]

            # Parse each column as a separate game
            for col in range(len(matchups)):
                matchup = matchups[col]
                if "vs" not in matchup.lower():
                    continue

                home, away = [t.strip() for t in matchup.split("vs", 1)]

                field = fields[col] if col < len(fields) else "TBD"
                ref = refs[col] if col < len(refs) else "TBD"
                raw_time = raw_times[col] if col < len(raw_times) else None

                # Normalize time formats
                time_clean = raw_time.lower().replace("pm", " pm").replace("am", " am")

                # Try multiple formats
                dt = None
                for fmt in ["%I:%M %p", "%I:%M", "%I %p"]:
                    try:
                        dt = datetime.strptime(f"{YEAR} {date_str} {time_clean}", f"%Y %m/%d {fmt}")
                        break
                    except:
                        continue

                # If still no time → leave as None (TBD)
                if dt is None:
                    dt = datetime.strptime(f"{YEAR} {date_str} 00:00", "%Y %m/%d %H:%M")

                dt = dt.replace(tzinfo=ET)

                games.append({
                    "date": date_str,
                    "time": raw_time,
                    "datetime": dt,
                    "field": field,
                    "ref": ref,
                    "home": home,
                    "away": away
                })

            i += 4
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

