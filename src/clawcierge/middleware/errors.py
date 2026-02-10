from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from clawcierge.errors import (
    AgentNotConnectedError,
    AgentNotFoundError,
    AuthenticationError,
    HandleTakenError,
    PipelineRejectionError,
)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HandleTakenError)
    async def handle_taken(request: Request, exc: HandleTakenError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"detail": str(exc), "handle": exc.handle},
        )

    @app.exception_handler(AgentNotFoundError)
    async def agent_not_found(request: Request, exc: AgentNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc)},
        )

    @app.exception_handler(AuthenticationError)
    async def authentication_error(request: Request, exc: AuthenticationError) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={"detail": exc.detail},
        )

    @app.exception_handler(PipelineRejectionError)
    async def pipeline_rejection(request: Request, exc: PipelineRejectionError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": exc.reason, "stage": exc.stage},
        )

    @app.exception_handler(AgentNotConnectedError)
    async def agent_not_connected(
        request: Request, exc: AgentNotConnectedError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"detail": str(exc)},
        )
