from contextlib import asynccontextmanager
from contextlib import AsyncExitStack
from typing import Optional, List, Dict
from urllib.parse import urlparse
import anyio

from mcp.client.mqtt import MqttTransportClient, MqttOptions

class MQTTMCPClient():

    def __init__(
        self,
        uri: str,
        client_desc: str,
        server_name_filter: str,
        max_servers_to_discover: int,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: int = 30,
    ):
        parse_uri = urlparse(uri)
        self.host = parse_uri.hostname
        self.port = parse_uri.port
        self.client_desc = client_desc
        self.server_name_filter = server_name_filter
        self.max_servers_to_discover = max_servers_to_discover
        send_stream, receive_stream = anyio.create_memory_object_stream()
        self.server_discover_finish_snd = send_stream
        self.server_discover_finish_rcv = receive_stream
        self.mcp_servers = []
        self.args = args or []
        self.env = env or {}
        self.timeout = timeout
        self.exit_stack: AsyncExitStack = AsyncExitStack()

    async def connect(self):
        mqtt_client = await self.exit_stack.enter_async_context(
            MqttTransportClient(
                self.client_desc,
                server_name_filter = self.server_name_filter,
                auto_connect_to_mcp_server = True,
                on_mcp_server_discovered = self.on_mcp_server_discovered,
                on_mcp_connect = self.on_mcp_connect,
                mqtt_options = MqttOptions(
                    host = self.host,
                    port = self.port,
                )
            )
        )
        mqtt_client.start()
        self.mqtt_client = mqtt_client
        async with self.server_discover_finish_rcv:
            async for item in self.server_discover_finish_rcv:
                if item == 'discovery_finished':
                    break
        for server in self.mcp_servers:
            if not server['success']:
                print(f"Failed to initalize with MCP server: {server['server_name']}")
            print(f"Initalized with MCP/MQTT server: {server['server_name']}")
        return [mqtt_client.get_session(server['server_name']) for server in self.mcp_servers if server['success']]

    async def on_mcp_server_discovered(self, client, server_name):
        print(f"Discovered {server_name}, connecting ...")
        await client.initialize_mcp_server(server_name)

    async def on_mcp_connect(self, client, server_name, connect_result):
        success, _init_result = connect_result
        self.mcp_servers.append({'server_name': server_name, 'success': success})

        print(f"Server Names now: {self.mcp_servers}")
        if len(self.mcp_servers) >= self.max_servers_to_discover:
            ## We stop the discovery if we have got at least 2 MCP/MQTT servers
            print(f"Now that got {self.max_servers_to_discover} MCP/MQTT servers, stop discovery.")
            await self.server_discover_finish_snd.send('discovery_finished')
