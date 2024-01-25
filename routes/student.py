# tullinge/booking
# https://github.com/tullinge/booking

# imports
from flask import Blueprint, render_template, redirect, request, session, jsonify, abort

# components import
from components.decorators import (
    login_required,
    user_setup_completed,
    user_not_setup,
    booking_blocked,
)
from components.core import basic_validation, calculate_available_spaces
from components.google import google_login, get_google_redirect_url
from components.validation import valid_integer, valid_string
from components.student import student_chosen_activity
from components.db import sql_query, dict_sql_query
from components.limiter_obj import limiter


# blueprint init
student_routes = Blueprint("student_routes", __name__, template_folder="../templates")


# index
@student_routes.route("/")
@booking_blocked
@login_required
@user_setup_completed
def index():
    """
    Student index

    * list available activities (GET)
        - along with information about them (also how many spaces available)
    """

    chosen_activity = student_chosen_activity()

    activities = []
    for activity in dict_sql_query("SELECT * FROM activities"):
        activities.append(
            {
                "activity": activity,
                "available_spaces": calculate_available_spaces(activity["id"]),
            }
        )

    return render_template(
        "student/index.html",
        fullname=session.get("fullname"),
        school_class=session.get("school_class"),
        activities=activities,
        chosen_activity=chosen_activity,
    )


# login
@student_routes.route("/login")
@limiter.limit("800 per hour")
def students_login():
    google_signin_url = get_google_redirect_url("/callback")

    return render_template("student/login.html", google_signin_url=google_signin_url)


@student_routes.route("/callback")
@limiter.limit("200 per hour")
@booking_blocked
def students_callback():
    # Get authorization code Google sent back
    code = request.args.get("code")

    # If no code was sent
    if not code:
        abort(400, "missing oauth token")

    # verify using separate module
    oauth_user = google_login(code, "/callback")

    existing_student = dict_sql_query(
        "SELECT * FROM students WHERE email = %s",
        fetchone=True,
        params=(oauth_user["email"],),
    )

    # check if email exists in students
    if not existing_student:
        # create new object
        sql_query(
            "INSERT INTO students (email, last_name, first_name) VALUES (%s, %s, %s)",
            params=(
                oauth_user["email"],
                oauth_user["family_name"],
                oauth_user["given_name"],
            ),
        )
        existing_student = dict_sql_query(
            "SELECT * FROM students WHERE email = %s",
            fetchone=True,
            params=(oauth_user["email"],),
        )

    school_class = None
    if existing_student["class_id"]:
        school_class = dict_sql_query(
            "SELECT class_name FROM school_classes WHERE id = %s",
            fetchone=True,
            params=(int(existing_student["class_id"]),),
        )["class_name"]

    session["fullname"] = f"{oauth_user['given_name']} {oauth_user['family_name']}"
    session["logged_in"] = True
    session["picture_url"] = oauth_user["picture"]
    session["id"] = existing_student["id"]
    session["school_class"] = school_class

    return redirect("/")


@student_routes.route("/callback/error", methods=["POST"])
def callback_error():
    return render_template(
        "callback_error.html", message=request.form.get("message"), redirect_basepath=""
    )


# logout
@student_routes.route("/logout")
@login_required
def logout():
    """
    Student logout

    * destory user session (GET)
    """

    session.pop("logged_in", False)
    session.pop("id", None)
    session.pop("school_class", None)

    return redirect("/login")


# setup
@student_routes.route("/setup", methods=["POST", "GET"])
@limiter.limit("500 per hour")
@booking_blocked
@login_required
@user_not_setup
def setup():
    """
    Student setup

    * only show page if student has not yet configured it's user (GET)
    * add first_name, last_name and school_class to student object (POST)
    """

    template = "student/setup.html"

    if request.method == "GET":
        return render_template(template)
    elif request.method == "POST":
        expected_values = ["join_code"]

        if not basic_validation(expected_values):
            return render_template(template, fail="Saknar/felaktig data.")

        join_code = request.form["join_code"]

        if len(join_code) != 8:
            return render_template(template, fail="Fel längd på kod."), 40

        # make sure to validate input variables against string authentication
        if not valid_string(
            join_code,
            allow_newline=False,
            allow_punctuation=False,
            allow_space=False,
        ):
            return (
                render_template(
                    template,
                    fail="Icke tillåtna karaktärer.",
                ),
                400,
            )

        # verify code
        school_class = dict_sql_query(
            "SELECT * FROM school_classes WHERE password = %s",
            fetchone=True,
            params=(join_code,),
        )

        if not school_class:
            return (
                render_template(
                    template,
                    fail="Felaktig kod.",
                ),
                400,
            )

        # passed validation, update user variables
        sql_query(
            f"UPDATE students SET class_id={school_class['id']}  WHERE id={session['id']}"
        )

        # set school_class
        session["school_class"] = school_class["class_name"]

        # redirect to index
        return redirect("/")


# selected activity
@student_routes.route("/activity/<id>", methods=["POST", "GET"])
@limiter.limit("500 per hour")
@booking_blocked
@login_required
@user_setup_completed
def selected_activity(id):
    """
    Selected activity

    * show activity information (GET)
    * book student to activity, if available spaces are still left (POST)
    """

    if not valid_integer(id):
        return (
            render_template(
                "errors/custom.html", title="400", message="ID is not integer."
            ),
            400,
        )

    activity = dict_sql_query(
        "SELECT * FROM activities WHERE id = %s", fetchone=True, params=(id,)
    )

    if not activity:
        return (
            render_template(
                "errors/custom.html", title="400", message="Activity dose not exist."
            ),
            400,
        )

    # check if activity has questions
    query = dict_sql_query(
        "SELECT * FROM questions WHERE activity_id = %s", params=(id,)
    )
    questions = []

    if query:
        # loops query to add each options for questions into list
        for question in query:
            questions.append(
                {
                    "info": question,
                    "options": dict_sql_query(
                        "SELECT * FROM options WHERE question_id = %s",
                        params=(question["id"],),
                    ),
                }
            )

    if request.method == "GET":
        return render_template(
            "student/activity.html",
            activity=activity,
            fullname=session.get("fullname"),
            school_class=session.get("school_class"),
            questions=questions,
            available_spaces=calculate_available_spaces(id),
        )

    if request.method == "POST":
        for k, v in request.form.items():
            if not valid_integer(k):
                return (
                    render_template(
                        "student/activity.html",
                        activity=activity,
                        fullname=session.get("fullname"),
                        school_class=session.get("school_class"),
                        questions=questions,
                        available_spaces=calculate_available_spaces(id),
                        fail="Felaktigt skickad data.",
                    ),
                    400,
                )

            question = dict_sql_query(
                "SELECT * FROM questions WHERE id = %s", fetchone=True, params=(k,)
            )

            if not question:
                return (
                    render_template(
                        "student/activity.html",
                        activity=activity,
                        fullname=session.get("fullname"),
                        school_class=session.get("school_class"),
                        questions=questions,
                        available_spaces=calculate_available_spaces(id),
                        fail="Fråga existerar inte.",
                    ),
                    400,
                )

            if not v and bool(question["obligatory"]):
                return (
                    render_template(
                        "student/activity.html",
                        activity=activity,
                        fullname=session.get("fullname"),
                        school_class=session.get("school_class"),
                        questions=questions,
                        available_spaces=calculate_available_spaces(id),
                        fail="Saknar data.",
                    ),
                    400,
                )

            if not valid_string(
                k,
                max_length=50,
                ignore_undefined=True,
                allow_newline=False,
                allow_punctuation=False,
                allow_space=False,
                swedish=False,
            ) or not valid_string(
                v, max_length=50, ignore_undefined=True, allow_newline=False
            ):
                return (
                    render_template(
                        "student/activity.html",
                        activity=activity,
                        fullname=session.get("fullname"),
                        school_class=session.get("school_class"),
                        questions=questions,
                        available_spaces=calculate_available_spaces(id),
                        fail="Innehåller ogiltiga tecken/för långa svar.",
                    ),
                    400,
                )

        if len(request.form) < len(
            dict_sql_query(
                "SELECT * FROM questions WHERE activity_id = %s", params=(id,)
            )
        ):
            return (
                render_template(
                    "student/activity.html",
                    activity=activity,
                    fullname=session.get("fullname"),
                    school_class=session.get("school_class"),
                    questions=questions,
                    available_spaces=calculate_available_spaces(id),
                    fail="Saknar svar på frågor.",
                ),
                400,
            )

        # check if it still has available_spaces
        if calculate_available_spaces(id) < 1:
            return (
                render_template(
                    "student/activity.html",
                    activity=activity,
                    fullname=session.get("fullname"),
                    school_class=session.get("school_class"),
                    questions=questions,
                    available_spaces=calculate_available_spaces(id),
                    fail="Denna aktivitet har inga lediga platser.",
                ),
                400,
            )

        # delete any previous answers this user has submitted
        sql_query(
            "DELETE FROM answers WHERE student_id = %s", params=(session.get("id"),)
        )

        # validation completed
        for question_id, answer in request.form.items():
            # check if question is of type written or not
            question = sql_query(
                "SELECT * FROM questions WHERE id = %s", params=(question_id,)
            )[0]

            if question[3]:
                # written answers
                sql_query(
                    "INSERT INTO answers (student_id, question_id, written_answer) VALUES (%s, %s, %s)",
                    params=(session.get("id"), question_id, str(answer)),
                )
            else:
                # option
                sql_query(
                    "INSERT INTO answers (student_id, question_id, option_id) VALUES (%s, %s, %s)",
                    params=(session.get("id"), question_id, answer),
                )

        # set chosen_activity
        sql_query(
            "UPDATE students SET chosen_activity = %s, attendance = 0 WHERE id = %s",
            params=(int(id), session.get("id")),
        )

        return redirect("/confirmation")


# confirmation
@student_routes.route("/confirmation")
@limiter.limit("500 per hour")
@booking_blocked
@login_required
@user_setup_completed
def confirmation():
    """
    Confirmation page

    * confirm the students new booking (GET)
    """

    chosen_activity = student_chosen_activity()
    answers = dict_sql_query(
        "SELECT * FROM answers WHERE student_id = %s",
        params=(session.get("id"),),
    )

    if chosen_activity:
        questions = []
        for q in dict_sql_query(
            "SELECT * FROM questions WHERE activity_id = %s",
            params=(chosen_activity["id"],),
        ):
            questions.append(
                {
                    "object": q,
                    "options": dict_sql_query(
                        "SELECT * FROM options WHERE question_id = %s",
                        params=(q["id"],),
                    ),
                }
            )

    return (
        render_template(
            "student/confirmation.html",
            fullname=session.get("fullname"),
            school_class=session.get("school_class"),
            chosen_activity=chosen_activity,
            answers=answers,
            questions=questions,
        )
        if chosen_activity
        else render_template(
            "errors/custom.html",
            title="400",
            message="Student has not chosen an activity.",
        ),
        400,
    )
