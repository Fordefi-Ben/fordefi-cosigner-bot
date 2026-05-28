"""
Pydantic models mirroring the Fordefi enriched transaction payload.

Only the fields the co-signer logic actually uses are typed explicitly.
All other fields are accepted via extra="allow" so the models won't break
if Fordefi adds new fields to the API.

Key design notes:
- `from` is a Python keyword, so Transfer uses Field(alias="from") + populate_by_name=True
- vault_group_ids uses list[Any] because the API sometimes sends [null] entries
- WebhookEnvelope wraps every inbound webhook; Transaction lives in envelope.event
"""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class Vault(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: Optional[str] = None
    name: Optional[str] = None
    address: Optional[str] = None
    state: Optional[str] = None
    type: Optional[str] = None
    # May contain null entries in some API responses, so typed as list[Any]
    vault_group_ids: Optional[list[Any]] = None


class EnrichedAddress(BaseModel):
    """
    A transaction participant that may be a vault, a contact, or an external address.
    Used for transfer from/to, allowance owner/spender, etc.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    vault: Optional[Vault] = None
    address: Optional[str] = None
    type: Optional[str] = None


class Chain(BaseModel):
    model_config = ConfigDict(extra="allow")

    chain_type: Optional[str] = None
    chain_id: Optional[int] = None
    unique_id: Optional[str] = None
    name: Optional[str] = None


class Risk(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Optional[str] = None
    severity: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None


class PolicyMatch(BaseModel):
    model_config = ConfigDict(extra="allow")

    is_default: Optional[bool] = None
    rule_id: Optional[str] = None
    rule_name: Optional[str] = None
    action_type: Optional[str] = None


class Transfer(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    amount: Optional[str] = None
    # "from" is a reserved keyword; alias required
    from_: Optional[EnrichedAddress] = Field(default=None, alias="from")
    to: Optional[EnrichedAddress] = None


class Allowance(BaseModel):
    model_config = ConfigDict(extra="allow")

    amount: Optional[str] = None
    spender: Optional[EnrichedAddress] = None
    owner: Optional[EnrichedAddress] = None
    # ISO 8601 datetime string if an expiration was set; None means no expiration
    expiration: Optional[str] = None


class BalanceChange(BaseModel):
    model_config = ConfigDict(extra="allow")

    diff: Optional[str] = None
    address: Optional[EnrichedAddress] = None


class Bridge(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: Optional[str] = None
    amount: Optional[str] = None


class Effects(BaseModel):
    model_config = ConfigDict(extra="allow")

    transfers: list[Transfer] = Field(default_factory=list)
    allowances: list[Allowance] = Field(default_factory=list)
    balance_changes: list[BalanceChange] = Field(default_factory=list)
    bridges: list[Bridge] = Field(default_factory=list)


class ExpectedResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    effects: Effects = Field(default_factory=Effects)


class ApproverEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    # Full user object; typed as dict to avoid strict parsing of nested user shape
    user: Optional[dict[str, Any]] = None
    modified_at: Optional[str] = None
    state: Optional[str] = None


class ApprovalGroup(BaseModel):
    model_config = ConfigDict(extra="allow")

    quorum_size: Optional[int] = None
    approvers: list[ApproverEntry] = Field(default_factory=list)


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    state: Optional[str] = None
    required_groups: Optional[int] = None
    approval_groups: list[ApprovalGroup] = Field(default_factory=list)
    error_message: Optional[str] = None


class ManagedTransactionData(BaseModel):
    model_config = ConfigDict(extra="allow")

    policy_match: Optional[PolicyMatch] = None
    risks: list[Risk] = Field(default_factory=list)
    aml_policy_match: Optional[PolicyMatch] = None
    vault: Optional[Vault] = None
    approval_request: Optional[ApprovalRequest] = None


# Severity levels in ascending order — used by has_risk_at_or_above
_SEVERITY_ORDER: dict[str, int] = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class Transaction(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str
    state: Optional[str] = None
    type: Optional[str] = None
    chain: Optional[Chain] = None
    managed_transaction_data: Optional[ManagedTransactionData] = None
    expected_result: Optional[ExpectedResult] = None

    # ── EVM message fields (type == "evm_message") ────────────────────────
    # "personal_message_type" = EIP-191 personal sign
    # "typed_message_type"    = EIP-712 structured data
    evm_message_type: Optional[str] = None
    # Plain-text (or hex) body for personal messages; JSON string for typed data
    raw_data: Optional[str] = None
    # Sender address for message-signing requests (no from/to on messages)
    sender: Optional[EnrichedAddress] = None

    def outbound_transfers(self) -> list[Transfer]:
        """Return transfers where the signing vault (managed_transaction_data.vault) is the sender."""
        if self.managed_transaction_data is None:
            return []
        vault = self.managed_transaction_data.vault
        if vault is None or vault.id is None:
            return []
        if self.expected_result is None:
            return []
        return [
            t
            for t in self.expected_result.effects.transfers
            if t.from_ and t.from_.vault and t.from_.vault.id == vault.id
        ]

    def has_risk_at_or_above(self, severity: str) -> bool:
        """Return True if any risk in the transaction meets or exceeds the given severity."""
        if self.managed_transaction_data is None:
            return False
        threshold = _SEVERITY_ORDER.get(severity.lower(), 0)
        return any(
            _SEVERITY_ORDER.get((r.severity or "").lower(), -1) >= threshold
            for r in self.managed_transaction_data.risks
        )


class WebhookEnvelope(BaseModel):
    """Outer wrapper for every Fordefi webhook delivery."""

    model_config = ConfigDict(extra="allow")

    webhook_id: Optional[str] = None
    event_id: Optional[str] = None
    attempt: Optional[int] = None
    sent_at: Optional[str] = None
    event_type: Optional[str] = None
    # Raw event dict — caller parses into Transaction after type filtering
    event: dict[str, Any]
