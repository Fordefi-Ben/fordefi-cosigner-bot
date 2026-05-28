"""
Tests for ExactMatcher, RegexMatcher, and PersonalMessageValidator.
Uses the real personal message fixture captured from the Fordefi API.
"""
import copy
import json
from pathlib import Path

import pytest

from cosigner.models.transaction import Transaction
from cosigner.validators.evm.personal_message import (
    ExactMatcher,
    PersonalMessageValidator,
    RegexMatcher,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_personal_msg.json"

LIGHTER_SIGNIN = (
    "Access Lighter account.\n\n"
    "Only sign this message for a trusted client!\n"
    "Chain ID: 304\n\n"
    "Timestamp: 1780010299120."
)
LIGHTER_REGISTER = (
    "Register Lighter Account\n\n"
    "pubkey: 0xe8e0b400fb2ef8b1b22d79e41d9d6fbf857cb0a36b74b7250551055c54b8ad4371ff492a07d88e84\n"
    "nonce: 0x0000000000000000\n"
    "account index: 0x00000000000b17ed\n"
    "api key index: 0x0000000000000000\n"
    "Only sign this message for a trusted client!"
)


@pytest.fixture(scope="module")
def raw_msg() -> dict:
    return json.loads(FIXTURE.read_text())


@pytest.fixture(scope="module")
def msg_tx(raw_msg) -> Transaction:
    return Transaction.model_validate(raw_msg)


# ── ExactMatcher ──────────────────────────────────────────────────────────────


def test_exact_matcher_hit() -> None:
    m = ExactMatcher({LIGHTER_SIGNIN})
    assert m.matches(LIGHTER_SIGNIN) is not None


def test_exact_matcher_miss() -> None:
    m = ExactMatcher({"some other message"})
    assert m.matches(LIGHTER_SIGNIN) is None


def test_exact_matcher_case_sensitive() -> None:
    m = ExactMatcher({"Hello World"})
    assert m.matches("hello world") is None
    assert m.matches("Hello World") is not None


def test_exact_matcher_multiple_options() -> None:
    m = ExactMatcher({LIGHTER_SIGNIN, LIGHTER_REGISTER})
    assert m.matches(LIGHTER_SIGNIN) is not None
    assert m.matches(LIGHTER_REGISTER) is not None
    assert m.matches("unknown message") is None


# ── RegexMatcher ──────────────────────────────────────────────────────────────


def test_regex_matcher_hit() -> None:
    m = RegexMatcher(r"^Access Lighter account\.")
    assert m.matches(LIGHTER_SIGNIN) is not None


def test_regex_matcher_miss() -> None:
    m = RegexMatcher(r"^Register Lighter Account")
    assert m.matches(LIGHTER_SIGNIN) is None


def test_regex_matcher_variable_fields() -> None:
    # Timestamp varies — regex handles it
    m = RegexMatcher(r"Timestamp: \d+\.")
    assert m.matches(LIGHTER_SIGNIN) is not None
    modified = LIGHTER_SIGNIN.replace("1780010299120", "9999999999999")
    assert m.matches(modified) is not None


def test_regex_matcher_hex_fields() -> None:
    m = RegexMatcher(r"pubkey: 0x[0-9a-f]+")
    assert m.matches(LIGHTER_REGISTER) is not None


def test_regex_matcher_case_insensitive() -> None:
    import re
    m = RegexMatcher(r"access lighter", flags=re.IGNORECASE)
    assert m.matches(LIGHTER_SIGNIN) is not None


def test_regex_matcher_anchored_full_string() -> None:
    pattern = (
        r"^Access Lighter account\.\n\n"
        r"Only sign this message for a trusted client!\n"
        r"Chain ID: \d+\n\n"
        r"Timestamp: \d+\.$"
    )
    m = RegexMatcher(pattern)
    assert m.matches(LIGHTER_SIGNIN) is not None
    assert m.matches(LIGHTER_SIGNIN + " extra") is None


# ── PersonalMessageValidator ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_approve_lighter_signin(raw_msg: dict) -> None:
    data = copy.deepcopy(raw_msg)
    data["raw_data"] = LIGHTER_SIGNIN
    tx = Transaction.model_validate(data)

    validator = PersonalMessageValidator(matchers=[RegexMatcher(r"^Access Lighter account\.")])
    decision = await validator.validate(tx)
    assert decision.action == "approve"


@pytest.mark.asyncio
async def test_approve_lighter_register(raw_msg: dict) -> None:
    data = copy.deepcopy(raw_msg)
    data["raw_data"] = LIGHTER_REGISTER
    tx = Transaction.model_validate(data)

    validator = PersonalMessageValidator(
        matchers=[RegexMatcher(r"^Register Lighter Account\n\npubkey: 0x[0-9a-f]+")]
    )
    decision = await validator.validate(tx)
    assert decision.action == "approve"


@pytest.mark.asyncio
async def test_abort_unrecognized_message(raw_msg: dict) -> None:
    data = copy.deepcopy(raw_msg)
    data["raw_data"] = "Sign this unknown message"
    tx = Transaction.model_validate(data)

    validator = PersonalMessageValidator(matchers=[RegexMatcher(r"^Access Lighter")])
    decision = await validator.validate(tx)
    assert decision.action == "abort"
    assert "no matcher" in decision.reason


@pytest.mark.asyncio
async def test_first_matcher_wins(raw_msg: dict) -> None:
    data = copy.deepcopy(raw_msg)
    data["raw_data"] = LIGHTER_SIGNIN
    tx = Transaction.model_validate(data)

    validator = PersonalMessageValidator(
        matchers=[
            RegexMatcher(r"^Access Lighter account\."),
            RegexMatcher(r"should never reach here"),
        ]
    )
    decision = await validator.validate(tx)
    assert decision.action == "approve"
    assert "Access Lighter" in decision.reason


@pytest.mark.asyncio
async def test_fallback_to_second_matcher(raw_msg: dict) -> None:
    data = copy.deepcopy(raw_msg)
    data["raw_data"] = LIGHTER_REGISTER
    tx = Transaction.model_validate(data)

    validator = PersonalMessageValidator(
        matchers=[
            RegexMatcher(r"^Access Lighter account\."),   # misses
            RegexMatcher(r"^Register Lighter Account"),    # hits
        ]
    )
    decision = await validator.validate(tx)
    assert decision.action == "approve"


@pytest.mark.asyncio
async def test_exact_matcher_in_validator(raw_msg: dict) -> None:
    data = copy.deepcopy(raw_msg)
    data["raw_data"] = "I agree to the terms"
    tx = Transaction.model_validate(data)

    validator = PersonalMessageValidator(matchers=[ExactMatcher({"I agree to the terms"})])
    decision = await validator.validate(tx)
    assert decision.action == "approve"


@pytest.mark.asyncio
async def test_abort_wrong_tx_type(msg_tx: Transaction) -> None:
    data = msg_tx.model_dump()
    data["type"] = "evm_transaction"
    tx = Transaction.model_validate(data)

    validator = PersonalMessageValidator(matchers=[RegexMatcher(r".*")])
    decision = await validator.validate(tx)
    assert decision.action == "abort"
    assert "personal_message_type" in decision.reason


@pytest.mark.asyncio
async def test_abort_missing_raw_data(raw_msg: dict) -> None:
    data = copy.deepcopy(raw_msg)
    data["raw_data"] = None
    tx = Transaction.model_validate(data)

    validator = PersonalMessageValidator(matchers=[RegexMatcher(r".*")])
    decision = await validator.validate(tx)
    assert decision.action == "abort"
    assert "raw_data" in decision.reason
