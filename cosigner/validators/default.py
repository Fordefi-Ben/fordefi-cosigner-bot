from cosigner.models.decision import Decision
from cosigner.models.transaction import Transaction
from cosigner.validators.base import BaseValidator


class DefaultValidator(BaseValidator):
    """
    Safe fallback for any transaction whose policy rule_id has no registered validator.

    Always aborts — unrecognized policies are blocked, not approved.
    This is intentionally fail-closed: a misconfigured or new policy rule should
    never silently approve transactions.
    """

    async def validate(self, tx: Transaction) -> Decision:
        policy = tx.managed_transaction_data.policy_match
        rule_id = policy.rule_id if policy else "unknown"
        return Decision(
            action="abort",
            reason=f"no validator registered for policy rule_id: {rule_id}",
        )
