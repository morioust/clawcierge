class ClawciergeError(Exception):
    """Base exception for all Clawcierge errors."""


class HandleTakenError(ClawciergeError):
    def __init__(self, handle: str) -> None:
        self.handle = handle
        super().__init__(f"Handle '{handle}' is already taken")


class AgentNotFoundError(ClawciergeError):
    def __init__(self, identifier: str) -> None:
        self.identifier = identifier
        super().__init__(f"Agent not found: {identifier}")


class AuthenticationError(ClawciergeError):
    def __init__(self, detail: str = "Invalid or missing API key") -> None:
        self.detail = detail
        super().__init__(detail)


class PipelineRejectionError(ClawciergeError):
    def __init__(self, stage: str, reason: str) -> None:
        self.stage = stage
        self.reason = reason
        super().__init__(f"Rejected at {stage}: {reason}")


class AgentNotConnectedError(ClawciergeError):
    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        super().__init__(f"Agent {agent_id} is not connected")
