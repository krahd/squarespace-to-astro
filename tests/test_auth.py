from pathlib import Path

from httpx import Client

from s2a.extract.auth import _rewrite_auth_timeout_error, _rewrite_navigation_error, apply_storage_state_cookies
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


def test_rewrite_navigation_error_explains_certificate_mismatch() -> None:
    error = _rewrite_navigation_error(
        RuntimeError(
            "Page.goto: net::ERR_CERT_COMMON_NAME_INVALID at https://tomas.laurenzo.squarespace.com/"),
        "https://tomas.laurenzo.squarespace.com/",
        insecure=False,
    )

    assert error is not None
    assert "TLS certificate validation failed" in str(error)
    assert "https://site.squarespace.com" in str(error)
    assert "--insecure" in str(error)


def test_rewrite_navigation_error_ignores_non_certificate_failures() -> None:
    assert (
        _rewrite_navigation_error(
            RuntimeError("Page.goto: net::ERR_NAME_NOT_RESOLVED at https://example.com/"),
            "https://example.com/",
            insecure=False,
        )
        is None
    )


def test_rewrite_auth_timeout_error_explains_missing_login_form() -> None:
    error = _rewrite_auth_timeout_error(
        "https://example.com/",
        mode="credentials",
    )

    assert "Timed out waiting for a login form" in str(error)
    assert "SQUARESPACE_USER" in str(error)
    assert "--login-url" in str(error)
