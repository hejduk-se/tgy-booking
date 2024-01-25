# tullinge/booking
# https://github.com/tullinge/booking

from flask import Blueprint, render_template, jsonify, request, session, redirect, abort

from components.db import dict_sql_query, sql_query
from components.google import google_login, get_google_redirect_url
from components.decorators import activity_leader_login_required
from components.validation import valid_integer

# blueprint init
activity_leader_routes = Blueprint(
    "activity_leader_routes", __name__, template_folder="../templates"
)

BASEPATH = "/leader"


@activity_leader_routes.route("/")
@activity_leader_login_required
def index():
    # fetch activities leader has access to
    query = dict_sql_query(
        "SELECT activity_id FROM leaders WHERE email = %s",
        params=(session.get("leader_email"),),
    )

    activities = []
    for obj in query:
        students = []

        # get questions
        questions = dict_sql_query(
            "SELECT * FROM questions WHERE activity_id = %s",
            params=(obj["activity_id"],),
        )

        # students that selected this activity
        for student in dict_sql_query(
            "SELECT * FROM students WHERE chosen_activity = %s",
            params=(obj["activity_id"],),
        ):
            # build answers
            answers = []
            for question in questions:
                answer = dict_sql_query(
                    "SELECT * FROM answers WHERE question_id = %s AND student_id = %s",
                    fetchone=True,
                    params=(question["id"], student["id"]),
                )

                if not answer:
                    answers.append()
                else:
                    if not question["written_answer"]:
                        answers.append(
                            dict_sql_query(
                                "SELECT text FROM options WHERE id = %s",
                                fetchone=True,
                                params=(answer["option_id"],),
                            )["text"]
                        )
                    else:
                        answers.append(answer["written_answer"])

            students.append(
                {
                    "student": student,
                    "class_name": dict_sql_query(
                        "SELECT class_name FROM school_classes WHERE id = %s",
                        fetchone=True,
                        params=(student["class_id"],),
                    )["class_name"],
                    "answers": answers,
                }
            )

        # add to list
        activities.append(
            {
                "name": dict_sql_query(
                    "SELECT name FROM activities WHERE id = %s",
                    fetchone=True,
                    params=(obj["activity_id"],),
                )["name"],
                "students": students,
                "questions": questions,
            }
        )

    return render_template("leader/index.html", activities=activities)


# toggle attendance
@activity_leader_routes.route("/attendance/<id>/<new_state>")
@activity_leader_login_required
def toggle_attendance(id, new_state):
    """
    Toggle attendance for student
    """

    if not valid_integer(id):
        return (
            render_template(
                "errors/custom.html", title="400", message="Id must be integer."
            ),
            400,
        )

    if not valid_integer(new_state):
        return (
            render_template(
                "errors/custom.html", title="400", message="New state must be integer."
            ),
            400,
        )

    if int(new_state) not in [0, 1, 2]:
        return (
            render_template(
                "errors/custom.html",
                title="400",
                message="New state must be 0, 1 or 2.",
            ),
            400,
        )

    student = dict_sql_query(
        "SELECT attendance, chosen_activity FROM students WHERE id = %s",
        params=(id,),
    )

    if not student:
        return (
            render_template(
                "errors/custom.html", title="400", message="Student does not exist."
            ),
            400,
        )

    # fetch activities leader has access to
    query = dict_sql_query(
        "SELECT activity_id FROM leaders WHERE email = %s",
        params=(session.get("leader_email"),),
    )

    leader_has_access_to_activity = False
    for obj in query:
        if obj["activity_id"] == student[0]["chosen_activity"]:
            leader_has_access_to_activity = True
            break

    if not leader_has_access_to_activity:
        return (
            render_template(
                "errors/custom.html",
                title="401",
                message="Leader does not have access to this activity.",
            ),
            401,
        )

    sql_query(
        "UPDATE students SET attendance = %s WHERE id = %s",
        params=(
            new_state,
            id,
        ),
    )

    return redirect(request.referrer)


@activity_leader_routes.route("/login")
def login():
    google_signin_url = get_google_redirect_url("/leader/callback")

    return render_template("leader/login.html", google_signin_url=google_signin_url)


@activity_leader_routes.route("/callback")
def students_callback():
    # Get authorization code Google sent back
    code = request.args.get("code")

    # verify using separate module
    oauth_user = google_login(code, "/leader/callback", ignore_wrong_hd=True)

    # perform some validation against database
    leader = dict_sql_query(
        "SELECT * FROM leaders WHERE email = %s",
        fetchone=True,
        params=(oauth_user["email"],),
    )

    if not leader:
        abort(401, "User is not leader.")

    session["leader_logged_in"] = True
    session["leader_id"] = leader["id"]
    session["leader_email"] = leader["email"]

    return redirect(BASEPATH)


@activity_leader_routes.route("/callback/error", methods=["POST"])
def callback_error():
    return render_template(
        "callback_error.html",
        message=request.form.get("message"),
        redirect_basepath="/leader",
    )


# logout
@activity_leader_routes.route("/logout")
@activity_leader_login_required
def logout():
    """
    Leader logout

    * destory user session (GET)
    """

    session.pop("leader_logged_in", False)
    session.pop("leader_id", None)
    session.pop("leader_email", None)

    return redirect(f"{BASEPATH}/login")
