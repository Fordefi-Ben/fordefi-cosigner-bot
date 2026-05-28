"""
Validator registry — maps policy rule_ids to validator instances.

This is the single place customers configure which validators handle which
Fordefi policy rules. Registration happens in main.py at startup; the
registry itself has no hardcoded rules.
"""
import logging

from cosigner.models.decision import Decision
from cosigner.models.transaction import Transaction
from cosigner.validators.base import BaseValidator
from cosigner.validators.default import DefaultValidator

logger = logging.getLogger(__name__)


class ValidatorRegistry:
    """
    Routes incoming transactions to the appropriate validator by policy rule_id.

    Any transaction whose rule_id has no registered validator is handled by
    DefaultValidator, which always aborts (fail-closed).
    """

    def __init__(self) -> None:
        self._validators: dict[str, BaseValidator] = {}
        self._default = DefaultValidator()

    def register(self, rule_id: str, validator: BaseValidator) -> None:
        """Associate a validator with a Fordefi policy rule_id (UUID string)."""
        self._validators[rule_id] = validator
        logger.info(
            "registered validator %s for rule_id=%s",
            type(validator).__name__,
            rule_id,
        )

    async def dispatch(self, tx: Transaction) -> Decision:
        """
        Look up the validator for the transaction's policy rule_id and run it.
        Falls back to DefaultValidator if no match is found.
        """
        policy = tx.managed_transaction_data.policy_match
        rule_id = policy.rule_id if policy else None

        validator = self._validators.get(rule_id) if rule_id else None

        if validator is None:
            logger.info(
                "no validator for rule_id=%s on tx %s, using default",
                rule_id,
                tx.id,
            )
            return await self._default.validate(tx)

        logger.info(
            "dispatching tx %s to %s (rule_id=%s)",
            tx.id,
            type(validator).__name__,
            rule_id,
        )
        return await validator.validate(tx)
