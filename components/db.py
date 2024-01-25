# tullinge/booking
# https://github.com/tullinge/booking

# imports
from os import environ
import pymysql


def create_conn():
    """
    Creates a connection from environment variables (or developer defaults if missing)
    """
    return pymysql.connect(
        host=environ.get("MYSQL_HOST", "localhost"),
        user=environ.get("MYSQL_USER", "admin"),
        password=environ.get("MYSQL_PASSWORD", "do-not-use-in-production"),
        db=environ.get("MYSQL_DATABASE", "booking"),
    )


def sql_query(query, params: tuple = ()):
    """
    Performs specified SQL query in database. Returns result from cursor.fetchall(), usually tuple
    If searching for a specific object, note that object will be wrapped in outside tuple
    """

    conn = create_conn()

    try:
        with conn.cursor() as cursor:
            if params != ():
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            result = cursor.fetchall()
        conn.commit()
    finally:
        conn.close()

    return result


def dict_sql_query(query, fetchone=False, params: tuple = ()):
    """
    Performs specified SQL query in database, return data as dict

    Try to use this one as much as possible when querying for data.
    """

    conn = create_conn()

    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            if params != ():
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            result = cursor.fetchone() if fetchone else cursor.fetchall()

        conn.commit()
    finally:
        conn.close()

    return result
