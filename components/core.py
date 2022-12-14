# tullinge/booking
# https://github.com/tullinge/booking

# imports
import string
import hashlib
import binascii
import os
import random

from flask import request

# components import
from components.db import sql_query


def basic_validation(expected_values):
    """
    Basic input/form validation, checks if all expected values are present

    :param expected_values, list of values that should be defined
    """

    if len(request.form) != len(expected_values):
        return False

    for v in expected_values:
        if not request.form.get(v):
            return False

    return True


def calculate_available_spaces(activity_id):
    """Returns integer of available spaces using specified activity_id"""

    activity = sql_query(f"SELECT * FROM activities WHERE id={activity_id}")[0]
    students = sql_query(f"SELECT * FROM students WHERE chosen_activity={activity_id}")

    return activity[2] - len(students)


def hash_password(password):
    # Hash a password for storing

    salt = hashlib.sha256(os.urandom(60)).hexdigest().encode("ascii")
    pwdhash = hashlib.pbkdf2_hmac("sha512", password.encode("utf-8"), salt, 100000)

    pwdhash = binascii.hexlify(pwdhash)

    return (salt + pwdhash).decode("ascii")


def verify_password(stored_password, provided_password):
    # Verify a stored password against one provided by user

    salt = stored_password[:64]
    stored_password = stored_password[64:]

    pwdhash = hashlib.pbkdf2_hmac(
        "sha512", provided_password.encode("utf-8"), salt.encode("ascii"), 100000
    )

    pwdhash = binascii.hexlify(pwdhash).decode("ascii")

    return pwdhash == stored_password


def random_string(length=10):
    """Generate a random string of fixed length"""

    return "".join(
        random.choice(string.ascii_uppercase + string.digits) for i in range(length)
    )


def get_client_ip():
    if request.environ.get("HTTP_X_FORWARDED_FOR") is None:
        remote_ip = request.environ["REMOTE_ADDR"]
    else:
        remote_ip = request.environ["HTTP_X_FORWARDED_FOR"]

    return remote_ip


def dict_search(list_dictionary, key, value):
    """
    Searches for dicts in list of dictionaries where a specific key has a specific value

    :param list list_dictionary: A list of dictionaries
    :param str key: Key of dictionary we're looking for
    :param str value: Value of the key we're looking for
    """

    return [element for element in list_dictionary if element[key] == value]


def allowed_file(filename: str, allowed_file_extensions: list):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in allowed_file_extensions
    )
