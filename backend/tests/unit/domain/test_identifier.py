# file_name: test_identifier.py

"""Unit tests for UUIDv7 entity identifiers."""

import time
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest

from app.domain.value_objects.identifier import (
    is_valid_id,
    new_id,
    parse_id,
    timestamp_ms,
)


def test_generated_identifiers_are_version_7():
    assert new_id().version == 7


def test_generated_identifiers_use_the_rfc_variant():
    # RFC 9562 variant bits are 0b10, which Python reports as RFC_4122.
    assert new_id().variant == "specified in RFC 4122"


def test_identifiers_are_unique():
    identifiers = {new_id() for _ in range(10_000)}

    assert len(identifiers) == 10_000


def test_identifiers_are_chronologically_ordered():
    identifiers = [new_id() for _ in range(1_000)]

    assert identifiers == sorted(identifiers)


def test_identifiers_stay_ordered_across_milliseconds():
    first = new_id()
    time.sleep(0.002)
    second = new_id()

    assert second > first


def test_identifiers_are_unique_under_concurrency():
    with ThreadPoolExecutor(max_workers=8) as pool:
        identifiers = set(pool.map(lambda _: new_id(), range(4_000)))

    assert len(identifiers) == 4_000


def test_the_embedded_timestamp_is_close_to_now():
    before = time.time_ns() // 1_000_000
    identifier = new_id()

    assert abs(timestamp_ms(identifier) - before) < 1_000


def test_a_uuid7_is_recognised():
    assert is_valid_id(new_id()) is True
    assert is_valid_id(str(new_id())) is True


def test_other_uuid_versions_are_rejected():
    assert is_valid_id(uuid4()) is False


@pytest.mark.parametrize("value", ["", "not-a-uuid", None, 42, object()])
def test_malformed_values_are_rejected(value):
    assert is_valid_id(value) is False


def test_parse_returns_the_identifier():
    identifier = new_id()

    assert parse_id(str(identifier)) == identifier


def test_parse_raises_on_an_invalid_identifier():
    with pytest.raises(ValueError) as error:
        parse_id(str(uuid4()))

    assert "UUID version 7" in str(error.value)


def test_parse_can_report_failure_without_raising():
    assert parse_id("nonsense", strict=False) is None


def test_identifiers_serialise_as_strings():
    identifier = new_id()

    assert str(identifier) == str(UUID(str(identifier)))
    assert len(str(identifier)) == 36
