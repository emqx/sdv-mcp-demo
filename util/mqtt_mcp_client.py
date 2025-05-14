from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Optional, List, Dict
from urllib.parse import urlparse
import anyio

from mcp.client.session import ClientSession
from mcp.client.mqtt import MqttTransportClient, MqttOptions
from mcp.shared.mqtt import configure_logging


class MQTTMCPClient(ClientSession):

    def __init__(
        self,
        command_or_url: str,
        client_id: str,
        server_name_filter: str,
        server_counts: int,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: int = 30,
    ):
        self.command_or_url = command_or_url
        self.client_id = client_id
        self.server_name_filter = server_name_filter
        self.server_counts = server_counts
        send_stream, receive_stream = anyio.create_memory_object_stream()
        self.server_discover_finish_snd = send_stream
        self.server_discover_finish_rcv = receive_stream
        self.mcp_servers = []
        self.args = args or []
        self.env = env or {}
        self.timeout = timeout
    
    async def on_mcp_server_discovered(self, client, server_name):
        print(f"Discovered {server_name}, connecting ...")
        await client.initialize_mcp_server(server_name)

    async def on_mcp_connect(self, client, server_name, connect_result):
        success, _init_result = connect_result
        self.mcp_servers.append({'server_name': server_name, 'success': success})

        print(f"Server Names now: {self.mcp_servers}")
        if len(self.mcp_servers) >= self.server_counts:
            ## We stop the discovery if we have got at least 2 MCP/MQTT servers
            print(f"Now that got {self.server_counts} MCP/MQTT servers, stop discovery.")
            await self.server_discover_finish_snd.send('discovery_finished')

    @asynccontextmanager
    async def _run_session(self):
        parse_url = urlparse(self.command_or_url)
        if parse_url.scheme in ('mqtt'):
            host_name = parse_url.hostname
            port = parse_url.port
            async with MqttTransportClient(
                self.client_id,
                server_name_filter = self.server_name_filter,
                auto_connect_to_mcp_server = True,
                on_mcp_server_discovered = self.on_mcp_server_discovered,
                on_mcp_connect = self.on_mcp_connect,
                mqtt_options = MqttOptions(
                    host = host_name,
                    port = port)
            ) as streams:
                streams.start()
                async with self.server_discover_finish_rcv:
                    async for item in self.server_discover_finish_rcv:
                        if item == 'discovery_finished':
                            break
                for server in self.mcp_servers:
                    if not server['success']:
                        print(f"Failed to initalize with MCP server: {server['server_name']}")
                    print(f"Initalized with MCP/MQTT server: {server['server_name']}")
                    async with streams.get_session(server['server_name']) as session:
                        yield session

    async def call_tool(self, tool_name: str, arguments: dict):
        async with self._run_session() as session:
            return await session.call_tool(tool_name, arguments)

    async def list_tools(self):
        async with self._run_session() as session:
            return await session.list_tools()