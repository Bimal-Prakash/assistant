import asyncio
import threading
import logging
from typing import List, Dict, Any, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import AsyncExitStack

logger = logging.getLogger("jarvis.mcp_client")

class AsyncMCPClient:
    def __init__(self, command: str, args: List[str]):
        self.server_parameters = StdioServerParameters(command=command, args=args)
        self.session: Optional[ClientSession] = None
        self._exit_stack: Optional[AsyncExitStack] = None
        self.tools: List[Dict[str, Any]] = []

    async def connect(self):
        logger.info("Connecting to MCP Server: %s %s", self.server_parameters.command, self.server_parameters.args)
        self._exit_stack = AsyncExitStack()
        try:
            read, write = await self._exit_stack.enter_async_context(stdio_client(self.server_parameters))
            self.session = await self._exit_stack.enter_async_context(ClientSession(read, write))
            await self.session.initialize()
            
            tools_response = await self.session.list_tools()
            self.tools = [{"name": t.name, "description": t.description, "inputSchema": t.inputSchema} for t in tools_response.tools]
            logger.info("MCP Server connected. Loaded %d tools.", len(self.tools))
        except Exception as e:
            logger.error("Failed to connect to MCP server: %s", e)
            await self.cleanup()

    async def call_tool(self, name: str, args: Dict[str, Any]) -> str:
        if not self.session:
            return "MCP Client not connected"
        try:
            result = await self.session.call_tool(name, arguments=args)
            return "\n".join(c.text for c in result.content if c.type == "text")
        except Exception as e:
            logger.error("MCP tool call failed: %s", e)
            return f"Error executing tool: {e}"

    async def cleanup(self):
        if self._exit_stack:
            await self._exit_stack.aclose()
        self.session = None
        self._exit_stack = None


class BackgroundMCPManager:
    """Runs the MCP client in a dedicated background asyncio thread so it stays alive."""
    def __init__(self, command: str, args: List[str]):
        self.client = AsyncMCPClient(command, args)
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._connected_event = threading.Event()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self.client.connect())
        self._connected_event.set()
        self._loop.run_forever()

    def start(self):
        self._thread.start()
        # Wait up to 5 seconds for connection
        self._connected_event.wait(timeout=5.0)

    def stop(self):
        if self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.client.cleanup(), self._loop)
            self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=2.0)

    def get_tools(self) -> List[Dict[str, Any]]:
        return self.client.tools

    def call_tool(self, name: str, args: Dict[str, Any]) -> str:
        if not self.client.session:
            return "MCP Client not connected"
        
        future = asyncio.run_coroutine_threadsafe(self.client.call_tool(name, args), self._loop)
        try:
            return future.result(timeout=10.0) # 10 sec timeout for tool execution
        except Exception as e:
            return f"Timeout or error waiting for tool: {e}"

# Global registry for active MCP servers
ACTIVE_MCP_SERVERS: Dict[str, BackgroundMCPManager] = {}

def start_mcp_server(server_name: str, command: str, args: List[str]):
    if server_name in ACTIVE_MCP_SERVERS:
        return
    manager = BackgroundMCPManager(command, args)
    manager.start()
    ACTIVE_MCP_SERVERS[server_name] = manager
    logger.info("Started MCP Server %s", server_name)

def get_all_mcp_tools() -> List[Dict[str, Any]]:
    tools = []
    for server_name, manager in ACTIVE_MCP_SERVERS.items():
        for t in manager.get_tools():
            # Prefix tool name with server to avoid collisions
            t_prefixed = t.copy()
            t_prefixed["name"] = f"mcp_{server_name}_{t['name']}"
            tools.append(t_prefixed)
    return tools

def call_mcp_tool(full_tool_name: str, args: Dict[str, Any]) -> str:
    if not full_tool_name.startswith("mcp_"):
        return "Not an MCP tool"
    
    parts = full_tool_name.split("_", 2)
    if len(parts) < 3:
        return "Invalid MCP tool name"
        
    server_name = parts[1]
    tool_name = parts[2]
    
    manager = ACTIVE_MCP_SERVERS.get(server_name)
    if not manager:
        return f"MCP server '{server_name}' not found or not running"
        
    return manager.call_tool(tool_name, args)
