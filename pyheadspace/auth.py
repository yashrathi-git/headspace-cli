import json
import re

import requests
from rich.console import Console

LOGIN_URL = "https://www.headspace.com/login"
AUTH_URL = "https://auth.headspace.com/co/authenticate"
BEARER_TOKEN_URL = "https://auth.headspace.com/authorize"

session = requests.Session()
console = Console()

headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:88.0) Gecko/20100101 Firefox/88.0",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.5",
    "Content-Type": "application/json",
    "Origin": "https://www.headspace.com",
    "Connection": "keep-alive",
    "TE": "Trailers",
}

session.headers.update(headers)


def get_client_id():
    response = session.get(LOGIN_URL)
    client_id = re.findall(r'"clientId":"(.+?)",', response.text)[0]
    return client_id


def prompt():
    email = console.input(f"[bold red]?[/] Email: ")
    password = console.input(f"[bold red]?[/] Password: ", password=True)

    return email, password


def get_bearer_token(client_id, login_ticket):
    params = {
        "client_id": client_id,
        "response_type": "token",
        "response_mode": "web_message",
        "redirect_uri": "https://www.headspace.com/auth",
        "scope": "openid email",
        "audience": "https://api.prod.headspace.com",
        "realm": "User-Password-Headspace",
        "login_ticket": login_ticket,
        "prompt": "none",
    }
    response = session.get(BEARER_TOKEN_URL, params=params)
    html = response.text
    bearer_token = re.findall(r'"access_token":"(.+?)"', html)[0]
    return bearer_token


def authenticate(email, password):
    data = {
        "client_id": get_client_id(),
        "username": email,
        "password": password,
        "realm": "User-Password-Headspace",
        "credential_type": "http://auth0.com/oauth/grant-type/password-realm",
    }
    response = session.post(
        AUTH_URL,
        headers=headers,
        data=json.dumps(data),
    )
    resp_json: dict = response.json()
    try:
        login_ticket = resp_json["login_ticket"]
    except KeyError:
        if "error" in resp_json.keys():
            console.print(resp_json["error"], style="red")
            if "error_description" in resp_json.keys():
                console.print(resp_json["error_description"])
        else:
            console.print(resp_json)
        return False
    bearer_token = get_bearer_token(data["client_id"], login_ticket)
    bearer_token = "bearer " + bearer_token
    return bearer_token
