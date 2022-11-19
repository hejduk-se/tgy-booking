# tullinge/booking
# https://github.com/tullinge/booking

# imports
from flask import jsonify, abort, request
from json import dumps

from google.oauth2 import id_token
from google.auth.transport import requests
from oauthlib.oauth2 import WebApplicationClient

import requests as requests_module

from os import environ

GOOGLE_CLIENT_ID = environ.get("GOOGLE_CLIENT_ID", default=False)
GOOGLE_CLIENT_SECRET = environ.get("GOOGLE_CLIENT_SECRET", default=False)
APP_URL = environ.get("APP_URL", default="http://localhost:5000")
GSUITE_DOMAIN_NAME = environ.get("GSUITE_DOMAIN_NAME", default=False)
MENTOR_GSUITE_DOMAIN_NAME = environ.get("MENTOR_GSUITE_DOMAIN_NAME", default=False)
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

# oauth2 client setup
client = WebApplicationClient(GOOGLE_CLIENT_ID)


def get_google_provider_cfg():
    return requests_module.get(GOOGLE_DISCOVERY_URL).json()


def get_google_redirect_url(callback_url: str):
    # Find out what URL to hit for Google login
    google_provider_cfg = get_google_provider_cfg()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    # Use library to construct the request for Google login and provide
    # scopes that let you retrieve user's profile from Google

    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=APP_URL + callback_url,
        scope=["openid", "email", "profile"],
    )

    return request_uri


def google_login(code: str, callback_url: str):
    print("hello!")

    # If no code was sent
    if not code:
        abort(400, "Missing OAuth token")

    # Find out what URL to hit to get tokens that allow you to ask for
    # things on behalf of a user
    google_provider_cfg = get_google_provider_cfg()
    token_endpoint = google_provider_cfg["token_endpoint"]

    # Prepare and send a request to get tokens
    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url,
        redirect_url=APP_URL + callback_url,
        code=code,
    )
    token_response = requests_module.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )

    # Parse the tokens
    client.parse_request_body_response(dumps(token_response.json()))

    # Now that you have tokens let's find and hit the URL
    # from Google that gives you the user's profile information,
    # including their Google profile image and email
    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests_module.get(uri, headers=headers, data=body)

    # You want to make sure their email is verified.
    # The user authenticated with Google, authorized your
    # app, and now you've verified their email through Google!
    if userinfo_response.json().get("email_verified"):
        if "hd" not in userinfo_response.json():
            abort(400, "Email is not hosted domain. Please use your school email.")

        if userinfo_response.json()["hd"] != GSUITE_DOMAIN_NAME:
            abort(
                400,
                f"This system requires that you login with your {GSUITE_DOMAIN_NAME}, but you logged in with {userinfo_response.json()['hd']}.",
            )

        return userinfo_response.json()

    abort(400, "User email not available or not verified by Google")
