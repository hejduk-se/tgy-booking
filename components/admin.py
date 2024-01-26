# tullinge/booking
# https://github.com/tullinge/booking

# imports
# components import
from components.db import sql_query, dict_sql_query
from components.core import calculate_available_spaces


def get_activites_with_spaces():
    query = sql_query("SELECT * FROM activities")

    activities = []
    for activity in query:
        activities.append((activity, calculate_available_spaces(activity[0])))

    return activities


def get_activity_questions_and_options(id):
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
                    "question": question,
                    "options": dict_sql_query(
                        "SELECT * FROM options WHERE question_id = %s",
                        params=(question["id"],),
                    ),
                }
            )

    return questions
