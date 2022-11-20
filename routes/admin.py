# tullinge/booking
# https://github.com/tullinge/booking

# imports
from flask import Blueprint, render_template, request, redirect, session, abort

# components import
from components.validation import valid_integer, valid_string
from components.db import sql_query, dict_sql_query
from components.decorators import admin_required
from components.codes import generate_code
from components.limiter_obj import limiter
from components.admin import (
    get_activites_with_spaces,
    get_activity_questions_and_options,
)
from components.google import get_google_redirect_url, google_login
from components.core import (
    hash_password,
    verify_password,
    calculate_available_spaces,
    basic_validation,
)

# blueprint init
admin_routes = Blueprint("admin_routes", __name__, template_folder="../templates")

BASEPATH = "/admin"


# admin login
@admin_routes.route("/login")
@limiter.limit("100 per hour")
def login():
    """
    Admin authentication

    * display login form (GET)
    """

    google_signin_url = get_google_redirect_url("/admin/callback")

    return render_template("admin/login.html", google_signin_url=google_signin_url)


@admin_routes.route("/callback")
def admin_callback():
    # Get authorization code Google sent back
    code = request.args.get("code")

    # verify using separate module
    oauth_user = google_login(code, "/admin/callback", ignore_wrong_hd=True)

    # perform some validation against database
    admin = dict_sql_query(
        f"SELECT * FROM admins WHERE email='{oauth_user['email']}'", fetchone=True
    )

    if not admin:
        abort(401, "User is not admin.")

    session["admin_logged_in"] = True
    session["admin_id"] = admin["id"]

    return redirect(BASEPATH)


# admin logout, pop session
@admin_routes.route("/logout")
@admin_required
def logout():
    """
    Destroy admin session and set admin_id as invalid
    """
    session.pop("admin_logged_in", False)
    session.pop("admin_id", None)

    return redirect(f"{BASEPATH}/login")


# index
@admin_routes.route("/", methods=["POST", "GET"])
@admin_required
def index():
    """
    Admin index
    """
    template = "admin/index.html"

    amount_activities = len(sql_query("SELECT * FROM activities"))
    amount_students_chosen_activity = len(
        sql_query("SELECT * FROM students WHERE chosen_activity IS NOT NULL")
    )

    if request.method == "GET":
        return render_template(
            template,
            amount_activities=amount_activities,
            amount_students_chosen_activity=amount_students_chosen_activity,
        )

    if request.method == "POST":
        if not request.form.get("booking_locked"):
            return (
                render_template(
                    template,
                    amount_activities=amount_activities,
                    amount_students_chosen_activity=amount_students_chosen_activity,
                    fail="Ogiltig data.",
                ),
                400,
            )

        if (
            request.form["booking_locked"] != "0"
            and request.form["booking_locked"] != "1"
        ):
            return (
                render_template(
                    template,
                    amount_activities=amount_activities,
                    amount_students_chosen_activity=amount_students_chosen_activity,
                    fail="Felaktig data på variabel.",
                ),
                400,
            )

        # set
        sql_query(
            f"UPDATE settings SET value='{request.form['booking_locked']}' WHERE identifier='booking_locked'"
        )

        return render_template(
            template,
            amount_activities=amount_activities,
            amount_students_chosen_activity=amount_students_chosen_activity,
            success="Uppdaterat status.",
        )


# activities
@admin_routes.route("/activities", methods=["POST", "GET"])
@admin_required
def activities():
    """
    Activities management

    * list available activities (GET)
    * create new activities (POST)
    """

    template = "admin/activities.html"
    activities = get_activites_with_spaces()

    if request.method == "GET":
        return render_template("admin/activities.html", activities=activities)

    if request.method == "POST":
        data = request.form

        # creating activity
        if request.form.get("request_type") == "add":
            expected_values = ["name", "spaces", "info", "request_type"]

            if not basic_validation(expected_values):
                return (
                    render_template(
                        template, activities=activities, fail="Felaktig data."
                    ),
                    400,
                )

            # validate
            if not valid_integer(data["spaces"]):
                return (
                    render_template(
                        template,
                        activities=activities,
                        fail="Antalet platser måste vara ett heltal.",
                    ),
                    400,
                )

            if not valid_string(
                data["name"], max_length=50, allow_newline=False
            ) or not valid_string(
                data["info"],
                max_length=511,
            ):
                return (
                    render_template(
                        template,
                        activities=activities,
                        fail="Data innehåller otillåtna tecken.",
                    ),
                    400,
                )

            # create
            sql_query(
                f"INSERT INTO activities (name, spaces, info) VALUES ('{data['name']}', {data['spaces']}, '{data['info']}')"
            )

            # re-fetch
            activities = get_activites_with_spaces()

            # success
            return render_template(
                template,
                activities=activities,
                success="Aktivitet skapad. Tryck på aktiviteten för att skapa frågor för aktiviteten.",
            )

        if request.form.get("request_type") == "delete":
            expected_values = ["id", "request_type"]

            # validate
            if not basic_validation(expected_values):
                return (
                    render_template(
                        template, activities=activities, fail="Felaktig data."
                    ),
                    400,
                )

            if not valid_integer(data["id"]):
                return (
                    render_template(
                        template, activities=activities, fail="Id has to be integer."
                    ),
                    400,
                )

            # delete activity
            sql_query(f"DELETE FROM activities WHERE id={data['id']}")

            # set chosen_activity to null on students that have booked this one
            sql_query(
                f"UPDATE students SET chosen_activity=NULL WHERE chosen_activity={data['id']}"
            )

            # delete activity leaders
            sql_query(f"DELETE FROM leaders WHERE activity_id={data['id']}")

            # re-fetch
            activities = get_activites_with_spaces()

            # success
            return (
                render_template(
                    template,
                    activities=activities,
                    success="Aktivitet borttagen. Alla elever som hade bokat denna aktivitet har fått den avbokad.",
                ),
                400,
            )

        return (
            render_template(template, activities=activities, fail="Ogiltig begäran."),
            400,
        )


# selected activity
@admin_routes.route("/activity/<id>", methods=["POST", "GET"])
@admin_required
def selected_activity(id):
    """
    Manage specific activity

    * display activity information (GET)
    * display questions attatched to this activity (GET)
    * create new questions for this activity (POST)
    * delete questions for this activity (POST)
    """

    template = "admin/activity.html"

    if not valid_integer(id):
        return (
            render_template(
                "errors/custom.html", title="400", message="ID is not integer."
            ),
            400,
        )

    activity = sql_query(f"SELECT * FROM activities WHERE id={id}")

    if not activity:
        return (
            render_template(
                "errors/custom.html", title="400", message="Activity dose not exist."
            ),
            400,
        )

    # get questions
    questions = get_activity_questions_and_options(id)

    if request.method == "GET":
        return render_template(
            template,
            activity=activity[0],
            questions=questions,
            available_spaces=calculate_available_spaces(id),
        )

    elif request.method == "POST":
        data = request.form

        if request.form.get("request_type") == "add":
            if not request.form.get("question"):
                return (
                    render_template(
                        template,
                        activity=activity[0],
                        questions=questions,
                        available_spaces=calculate_available_spaces(id),
                        fail="Ingen data skickades/saknar data.",
                    ),
                    400,
                )

            # check
            if not valid_string(data["question"], max_length=255, allow_newline=False):
                return (
                    render_template(
                        template,
                        activity=activity[0],
                        questions=questions,
                        available_spaces=calculate_available_spaces(id),
                        fail="Ogiltiga tecken eller fel längd på fråga (1-255).",
                    ),
                    400,
                )

            # is written answer
            if request.form.get("written_answer"):
                obligatory = True
                if request.form.get("voluntary"):
                    obligatory = False

                sql_query(
                    f"INSERT INTO questions (activity_id, question, written_answer, obligatory) VALUES ({id}, '{data['question']}', 1, {obligatory})"
                )

                # re-fetch
                questions = get_activity_questions_and_options(id)

                return render_template(
                    template,
                    activity=activity[0],
                    questions=questions,
                    available_spaces=calculate_available_spaces(id),
                    success="Fråga skapad.",
                )

            # admin is creating question with options
            sql_query(
                f"INSERT INTO questions (activity_id, question, written_answer) VALUES ({id}, '{data['question']}', 0)"
            )

            # re-fetch
            questions = get_activity_questions_and_options(id)

            return render_template(
                template,
                activity=activity[0],
                questions=questions,
                available_spaces=calculate_available_spaces(id),
                success="Fråga skapad. Tryck på frågan nedan för att lägga till svarsalternativ.",
            )

        if request.form.get("request_type") == "delete":
            # form validation
            if not basic_validation(["request_type", "id"]):
                return (
                    render_template(
                        activity=activity[0],
                        questions=questions,
                        available_spaces=calculate_available_spaces(id),
                        fail="Saknar data.",
                    ),
                    400,
                )

            if not valid_integer(data["id"]):
                return (
                    render_template(
                        activity=activity[0],
                        questions=questions,
                        available_spaces=calculate_available_spaces(id),
                        fail="Id must be integer.",
                    ),
                    400,
                )

            # delete
            sql_query(f"DELETE FROM questions WHERE id={data['id']}")

            # delete options
            sql_query(f"DELETE FROM options WHERE question_id={data['id']}")

            # delete students answers
            sql_query(f"DELETE FROM answers WHERE question_id={data['id']}")

            # re-fetch
            questions = get_activity_questions_and_options(id)

            return render_template(
                template,
                activity=activity[0],
                questions=questions,
                available_spaces=calculate_available_spaces(id),
                success="Frågan borttagen.",
            )

        # bad request
        return (
            render_template(
                activity=activity[0],
                questions=questions,
                available_spaces=calculate_available_spaces(id),
                fail="Ogiltig begäran.",
            ),
            400,
        )


@admin_routes.route("/activity/<id>/edit", methods=["POST", "GET"])
@admin_required
def edit_activity(id):
    """
    Edit activity

    * display activity information (GET)
    * edit activity information (POST)
    """

    template = "admin/activity_edit.html"

    if not valid_integer(id):
        return (
            render_template(
                "errors/custom.html", title="400", message="Id must be integer."
            ),
            400,
        )

    activity = sql_query(f"SELECT * FROM activities WHERE id={id}")

    if not activity:
        return (
            render_template(
                "errors/custom.html", title="400", message="Activity doesn't exist."
            ),
            400,
        )

    if request.method == "GET":
        return render_template(template, activity=activity[0])

    if request.method == "POST":
        if not basic_validation(["name", "spaces", "info"]):
            return (
                render_template(template, activity=activity[0], fail="Saknar data."),
                400,
            )

        if not valid_integer(request.form["spaces"]):
            return (
                render_template(
                    template,
                    activity=activity[0],
                    fail="Antalet platser måste vara ett heltal.",
                ),
                400,
            )

        if not valid_string(
            request.form["name"],
            max_length=50,
            allow_newline=False,
        ) or not valid_string(
            request.form["info"],
            max_length=511,
        ):
            return (
                render_template(
                    template,
                    activity=activity[0],
                    fail="Data innehåller otillåtna tecken.",
                ),
                400,
            )

        # update
        sql_query(
            f"UPDATE activities SET name = '{request.form['name']}', spaces = {request.form['spaces']}, info = '{request.form['info']}' WHERE id={id}"
        )

        # re-fetch
        activity = sql_query(f"SELECT * FROM activities WHERE id={id}")

        return render_template(
            template, activity=activity[0], success="Aktiviteten uppdaterad."
        )


# view question
@admin_routes.route("/question/<id>", methods=["POST", "GET"])
@admin_required
def question_id(id):
    """
    Manage question options, requires specific question id
    question must not be of type written_answer

    * list existing options for this question (GET)
    * create new options for this question (POST)
    """

    template = "admin/view_question.html"

    if not valid_integer(id):
        return (
            render_template(
                "errors/custom.html", title="400", message="Id must be integer."
            ),
            400,
        )

    question = sql_query(f"SELECT * FROM questions WHERE id={id}")

    if not question:
        return (
            render_template(
                "errors/custom.html", title="400", message="Question does not exist."
            ),
            400,
        )

    if question[0][3]:
        return (
            render_template(
                "errors/custom.html",
                title="400",
                message="Question is not correct type.",
            ),
            400,
        )

    # get options
    options = sql_query(f"SELECT * FROM options WHERE question_id={question[0][0]}")

    if request.method == "GET":
        return render_template(template, question=question[0], options=options)

    if request.method == "POST":
        data = request.form

        if not request.form.get("text"):
            return (
                render_template(
                    template, question=question[0], options=options, fail="Saknar data."
                ),
                400,
            )

        if not valid_string(
            data["text"],
            max_length=255,
            allow_newline=False,
        ):
            return (
                render_template(
                    template,
                    question=question[0],
                    options=options,
                    fail="Ogiltiga tecken skickade.",
                ),
                400,
            )

        # add option
        sql_query(
            f"INSERT INTO options (question_id, text) VALUES ({id}, '{data['text']}')"
        )

        # re-fetch
        options = sql_query(f"SELECT * FROM options WHERE question_id={question[0][0]}")

        return render_template(
            template,
            question=question[0],
            options=options,
            success="Alternativ skapat.",
        )


# booked students to specific activity
@admin_routes.route("/activity/<id>/students")
@admin_required
def activity_students(id):
    """
    Students booked to activity

    * display all students booked to this activity (GET)
        - along with any answers to questions available for this activity
    * (hopefully) printer friendly
    """

    if not valid_integer(id):
        return (
            render_template(
                "errors/custom.html", title="400", message="Id must be integer."
            ),
            400,
        )

    activity = sql_query(f"SELECT * FROM activities WHERE id={id}")

    if not activity:
        return (
            render_template(
                "errors/custom.html", title="400", message="Activity dose not exist."
            ),
            400,
        )

    # get students that have booked this activity and their answers
    query = sql_query(
        f"SELECT id, last_name, first_name, class_id, attendance FROM students WHERE chosen_activity={id}"
    )

    students = []
    for student in query:
        answer_query = sql_query(
            f"SELECT option_id, written_answer FROM answers WHERE student_id={student[0]}"
        )

        answers = []
        for answer in answer_query:
            if answer[0] is not None:
                option_name = sql_query(
                    f"SELECT text FROM options WHERE id={answer[0]}"
                )[0][0]
                answers.append(option_name)
            else:
                answers.append(answer[1])

        try:
            class_name = sql_query(
                f"SELECT class_name FROM school_classes WHERE id={student[3]}"
            )[0][0]
        except Exception:
            class_name = "error"

        students.append((student, answers, class_name))

    questions = sql_query(f"SELECT question FROM questions WHERE activity_id={id}")

    return render_template(
        "admin/activity_students.html",
        students=students,
        activity=activity[0],
        questions=questions,
    )


# toggle attendance
@admin_routes.route("/attendance/<id>/<new_state>")
@admin_required
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

    student = sql_query(f"SELECT attendance FROM students WHERE id={id}")

    if not student:
        return (
            render_template(
                "errors/custom.html", title="400", message="Student does not exist."
            ),
            400,
        )

    sql_query(f"UPDATE students SET attendance={new_state} WHERE id={id}")

    return redirect(request.referrer)


# admin user management
@admin_routes.route("/users", methods=["GET", "POST"])
@admin_required
def admin_users():
    """
    Admin user management

    * list all existing admin users (GET)
    * delete existing admin users (POST)
    * create new admin users (POST)
    """

    template = "admin/users.html"
    query = "SELECT id, name, email FROM admins"
    admins = dict_sql_query(query)

    if request.method == "GET":
        return render_template(template, admins=admins)

    if request.method == "POST":
        data = request.form

        if not data:
            return (
                render_template(template, admins=admins, fail="Ogiltig begäran."),
                400,
            )

        # delete
        if data["request_type"] == "delete":
            if len(data) != 2 or not data["id"]:
                return (
                    render_template(template, admins=admins, fail="Saknar data."),
                    400,
                )

            if not valid_integer(data["id"]):
                return (
                    render_template(
                        template, admins=admins, fail="Id måste vara heltal."
                    ),
                    400,
                )

            # cannot delete self
            if int(data["id"]) == int(session.get("admin_id")):
                return (
                    render_template(
                        template,
                        admins=admins,
                        fail="Kan inte radera den egna användaren.",
                    ),
                    400,
                )

            # delete user
            sql_query(f"DELETE FROM admins WHERE id={data['id']}")

            # update admins
            admins = dict_sql_query(query)

            return render_template(
                template, admins=admins, success="Användare raderad."
            )

        if data["request_type"] == "add":
            if len(data) != 3:
                return (
                    render_template(template, admins=admins, fail="Saknar data."),
                    400,
                )

            if not valid_string(
                data["name"],
                min_length=4,
                max_length=255,
                allow_newline=False,
                allow_punctuation=False,
            ):
                return (
                    render_template(
                        template, admins=admins, fail="Namn innehåller ogiltiga tecken."
                    ),
                    400,
                )

            if sql_query(
                f"SELECT id FROM admins WHERE email='{data['email'].lower()}'"
            ):
                return (
                    render_template(
                        template,
                        admins=admins,
                        fail="En admin med detta email existerar redan.",
                    ),
                    400,
                )

            # create new user
            sql_query(
                f"INSERT INTO admins (name, email) VALUES ('{data['name']}', '{data['email'].lower()}')"
            )

            # re-fetch
            admins = dict_sql_query(query)

            return render_template(
                template, admins=admins, success="Nytt konto skapats."
            )

        return render_template(template, admins=admins, fail="Felaktig begäran."), 400


# student codes
@admin_routes.route("/students", methods=["GET"])
@admin_required
def students():
    """
    Student account management

    * list all students/codes (GET)
    """

    students = []
    if request.args.get("show"):
        for student in dict_sql_query("SELECT * FROM students"):
            students.append(
                {
                    "student": student,
                    "activity_name": dict_sql_query(
                        f"SELECT name FROM activities WHERE id={student['chosen_activity']}",
                        fetchone=True,
                    )["name"]
                    if student["chosen_activity"]
                    else "Ej valt",
                    "class_name": dict_sql_query(
                        f"SELECT class_name FROM school_classes WHERE id={student['class_id']}",
                        fetchone=True,
                    )["class_name"]
                    if student["class_id"]
                    else "Har ej gått med.",
                }
            )

    if request.method == "GET":
        return render_template("admin/students.html", students=students)


# school classes management
@admin_routes.route("/classes", methods=["POST", "GET"])
@admin_required
def school_classes():
    """
    School classes management

    * list available school_classes (GET)
    * create new school_classes (POST)
    * delete existing school_classes (POST)
    """

    template = "admin/school_classes.html"
    school_classes = dict_sql_query("SELECT * FROM school_classes")

    if request.method == "GET":
        return render_template(template, school_classes=school_classes)

    if request.method == "POST":
        data = request.form

        if not data or len(data) != 2:
            return (
                render_template(
                    template, school_classes=school_classes, fail="Ingen data angiven."
                ),
                400,
            )

        # if adding
        if data["request_type"] == "add":
            if not data["class_name"]:
                return (
                    render_template(
                        template,
                        school_classes=school_classes,
                        fail="Saknar variabler.",
                    ),
                    400,
                )

            class_check = sql_query(
                f"SELECT * FROM school_classes WHERE class_name = BINARY '{data['class_name'].upper()}'"
            )

            if class_check:
                return (
                    render_template(
                        template,
                        school_classes=school_classes,
                        fail="Denna klass finns redan.",
                    ),
                    400,
                )

            if not valid_string(
                data["class_name"],
                min_length=3,
                max_length=10,
            ):
                return (
                    render_template(
                        template,
                        school_classes=school_classes,
                        fail="För kort/långt klassnamn.",
                    ),
                    400,
                )

            if not valid_string(
                data["class_name"],
                min_length=3,
                max_length=10,
                allow_space=False,
                allow_newline=False,
                allow_punctuation=False,
            ):
                return (
                    render_template(
                        template,
                        school_classes=school_classes,
                        fail="Innehåller ogiltiga tecken.",
                    ),
                    400,
                )

            # create
            sql_query(
                f"INSERT INTO school_classes (class_name, password) VALUES ('{data['class_name'].upper()}', '{generate_code()}')"
            )

            # re-fetch
            school_classes = dict_sql_query("SELECT * FROM school_classes")

            return (
                render_template(
                    template, school_classes=school_classes, success="Ny klass skapad."
                ),
                201,
            )

        # if deleting
        if data["request_type"] == "delete":
            if not data["id"]:
                return (
                    render_template(
                        template,
                        school_classes=school_classes,
                        fail="Saknar variabler.",
                    ),
                    400,
                )

            if not valid_integer(data["id"]):
                return (
                    render_template(
                        template,
                        school_classes=school_classes,
                        fail="Id måste vara heltal.",
                    ),
                    400,
                )

            # delete
            sql_query(f"DELETE FROM school_classes WHERE id={data['id']}")

            # update students
            sql_query(f"UPDATE students SET class_id=NULL WHERE class_id={data['id']}")

            # re-fetch
            school_classes = dict_sql_query("SELECT * FROM school_classes")

            return render_template(
                template, school_classes=school_classes, success="Klass raderad."
            )

        # if invalid request_type
        return (
            render_template(
                template, school_classes=school_classes, fail="Ogiltig förfrågan."
            ),
            400,
        )


# show students per class
@admin_routes.route("/classes/<id>/students")
@admin_required
def student_classes(id):
    """
    Show students registrered to class

    * display list of all students (GET)
    """

    template = "admin/class_students.html"

    if not valid_integer(id):
        return (
            render_template(
                "errors/custom.html", title="400", message="Id must be integer"
            ),
            400,
        )

    school_class = dict_sql_query(
        f"SELECT * FROM school_classes WHERE id={id}", fetchone=True
    )

    if not school_class:
        return (
            render_template(
                "errors/custom.html", title="400", message="Class does not exist."
            ),
            400,
        )

    # show students with  class defined as this one
    students = []

    for student in dict_sql_query(
        f"SELECT * FROM students WHERE class_id={school_class['id']}"
    ):
        students.append(
            {
                "student": student,
                "activity_name": dict_sql_query(
                    f"SELECT name FROM activities WHERE id={student['chosen_activity']}",
                    fetchone=True,
                )["name"]
                if student["chosen_activity"]
                else "Ej valt",
            }
        )

    return render_template(template, school_class=school_class, students=students)


# admin leaders management
@admin_routes.route("/activity/<id>/leaders", methods=["POST", "GET"])
@admin_required
def admin_leaders(id):
    """
    Show leaders registrered to activity

    * display list of all activity leader (GET)
    * add/delete activity leader (POST)
    """

    template = "admin/activity_leaders.html"

    if not valid_integer(id):
        return (
            render_template(
                "errors/custom.html", title="400", message="Id must be integer"
            ),
            400,
        )

    activity = dict_sql_query(f"SELECT * FROM activities WHERE id={id}", fetchone=True)

    if not activity:
        return (
            render_template(
                "errors/custom.html", title="400", message="Activity does not exist."
            ),
            400,
        )

    leaders = dict_sql_query(f"SELECT * FROM leaders WHERE activity_id={id}")

    if request.method == "GET":
        return render_template(template, activity=activity, leaders=leaders)

    if request.method == "POST":
        if not request.form.get("request_type"):
            return (
                render_template(
                    template,
                    activity=activity,
                    leaders=leaders,
                    fail="Ogiltig begäran.",
                ),
                400,
            )

        if request.form["request_type"] == "add":
            if not basic_validation(["request_type", "email"]):
                return (
                    render_template(
                        template,
                        activity=activity,
                        leaders=leaders,
                        fail="Saknar data.",
                    ),
                    400,
                )

            if len(request.form["email"]) < 5 or len(request.form["email"]) > 255:
                return (
                    render_template(
                        template,
                        activity=activity,
                        leaders=leaders,
                        fail="För lång/för kort mailadress (5-255).",
                    ),
                    400,
                )

            if not "@" in request.form["email"] or not "." in request.form["email"]:
                return (
                    render_template(
                        template,
                        activity=activity,
                        leaders=leaders,
                        fail="Ser inte ut som en giltig mailadress.",
                    ),
                    400,
                )

            # create
            sql_query(
                f"INSERT INTO leaders (email, activity_id) VALUES ('{request.form['email'].lower()}', {activity['id']})"
            )

            # re-fetch
            leaders = dict_sql_query(f"SELECT * FROM leaders WHERE activity_id={id}")

            return render_template(
                template,
                activity=activity,
                leaders=leaders,
                success="Lagt till aktivitetsledare.",
            )

        if request.form["request_type"] == "delete":
            if not basic_validation(["request_type", "id"]):
                return (
                    render_template(
                        template,
                        activity=activity,
                        leaders=leaders,
                        fail="Saknar data.",
                    ),
                    400,
                )

            if not valid_integer(request.form["id"]):
                return (
                    render_template(
                        template,
                        activity=activity,
                        leaders=leaders,
                        fail="Id måste vara ett heltal.",
                    ),
                    400,
                )

            # delete
            sql_query(f"DELETE FROM leaders WHERE id={request.form['id']}")

            # re-fetch
            leaders = dict_sql_query(f"SELECT * FROM leaders WHERE activity_id={id}")

            return render_template(
                template,
                activity=activity,
                leaders=leaders,
                success="Aktivitetsledare borttagen.",
            )

        return (
            render_template(
                template,
                activity=activity,
                leaders=leaders,
                fail="Ogiltig begäran.",
            ),
            400,
        )


# change password
@admin_routes.route("/changepassword", methods=["POST", "GET"])
@admin_required
def change_password():
    """
    Change account password

    * display form (GET)
    * change password for logged in admin (POST)
    """
    template = "admin/changepassword.html"

    # view page
    if request.method == "GET":
        return render_template(template)

    # change
    if request.method == "POST":
        data = request.form

        admin = sql_query(
            f"SELECT password FROM admins WHERE id={session.get('admin_id')}"
        )

        if not admin:
            return render_template(template, fail="Admin does not exist."), 400

        if (
            len(data) != 3
            or not data["current_password"]
            or not data["new_password"]
            or not data["new_password_verify"]
        ):
            return render_template(template, fail="Felaktig begäran."), 400

        if not verify_password(admin[0][0], data["current_password"]):
            return (
                render_template(template, fail="Felaktigt angivet nuvarande lösenord."),
                400,
            )

        if data["new_password"] != data["new_password_verify"]:
            return (
                render_template(
                    template, fail="Nya lösenordet måste vara likadant i båda fälten."
                ),
                400,
            )

        if not valid_string(data["new_password"], min_length=8, max_length=100):
            return (
                render_template(
                    template,
                    fail="Lösenordet för kort eller för långt (8-100).",
                ),
                400,
            )

        # update user
        sql_query(
            f"UPDATE admins SET password = '{hash_password(data['new_password'])}' WHERE id = {session.get('admin_id')}"
        )

        # change password
        return render_template(template, success="Lösenord bytt.")
