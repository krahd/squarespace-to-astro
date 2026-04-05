from s2a.extract.json_data import build_json_data_url
from s2a.url_utils import canonicalize_page_url, coerce_url, is_crawlable_link


def test_coerce_url_adds_scheme_and_root_path() -> None:
    assert coerce_url("example.com") == "https://example.com/"


def test_canonicalize_page_url_strips_query_fragment_and_trailing_slash() -> None:
    assert (
        canonicalize_page_url("https://example.com/about/?ref=nav#team")
        == "https://example.com/about"
    )


def test_build_json_data_url_sets_format_query_param() -> None:
    assert (
        build_json_data_url("https://example.com/about")
        == "https://example.com/about?format=json-pretty"
    )


def test_is_crawlable_link_rejects_assets() -> None:
    assert not is_crawlable_link("https://example.com/logo.png", "https://example.com")
