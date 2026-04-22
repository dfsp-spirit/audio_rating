import pytest

from audiorating_backend.parsers.settings_parser import (
    parse_admin_credentials,
    parse_string_or_json_list,
)


def test_parse_string_or_json_list_accepts_plain_string():
    assert parse_string_or_json_list("admin", "AR_API_ADMIN_USERNAME") == ["admin"]


def test_parse_string_or_json_list_accepts_json_list():
    assert parse_string_or_json_list('["admin1", "admin2"]', "AR_API_ADMIN_USERNAME") == [
        "admin1",
        "admin2",
    ]


def test_parse_admin_credentials_accepts_matching_json_lists():
    credentials = parse_admin_credentials(
        '["admin1", "admin2"]',
        '["secret1", "secret2"]',
    )
    assert credentials == [("admin1", "secret1"), ("admin2", "secret2")]


def test_parse_admin_credentials_accepts_plain_strings_for_backwards_compatibility():
    credentials = parse_admin_credentials("admin", "secret")
    assert credentials == [("admin", "secret")]


def test_parse_admin_credentials_raises_when_lengths_do_not_match():
    with pytest.raises(ValueError, match="same number of entries"):
        parse_admin_credentials('["admin1", "admin2"]', '["secret1"]')