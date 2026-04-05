from pathlib import Path

from httpx import Client

from s2a.extract.auth import apply_storage_state_cookies
from s2a.files import write_json


def test_apply_storage_state_cookies_loads_cookies_into_httpx_client(tmp_path: Path) -> None:
    storage_state = tmp_path / "storage_state.json"
    write_json(
        storage_state,
        {
            "cookies": [
                {
                    "name": "siteUserCrumb",
                    "value": "abc123",
                    "domain": "example.com",
                    "path": "/",
                }
            ],
            "origins": [],
        },
    )

    client = Client()
    apply_storage_state_cookies(client, storage_state)

    assert client.cookies.get("siteUserCrumb", domain="example.com", path="/") == "abc123"
