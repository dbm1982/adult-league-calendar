import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime, timedelta
import re
from zoneinfo import ZoneInfo
import json

URL = "https://southshoreadultsoccer.com/schedule-union-point-weymouth/"
YEAR = datetime.now().year

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

    rows = table.find_all("tr")
    games = []

    # State machine
    current_date = None
    matchups = None
    fields = None
    times = None
    refs = None

    def flush_block():
        """Build game objects when all four components exist."""
        nonlocal games, current_date, matchups, fields, times, refs

        if not (current_date and matchups):
            return

        # Normalize lists to same length
        max_len = max(len(matchups), len(fields), len(times), len(refs))
        def pad(lst):
            return lst + ["TBD"] * (max_len - len(lst))

        m = pad(matchups)
        f = pad(fields)
        t = pad(times)
        r = pad(refs)

        for col in range(max_len):
            matchup = m[col]
            if "vs" not in matchup.lower().replace(".", "").replace(" ", ""):
                continue

            home_raw, away_raw = [x.strip() for x in matchup.split("vs")]

            NORMALIZE = {
                "grey": "gray",
                "biege": "beige",
            }
            
            home = NORMALIZE.get(home_raw.lower(), home_raw.lower())
            away = NORMALIZE.get(away_raw.lower(), away_raw.lower())
            

            raw_time = t[col].strip()
            time_clean = raw_time.lower().replace("pm", "").replace("am", "").strip()
            time_clean = time_clean.replace(" ", "")

            dt = None
            for fmt in ["%I:%M", "%I"]:
                try:
                    dt = datetime.strptime(
                        f"{YEAR} {current_date} {time_clean} PM",
                        f"%Y %m/%d {fmt} %p"
                    )
                    break
                except:
                    continue

            if dt is None:
                dt = datetime.strptime(
                    f"{YEAR} {current_date} 08:00 PM",
                    "%Y %m/%d %I:%M %p"
                )

            dt = dt.replace(tzinfo=ET)

            games.append({
                "date": current_date,
                "time": raw_time,
                "datetime": dt,
                "field": f[col],
                "ref": r[col],
                "home": home,
                "away": away
            })

        # Reset state
        current_date = None
        matchups = None
        fields = None
        times = None
        refs = None

    # Iterate through rows
    for row in rows:
        cells = [c.get_text(strip=True) for c in row.find_all("td")]
        if not cells:
            continue

        # DATE ROW
        if re.match(r"^\d{1,2}/\d{1,2}", cells[0]):
            flush_block()
            current_date = cells[0]
            matchups = cells[1:]
            fields = []
            times = []
            refs = []
            continue

        # FIELD ROW (contains "field" in any cell)
        if any("field" in c.lower() for c in cells):
            fields = cells[1:]
            continue

        # TIME ROW (contains times like 5:30, 7:15, 10:00)
        if any(re.match(r"^\d{1,2}:\d{2}", c) for c in cells):
            times = cells[1:]
            continue

        # REF ROW (contains "ref")
        if any("ref" in c.lower() for c in cells):
            refs = cells[1:]
            continue

        # IGNORE metadata rows like "week 5", "monday", etc.
        continue

    # Flush last block
    flush_block()

    return games


def filter_for_team(games, keyword):

    keyword = keyword.lower()

    return [
        g for g in games
        if (
            keyword in g["home"].lower()
            or
            keyword in g["away"].lower()
        )
    ]


def create_ics(games, filename):

    cal = Calendar()

    for g in games:

        event = Event()

        title = (
            f"{g['home'].title()} "
            f"vs "
            f"{g['away'].title()}"
        )

        event.name = (
            f"Adult Soccer Game: {title}"
        )

        event.begin = g["datetime"]

        event.end = (
            g["datetime"]
            + timedelta(minutes=90)
        )

        event.location = (
            "170 Memorial Grove Ave, "
            "Weymouth, MA 02190"
        )

        ref_clean = (
            g["ref"]
            .replace("ref –", "")
            .strip()
            .title()
            if g["ref"]
            else "TBD"
        )

        field_clean = (
            g["field"].title()
            if g["field"]
            else "TBD"
        )

        event.description = (
            f"Field: {field_clean}\n"
            f"Referee: {ref_clean}"
        )

        cal.events.add(event)

    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as f:

        f.writelines(cal)


def build_team_game_rows(games):

    games_sorted = sorted(
        games,
        key=lambda g: g["datetime"]
    )

    rows = []
    game_counter = 1

    for g in games_sorted:

        game_id = f"G{game_counter}"

        date_str = g["datetime"].strftime(
            "%Y-%m-%d"
        )

        time_str = g["datetime"].strftime(
            "%I:%M %p"
        )

        field_clean = (
            g["field"].title()
            if g["field"]
            else "TBD"
        )

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


def write_team_games_file(
    rows,
    filename="all_team_games.tsv"
):

    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            "game_id\tteam_id\tdate\t"
            "time\topponent\tfield\n"
        )

        for r in rows:

            f.write(
                f"{r['game_id']}\t"
                f"{r['team_id']}\t"
                f"{r['date']}\t"
                f"{r['time']}\t"
                f"{r['opponent']}\t"
                f"{r['field']}\n"
            )


def extract_all_team_keywords(games):

    keywords = set()

    for g in games:

        for side in (
            g["home"],
            g["away"]
        ):

            parts = side.lower().split()

            for p in parts:

                if p.isalpha():
                    keywords.add(p)

    return sorted(keywords)


def main():

    html = fetch_html(URL)

    games = parse_schedule(html)

    # ------------------------------------------
    # MASTER CALENDAR
    # ------------------------------------------

    create_ics(
        games,
        "master_schedule.ics"
    )

    print(
        f"Created master_schedule.ics "
        f"with {len(games)} games."
    )

    # ------------------------------------------
    # TEAM CALENDARS
    # ------------------------------------------

    all_keywords = extract_all_team_keywords(
        games
    )

    print(
        "Detected team keywords:",
        all_keywords
    )

    for keyword in all_keywords:

        team_games = filter_for_team(
            games,
            keyword
        )

        if not team_games:
            continue

        filename = (
            f"team_{keyword}.ics"
        )

        create_ics(
            team_games,
            filename
        )

        print(
            f"Created {filename} "
            f"with {len(team_games)} games."
        )

    # ------------------------------------------
    # TEAM LIST
    # ------------------------------------------

    with open(
        "teams.json",
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            all_keywords,
            f,
            indent=2
        )

    print(
        "All team schedules generated."
    )

    # ------------------------------------------
    # GAMES TSV
    # ------------------------------------------

    team_rows = build_team_game_rows(
        games
    )

    write_team_games_file(
        team_rows
    )

    print(
        f"Wrote {len(team_rows)} "
        f"team-game rows to "
        f"all_team_games.tsv"
    )


if __name__ == "__main__":
    main()
