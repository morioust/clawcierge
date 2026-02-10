from typing import Any

import jsonschema
from pydantic import BaseModel, Field, model_validator


class CapabilityDefinition(BaseModel):
    action: str = Field(min_length=1, max_length=200)
    params_schema: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_json_schema(self) -> "CapabilityDefinition":
        if self.params_schema:
            try:
                jsonschema.Draft7Validator.check_schema(self.params_schema)
            except jsonschema.SchemaError as e:
                raise ValueError(f"Invalid JSON Schema in params_schema: {e.message}") from e
        return self


class UploadCapabilitiesRequest(BaseModel):
    capabilities: list[CapabilityDefinition] = Field(min_length=1)


class CapabilityContractResponse(BaseModel):
    id: str
    agent_id: str
    version: int
    capabilities: list[dict[str, Any]]
    constraints: dict[str, Any]
    is_active: bool
