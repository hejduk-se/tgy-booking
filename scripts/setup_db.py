# tullinge/booking
# https://github.com/tullinge/booking

import sys
from pathlib import Path

# Add parent folder
sys.path.append(str(Path(__file__).parent.parent.absolute()))

from components.db import sql_query


def insert(query, name=None):
    try:
        sql_query(query)
    except Exception:
        print(f"unable to create {name}, already exists?")


# create tables
def create_tabels():
    # activities
    insert(
        """
        CREATE TABLE activities (
            id INT NOT NULL AUTO_INCREMENT,
            name VARCHAR(50) DEFAULT NULL,
            spaces INT DEFAULT NULL,
            info VARCHAR(511) DEFAULT NULL,
            PRIMARY KEY (id)
        );
    """,
        name="activities",
    )

    # questions
    insert(
        """
        CREATE TABLE questions (
            id INT NOT NULL AUTO_INCREMENT,
            activity_id INT NOT NULL,
            question VARCHAR(255) NOT NULL,
            written_answer BOOLEAN DEFAULT FALSE,
            obligatory BOOLEAN DEFAULT TRUE,
            PRIMARY KEY (id)
        );
    """,
        name="questions",
    )

    # options on questions
    insert(
        """
        CREATE TABLE options (
            id INT NOT NULL AUTO_INCREMENT,
            question_id INT NOT NULL,
            text VARCHAR(255) NOT NULL,
            PRIMARY KEY (id)
        );
    """,
        name="options",
    )

    # answers from students
    insert(
        """
        CREATE TABLE answers (
            id INT NOT NULL AUTO_INCREMENT,
            student_id INT NOT NULL,
            question_id INT NOT NULL,
            option_id INT DEFAULT NULL,
            written_answer VARCHAR(255) DEFAULT NULL,
            PRIMARY KEY (id)
        );
    """,
        name="answers",
    )

    # admins
    # password should always be stored in hashed format
    insert(
        """
        CREATE TABLE admins (
            id INT NOT NULL AUTO_INCREMENT,
            name VARCHAR(50) DEFAULT NULL,
            username VARCHAR(255) DEFAULT NULL,
            password VARCHAR(255) DEFAULT NULL,
            PRIMARY KEY (id)
        );
    """,
        name="admins",
    )

    # students
    # password is stored in plain text
    insert(
        """
        CREATE TABLE students (
            id INT NOT NULL AUTO_INCREMENT,
            email VARCHAR(255) NOT NULL UNIQUE,
            last_name VARCHAR(50) DEFAULT NULL,
            first_name VARCHAR(50) DEFAULT NULL,
            class_id INT DEFAULT NULL,
            chosen_activity INT DEFAULT NULL,
            PRIMARY KEY (id)
        );
    """,
        name="students",
    )

    # school_classes
    insert(
        """
        CREATE TABLE school_classes (
            id INT NOT NULL AUTO_INCREMENT,
            class_name VARCHAR(10) NOT NULL UNIQUE,
            password VARCHAR(8) NOT NULL UNIQUE,
            PRIMARY KEY (id)
        );
    """,
        name="school_classes",
    )

    # leaders
    insert(
        """
        CREATE TABLE leaders (
            id INT NOT NULL AUTO_INCREMENT,
            email VARCHAR(255) NOT NULL,
            activity_id INT DEFAULT NULL,
            PRIMARY KEY(id)
        )
    """,
        name="mentors",
    )


if __name__ == "__main__":
    create_tabels()
