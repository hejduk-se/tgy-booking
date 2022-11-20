# tullinge/booking
# https://github.com/tullinge/booking

import sys
from pathlib import Path

# Add parent folder
sys.path.append(str(Path(__file__).parent.parent.absolute()))

from components.db import sql_query
from components.validation import valid_string

data = {}

data["name"] = input("Enter name: ")
data["email"] = input("Enter email: ").lower()

for k, v in data.items():
    if len(v) >= 255 or len(v) < 4:
        raise Exception(f"{k} too long or too short (4-255)")

    if k == "name":
        if not valid_string(v, allow_newline=False, allow_punctuation=False):
            raise Exception("name contains illegal characters")


sql_query(
    f"INSERT INTO admins (name, email) VALUES ('{data['name']}', '{data['email']}')"
)
