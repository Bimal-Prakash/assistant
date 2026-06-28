import logging
# pyrefly: ignore [missing-import]
from fastapi import FastAPI
from server.api.routes import router

from contextlib import asynccontextmanager
from core.config import MCP_SERVERS
from agent.mcp_client import start_mcp_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

logger = logging.getLogger("jarvis.server")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Booting MCP Servers...")
    for server_name, config in MCP_SERVERS.items():
        start_mcp_server(server_name, config["command"], config["args"])
    yield
    logger.info("Shutting down Jarvis...")

app = FastAPI(title="Jarvis Assistant API", version="1.0.0", lifespan=lifespan)

app.include_router(router)
