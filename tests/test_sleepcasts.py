from pyheadspace import __main__ as main


class FakeResponse:
    def __init__(self, json_data):
        self.json_data = json_data
        self.ok = True
        self.status_code = 200

    def json(self):
        return self.json_data


def test_get_sleepcast_assets_finds_current_tracks(monkeypatch):
    assets = [
        {"mediaItemId": 1, "metadata": {"trackType": "VOICE"}},
        {"mediaItemId": 2, "metadata": {"trackType": "AMBIENCE"}},
        {"mediaItemId": 3, "metadata": {"trackType": "MIXED"}},
    ]
    response = FakeResponse(assets)
    monkeypatch.setattr(main.session, "get", lambda url, params: response)

    result = main.get_sleepcast_assets(412, "2026-11-09")

    assert result["voice"]["mediaItemId"] == 1
    assert result["ambience"]["mediaItemId"] == 2
    assert result["mixed"]["mediaItemId"] == 3


def test_find_sleepcast_id_supports_current_and_public_urls():
    assert (
        main.find_sleepcast_id(
            "https://my.headspace.com/modes/explore/content/412?mode=sleep"
        )
        == 412
    )
    assert (
        main.find_sleepcast_id(
            "https://www.headspace.com/content/sleepcast/night-town/412"
        )
        == 412
    )


def test_get_sleepcast_catalog_deduplicates_and_sorts(monkeypatch):
    catalog = {
        "categories": [
            {
                "contentTiles": [
                    {"contentId": 2, "contentType": "SLEEPCAST", "title": "Zulu"},
                    {"contentId": 1, "contentType": "SLEEPCAST", "title": "Alpha"},
                ]
            },
            {
                "contentTiles": [
                    {"contentId": 2, "contentType": "SLEEPCAST", "title": "Zulu"},
                    {"contentId": 3, "contentType": "ONEOFF", "title": "Other"},
                ]
            },
        ]
    }
    response = FakeResponse(catalog)
    monkeypatch.setattr(main, "USER_ID", "user-id")
    monkeypatch.setattr(main.session, "get", lambda url, params: response)

    result = main.get_sleepcast_catalog()

    assert [item["contentId"] for item in result] == [1, 2]


def test_download_sleepcast_can_download_all_tracks(monkeypatch):
    assets = {
        track: {
            "mediaItemId": media_id,
            "analyticsData": {"content_name": "Night Town"},
        }
        for track, media_id in (("mixed", 1), ("voice", 2), ("ambience", 3))
    }
    downloads = []
    monkeypatch.setattr(main, "get_sleepcast_assets", lambda content_id, date: assets)
    monkeypatch.setattr(
        main, "download", lambda *args, **kwargs: downloads.append((args, kwargs))
    )

    main.download_sleepcast(
        412,
        track="all",
        container="mp3",
        playback_date=None,
        out="sleep",
    )

    assert [kwargs["filename"] for _, kwargs in downloads] == [
        "Night Town - Mixed",
        "Night Town - Voice",
        "Night Town - Ambience",
    ]
    assert all(args[0].endswith("?container=mp3") for args, _ in downloads)
    assert all(kwargs["authenticated"] for _, kwargs in downloads)
