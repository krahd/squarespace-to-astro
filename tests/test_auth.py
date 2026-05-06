from pathlib import Path

from httpx import Client

from s2a.extract.auth import (
    _rewrite_auth_timeout_error,
    _rewrite_navigation_error,
    apply_storage_state_cookies,
    check_storage_state,
)
from s2a.files import write_json


def test_apply_storage_state_cookies_loads_cookies_into_httpx_client(
    tmp_path: Path,
) -> None:
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

    assert (
        client.cookies.get("siteUserCrumb", domain="example.com", path="/") == "abc123"
    )


def test_rewrite_navigation_error_explains_certificate_mismatch() -> None:
    error = _rewrite_navigation_error(
        RuntimeError(
            "Page.goto: net::ERR_CERT_COMMON_NAME_INVALID at https://tomas.laurenzo.squarespace.com/"
        ),
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
            RuntimeError(
                "Page.goto: net::ERR_NAME_NOT_RESOLVED at https://example.com/"
            ),
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


def test_check_storage_state_missing_file(tmp_path: Path) -> None:
    warnings = check_storage_state(tmp_path / "nonexistent.json")
    assert len(warnings) == 1
    assert "not found" in warnings[0]


def test_check_storage_state_no_cookies(tmp_path: Path) -> None:
    path = tmp_path / "storage.json"
    write_json(path, {"cookies": [], "origins": []})
    warnings = check_storage_state(path)
    assert len(warnings) == 1
    assert "no cookies" in warnings[0].lower()


def test_check_storage_state_expired_cookies(tmp_path: Path) -> None:
    path = tmp_path / "storage.json"
    write_json(
        path,
        {
            "cookies": [
                {
                    "name": "stale_token",
                    "value": "abc",
                    "domain": "example.com",
                    "path": "/",
                    "expires": 1000,  # Far in the past
                },
                {
                    "name": "session_cookie",
                    "value": "xyz",
                    "domain": "example.com",
                    "path": "/",
                    "expires": -1,  # Session cookie — not flagged
                },
            ],
            "origins": [],
        },
    )
    warnings = check_storage_state(path)
    assert len(warnings) == 1
    assert "stale_token" in warnings[0]
    assert "session_cookie" not in warnings[0]


def test_check_storage_state_valid_cookies(tmp_path: Path) -> None:
    import time

    path = tmp_path / "storage.json"
    future = int(time.time()) + 86400  # 24 hours from now
    write_json(
        path,
        {
            "cookies": [
                {
                    "name": "auth",
                    "value": "valid",
                    "domain": "example.com",
                    "path": "/",
                    "expires": future,
                }
            ],
            "origins": [],
        },
    )
    warnings = check_storage_state(path)
    assert warnings == []
