from typing import Any

import simpleeval
from pydantic import BaseModel, Field, model_validator


class PolicyRule(BaseModel):
    condition: str = Field(min_length=1, max_length=500)
    action: str = Field(pattern=r"^(reject|allow)$")
    reason: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def validate_expression(self) -> "PolicyRule":
        try:
            evaluator = simpleeval.EvalWithCompoundTypes()
            # Provide dummy namespace so name lookups don't fail
            evaluator.names = {"sender_id": "", "action": ""}
            evaluator.eval(self.condition)
        except simpleeval.FeatureNotAvailable as e:
            raise ValueError(f"Disallowed feature in policy expression: {e}") from e
        except SyntaxError as e:
            raise ValueError(f"Invalid policy expression syntax: {e}") from e
        except simpleeval.NameNotDefined:
            # Expression references names not in our dummy namespace — that's fine
            pass
        except Exception:
            # Other eval errors (type errors, etc.) are OK at validation time;
            # actual values will differ at runtime
            pass
        return self


class UploadPoliciesRequest(BaseModel):
    rules: list[PolicyRule] = Field(min_length=1)


class PolicyResponse(BaseModel):
    id: str
    agent_id: str
    version: int
    rules: list[dict[str, Any]]
    is_active: bool
