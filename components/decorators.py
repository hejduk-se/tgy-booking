# tullinge/booking
# https://github.com/tullinge/booking

# imports
from functools import wraps
from flask import session, redirect

# components import
from components.db import sql_query, dict_sql_query


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # check if user is logged in
        if not session.get("logged_in"):
            return redirect("/login")

        # check if student exists
        student = sql_query(
            "SELECT * FROM students WHERE id = %s", params=(session.get("id"),)
        )

        if not student:
            session.pop("id", None)
            session.pop("logged_in", False)

            return redirect("/login")

        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):  # lgtm [py/similar-function]
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # check if admin is logged in
        if not session.get("admin_logged_in"):
            return redirect("/admin/login")

        # check if admin exists aswell
        if not sql_query(
            "SELECT id FROM admins WHERE id = %s", params=(session.get("admin_id"),)
        ):
            session.pop("admin_logged_in", False)
            session.pop("admin_id", None)

            return redirect("/admin/login")

        return f(*args, **kwargs)

    return decorated_function


def activity_leader_login_required(f):  # lgtm [py/similar-function]
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # check if leader is logged in
        if not session.get("leader_logged_in"):
            return redirect("/leader/login")

        # check if leader exists aswell
        if not sql_query(
            "SELECT id FROM leaders WHERE id = %s", params=(session.get("leader_id"),)
        ):
            session.pop("leader_logged_in", False)
            session.pop("leader_id", None)

            return redirect("/leader/login")

        return f(*args, **kwargs)

    return decorated_function


def user_setup_completed(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # decorator should be after @login_required, therefore assume user auth
        student = dict_sql_query(
            "SELECT * FROM students WHERE id = %s",
            fetchone=True,
            params=(session.get("id"),),
        )

        if student:
            if not (
                student["class_id"]
            ):  # checks if user-configurable variables are defined
                # redirect to initial setup page
                return redirect("/setup")
        else:
            # raise exception, should not occur if authentication has succeeded
            raise Exception("user id does not exist")

        return f(*args, **kwargs)

    return decorated_function


def user_not_setup(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # decorator should be after @login_required, therefore assume user auth
        student = dict_sql_query(
            "SELECT * FROM students WHERE id = %s",
            fetchone=True,
            params=(session.get("id"),),
        )

        if student:
            if student["class_id"]:
                # user has already configured
                return redirect("/")
        else:
            # raise exception, should not occur if authentication has succeeded
            raise Exception("user id does not exist")

        return f(*args, **kwargs)

    return decorated_function


def booking_blocked(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # check setting
        if (
            dict_sql_query(
                "SELECT value FROM settings WHERE identifier='booking_locked'",
                fetchone=True,
            )["value"]
            == "1"
        ):
            session.pop("id", None)
            session.pop("logged_in", False)

            return redirect("/login")

        return f(*args, **kwargs)

    return decorated_function
