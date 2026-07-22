import os
import json
import gspread
from google.oauth2.service_account import Credentials

# --------------------------------------------------
# CONFIG
# --------------------------------------------------

SPREADSHEET_ID = "1afoSDWnUlB6ZN5Wlz4CDyX1whhzNNHxm6vCINs-2LDM"
SHEET_NAME = "Games"

# --------------------------------------------------
# GOOGLE AUTH
# --------------------------------------------------

service_account_info = json.loads(
    os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
)

creds = Credentials.from_service_account_info(
    service_account_info,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
)

client = gspread.authorize(creds)

spreadsheet = client.open_by_key(
    SPREADSHEET_ID
)

sheet = spreadsheet.worksheet(
    SHEET_NAME
)

# --------------------------------------------------
# LOAD TSV
# --------------------------------------------------

rows = []

with open(
    "all_team_games.tsv",
    "r",
    encoding="utf-8"
) as f:

    lines = f.readlines()

for line in lines[1:]:

    parts = line.strip().split("\t")

    if len(parts) != 6:
        continue

    rows.append(parts)

# --------------------------------------------------
# SAFETY CHECK
# --------------------------------------------------

if len(rows) == 0:

    raise Exception(
        "No games found in all_team_games.tsv - refusing to overwrite Games sheet."
    )

# --------------------------------------------------
# REBUILD GAMES TAB
# --------------------------------------------------

sheet.batch_clear(
    ["A:F"]
)

sheet.update(
    "A1:F1",
    [[
        "game_id",
        "team_id",
        "date",
        "time",
        "opponent",
        "field"
    ]]
)

sheet.update(
    f"A2:F{len(rows)+1}",
    rows
)

print(
    f"Updated Games sheet with {len(rows)} rows."
)
