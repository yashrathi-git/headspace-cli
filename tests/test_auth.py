from pyheadspace import auth


class FakeResponse:
    def __init__(
        self, *, url="", history=None, text="", json_data=None, status_code=200
    ):
        self.url = url
        self.history = history or []
        self.text = text
        self.json_data = json_data
        self.status_code = status_code

    def raise_for_status(self):
        return None

    def json(self):
        return self.json_data


def test_get_client_id_from_app_config(monkeypatch):
    app = FakeResponse(
        url="https://my.headspace.com/",
        text='<link href="/static/js/configHelpers-current.js">',
    )
    config = FakeResponse(
        url="https://my.headspace.com/static/js/configHelpers-current.js",
        text="const config = {clientId: `current-client`};",
    )

    def get(url):
        if url == auth.LOGIN_URL:
            return app
        return config

    monkeypatch.setattr(auth.session, "get", get)

    assert auth.get_client_id() == "current-client"


def test_get_client_id_from_legacy_page(monkeypatch):
    response = FakeResponse(text='window.config = {clientId: "legacy-client"};')
    monkeypatch.setattr(auth.session, "get", lambda url: response)

    assert auth.get_client_id() == "legacy-client"


def test_authenticate_uses_password_realm_token_grant(monkeypatch):
    request = {}

    def post(url, json):
        request.update(url=url, json=json)
        return FakeResponse(json_data={"access_token": "secret-token"})

    monkeypatch.setattr(auth, "get_client_id", lambda: "current-client")
    monkeypatch.setattr(auth.session, "post", post)

    assert auth.authenticate("person@example.com", "password") == "bearer secret-token"
    assert request["url"] == auth.TOKEN_URL
    assert request["json"]["grant_type"].endswith("password-realm")
    assert request["json"]["client_id"] == "current-client"
