import re
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from rich.console import Console

LOGIN_URL = "https://my.headspace.com/"
TOKEN_URL = "https://auth.headspace.com/oauth/token"

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
    response.raise_for_status()

    # Headspace's current login flow redirects through Auth0's /authorize
    # endpoint, where the client ID is a query parameter.
    for redirect in reversed([*response.history, response]):
        client_ids = parse_qs(urlparse(redirect.url).query).get("client_id")
        if client_ids:
            return client_ids[0]

    match = re.search(r"clientId\s*:\s*[`\"']([^`\"']+)", response.text)
    if match:
        return match.group(1)

    # The current app keeps its Auth0 settings in a generated config bundle.
    config_path = re.search(
        r'(?:src|href)=["\']([^"\']*configHelpers[^"\']*\.js)["\']',
        response.text,
    )
    if config_path:
        config_response = session.get(urljoin(response.url, config_path.group(1)))
        config_response.raise_for_status()
        match = re.search(
            r"clientId\s*:\s*[`\"']([^`\"']+)", config_response.text
        )
        if match:
            return match.group(1)

    raise RuntimeError("Headspace login did not provide an Auth0 client ID")


def prompt():
    email = console.input(f"[bold red]?[/] Email: ")
    password = console.input(f"[bold red]?[/] Password: ", password=True)

    return email, password


def authenticate(email, password):
    try:
        client_id = get_client_id()
    except (requests.RequestException, RuntimeError) as error:
        console.print(f"Unable to start Headspace login: {error}", style="red")
        return False

    data = {
        "grant_type": "http://auth0.com/oauth/grant-type/password-realm",
        "client_id": client_id,
        "username": email,
        "password": password,
        "realm": "User-Password-Headspace",
        "audience": "https://api.prod.headspace.com",
        "scope": "openid email",
    }

    response = session.post(TOKEN_URL, json=data)
    try:
        resp_json: dict = response.json()
    except ValueError:
        console.print(
            f"Headspace login returned an unexpected response ({response.status_code})",
            style="red",
        )
        return False

    access_token = resp_json.get("access_token")
    if access_token:
        return "bearer " + access_token

    if "error" in resp_json:
        console.print(resp_json["error"], style="red")
        if "error_description" in resp_json:
            console.print(resp_json["error_description"])
    else:
        console.print(resp_json)
    return False
