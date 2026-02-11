from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from clawcierge.config import settings
from clawcierge.database import engine
from clawcierge.middleware.errors import register_exception_handlers
from clawcierge.routes.admin import router as admin_router
from clawcierge.routes.agent_ws import router as agent_ws_router
from clawcierge.routes.agents import router as agents_router
from clawcierge.routes.capabilities import router as capabilities_router
from clawcierge.routes.directory import router as directory_router
from clawcierge.routes.health import router as health_router
from clawcierge.routes.info import router as info_router
from clawcierge.routes.policies import router as policies_router
from clawcierge.routes.requests import router as requests_router

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.PrintLoggerFactory(),
)

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    log.info("starting", env=settings.app_env)
    yield
    await engine.dispose()
    log.info("shutdown")


app = FastAPI(title="Clawcierge", version="0.1.0", lifespan=lifespan)

register_exception_handlers(app)

app.include_router(health_router)
app.include_router(info_router)
app.include_router(agents_router)
app.include_router(directory_router)
app.include_router(capabilities_router)
app.include_router(policies_router)
app.include_router(requests_router)
app.include_router(agent_ws_router)
app.include_router(admin_router)
