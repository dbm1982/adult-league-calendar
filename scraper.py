import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime, timedelta
import re
from zoneinfo import ZoneInfo

URL = "https://southshoreadultsoccer.com/schedule-union-point-weymouth/"
YOUR_TEAM_KEYWORD = "gray"
YEAR = 2026

ET = ZoneInfo("America/New_York")

def fetch_html(url):
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.text


def parse_schedule(html):
    soup = BeautifulSoup(html, "html.parser")

    table = soup.find("table")
    if not table:
        raise ValueError("No schedule table found")

    games = []
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
            matchups = cells[1:]

            # Fields row
            fields_row = rows[i+1]
            fields = [c.get_text(strip=True) for c in fields_row.find_all("td")][1:]

            # Times row
            times_row = rows[i+2]
            raw_times = [c.get_text(strip=True) for c in times_row.find_all("td")][1:]

            # Refs row
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

                # -------------------------------
                # NORMALIZE ALL TIMES TO PM
                # -------------------------------
                time_clean = (raw_time or "").lower().strip()

                # Remove am/pm markers entirely
                time_clean = time_clean.replace("pm", "").replace("am", "").strip()

                # Remove spaces: "8 pm" → "8", "8:15 pm" → "8:15"
                time_clean = time_clean.replace(" ", "")

                # Try parsing formats
                dt = None
                for fmt in ["%I:%M", "%I"]:
                    try:
                        dt = datetime.strptime(
                            f"{YEAR} {date_str} {time_clean} PM",
                            f"%Y %m/%d {fmt} %p"
                        )
                        break
                    except:
                        continue

                # If still no time, fallback to a reasonable PM time
                if dt is None:
                    dt = datetime.strptime(
                        f"{YEAR} {date_str} 08:00 PM",
                        "%Y %m/%d %I:%M %p"
                    )

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

        event.begin = g["datetime"]
        event.end = g["datetime"] + timedelta(minutes=90)

        event.location = "170 Memorial Grove Ave, Weymouth, MA 02190"

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
    games_sorted = sorted(games, key=lambda g: g["datetime"])

    rows = []
    game_counter = 1

    for g in games_sorted:
        game_id = f"G{game_counter}"

        date_str = g["datetime"].strftime("%Y-%m-%d")
        time_str = g["datetime"].strftime("%I:%M %p")
        field_clean = g["field"].title() if g["field"] else "TBD"

        rows.append({
            "game_id": game_id,
            "team_id": g["home"].title(),
            "date": date_str,
            "time": time_str,
            "opponent": g["away"].title(),
            "field": field_clean
        })

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
    keywords = set()

    for g in games:
        for side in (g["home"], g["away"]):
            parts = side.lower().split()
            for p in parts:
                if p.isalpha():
                    keywords.add(p)

    return sorted(keywords)


def main():
    html = fetch_html(URL)
    games = parse_schedule(html)

    all_keywords = extract_all_team_keywords(games)
    print("Detected team keywords:", all_keywords)

    for keyword in all_keywords:
        team_games = filter_for_team(games, keyword)
        if not team_games:
            continue

        filename = f"team_{keyword}.ics"
        create_ics(team_games, filename)
        print(f"Created {filename} with {len(team_games)} games.")

    import json
    with open("teams.json", "w") as f:
        json.dump(all_keywords, f, indent=2)

    print("All team schedules generated.")

    team_rows = build_team_game_rows(games)
    write_team_games_file(team_rows)
    print(f"Wrote {len(team_rows)} team-game rows to all_team_games.tsv")


if __name__ == "__main__":
    main()
