"""
Validator for EIP-191 personal message signing requests (evm_message_type = personal_message_type).

`PersonalMessageValidator` holds a list of `MessageMatcher` instances and approves
the transaction if any matcher succeeds. If none match, the transaction is aborted
(fail-closed).

Built-in matchers:
- `ExactMatcher` — raw text must equal one of a set of strings exactly
- `RegexMatcher` — raw text must match a regular-expression pattern

Usage example::

    from cosigner.validators.evm.personal_message import (
        PersonalMessageValidator, RegexMatcher, ExactMatcher
    )

    validator = PersonalMessageValidator(
        matchers=[
            RegexMatcher(r"^Access MyApp\\.\\n\\nTimestamp: \\d+\\.$"),
            ExactMatcher({"I agree to the terms of service"}),
        ],
    )
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Optional

from cosigner.models.decision import Decision
from cosigner.models.transaction import Transaction
from cosigner.validators.base import BaseValidator


class MessageMatcher(ABC):
    """
    Abstract base for a single match rule.

    ``matches()`` returns a human-readable description of the match on success,
    or None if the rule does not match.
    """

    @abstractmethod
    def matches(self, raw: str) -> Optional[str]:
        """Return a description string if matched, None otherwise."""
        ...


class ExactMatcher(MessageMatcher):
    """
    Approve if the raw message text is exactly one of the configured strings.

    Comparison is byte-exact — no case folding or whitespace trimming.
    """

    def __init__(self, messages: set[str]) -> None:
        self._messages = messages

    def matches(self, raw: str) -> Optional[str]:
        if raw in self._messages:
            return f"exact match on {len(raw)}-character message"
        return None


class RegexMatcher(MessageMatcher):
    """
    Approve if the raw message text matches a regular-expression pattern.

    The pattern is applied with ``re.search``, so anchors (``^``, ``$``) should
    be used if a full-string match is required.
    """

    def __init__(self, pattern: str, flags: int = 0) -> None:
        self._pattern = re.compile(pattern, flags)

    def matches(self, raw: str) -> Optional[str]:
        if self._pattern.search(raw):
            return f"regex match: {self._pattern.pattern!r}"
        return None


class PersonalMessageValidator(BaseValidator):
    """
    Approve EIP-191 personal messages that satisfy at least one configured matcher.
    Abort if no matcher matches (fail-closed).

    Matchers are evaluated in order — the first match wins.
    """

    def __init__(self, matchers: list[MessageMatcher]) -> None:
        self._matchers = matchers

    async def validate(self, tx: Transaction) -> Decision:
        if tx.type != "evm_message" or tx.evm_message_type != "personal_message_type":
            return Decision(
                action="abort",
                reason=(
                    f"PersonalMessageValidator expects personal_message_type, "
                    f"got type={tx.type!r} evm_message_type={tx.evm_message_type!r}"
                ),
            )

        raw = tx.raw_data
        if not raw:
            return Decision(action="abort", reason="personal message has no raw_data")

        for matcher in self._matchers:
            description = matcher.matches(raw)
            if description:
                return Decision(action="approve", reason=description)

        return Decision(action="abort", reason="no matcher approved this personal message")
