"""Shared base model for every Spec sub-model."""

from pydantic import BaseModel, ConfigDict


class SpecModel(BaseModel):
    """Base for Spec models.

    Enables `validate_assignment` so direct field assignment validates.
    """

    model_config = ConfigDict(validate_assignment=True, arbitrary_types_allowed=True)
