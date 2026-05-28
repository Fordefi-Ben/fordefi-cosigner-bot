from typing import Literal
from pydantic import BaseModel


class Decision(BaseModel):
    """The outcome of a validator's evaluation of a transaction."""

    action: Literal["approve", "abort"]
    reason: str
