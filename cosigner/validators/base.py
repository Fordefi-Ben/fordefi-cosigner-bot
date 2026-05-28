from abc import ABC, abstractmethod

from cosigner.models.decision import Decision
from cosigner.models.transaction import Transaction


class BaseValidator(ABC):
    """
    Abstract base for all transaction validators.

    Implement validate() to inspect the transaction and return a Decision.
    The method is async so validators can perform I/O (e.g. allowlist lookups
    against an external service) without blocking the event loop.
    """

    @abstractmethod
    async def validate(self, tx: Transaction) -> Decision:
        """Evaluate tx and return Decision(action="approve"|"abort", reason=...)."""
        ...
