from contextlib import AsyncExitStack
import os
import sys
import time
import anyio
from typing import Any, Union, Tuple
import logging
import threading
import traceback
from dotenv import load_dotenv
from urllib.parse import urlparse
from mcp.client.mqtt import MqttTransportClient, MqttOptions
from mcp.shared.mqtt import configure_logging

from llama_index.core.workflow import (
    Event,
    StartEvent,
    StopEvent,
    Workflow,
    step,
    Context,
)
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.llms import ChatMessage, MessageRole 
from llama_index.core.agent.workflow import (AgentWorkflow, AgentStream, ToolCallResult)
from llama_index.llms.openai_like import OpenAILike
from llama_index.llms.siliconflow import SiliconFlow
from llama_index.tools.mcp import BasicMCPClient, McpToolSpec

from util import load_system_prompt,load_json_prompt

configure_logging(level="INFO")
logger = logging.getLogger(__name__)

load_dotenv()

def cprint(text: str, end: str = "", flush: bool = True):
    WORKFLOW_COLOR = '\033[36m'
    RESET = '\033[0m'
    print(f"{WORKFLOW_COLOR}{text}{RESET}", end=end, flush=flush)

class ProgressEvent(Event):
    msg: str

class ReportEvent(Event):
    msg: str

class DriverBehaviorFlow(Workflow):
    def __init__(
            self,
            llm: OpenAILike,
            memory: ChatMemoryBuffer = None,
            *args,
            **kwargs):
        if memory is None:
            memory = ChatMemoryBuffer(token_limit=64000)
        self.memory = memory
        self.client = None
        self.llm = llm
        send_stream, receive_stream = anyio.create_memory_object_stream()
        self.server_discover_finish_snd = send_stream
        self.server_discover_finish_rcv = receive_stream
        self.mcp_servers = []
        self.exit_stack: AsyncExitStack = AsyncExitStack()
        super().__init__(*args, **kwargs)

    @step
    async def process_input(self, ctx: Context, ev: StartEvent) -> Union[ReportEvent]:
        self.all_tools = await self.init_mcp_server()
        tools_name = [tool.metadata.name for tool in self.all_tools]
        # # Add event showing available tools
        ctx.write_event_to_stream(ProgressEvent(msg=f"Available tools: {tools_name}\n\n"))

        system_prompt=load_system_prompt(prompt_filename="system.txt", lang="zh").format(ev=ev)
        self.memory.put(ChatMessage(role=MessageRole.SYSTEM,content=system_prompt))
        
        query_info = AgentWorkflow.from_tools_or_functions(
            tools_or_functions=self.all_tools,
            llm=self.llm,
            system_prompt=system_prompt,
            verbose=False,
            timeout=180,
            )
        
        json_prompts = load_json_prompt("data_analysis.json", "zh")
        user_prompt = json_prompts["enrich_data"].format(ev=ev)
        self.memory.put(ChatMessage(role=MessageRole.USER,content=user_prompt))

        handler = query_info.run(user_msg=f'{user_prompt}. \n\n')

        response = ""
        async for event in handler.stream_events():
            if isinstance(event, AgentStream):
                cprint(event.delta, end="", flush=True)
                # ctx.write_event_to_stream(ProgressEvent(msg=event.delta))
                response += event.delta
            elif isinstance(event, ToolCallResult):
                ctx.write_event_to_stream(ProgressEvent(msg=f'{event.tool_name}: {event.tool_kwargs}\n\n'))
                ctx.write_event_to_stream(ProgressEvent(msg=f'{event.tool_output}\n'))

        self.memory.put(ChatMessage(role=MessageRole.ASSISTANT,content=response))
        return ReportEvent(msg=response)

    @step
    async def gen_report(self, ctx: Context, ev: ReportEvent) -> Union[StopEvent]:
        user_prompt = load_json_prompt("data_analysis.json", "zh")["gen_report"]
        self.memory.put(ChatMessage(role=MessageRole.USER, content=user_prompt))
        chat_history = self.memory.get()

        response = ""
        handle = await self.llm.astream_chat(chat_history)
        async for token in handle:
            # cprint(token.delta)
            ctx.write_event_to_stream(ProgressEvent(msg=token.delta))
            response += token.delta
        return StopEvent(result=response)

    async def on_mcp_server_discovered(self, client, server_name):
        logger.info(f"Discovered {server_name}, connecting ...")
        await client.initialize_mcp_server(server_name)

    async def on_mcp_connect(self, client, server_name, connect_result):
        success, _init_result = connect_result
        self.mcp_servers.append({'server_name': server_name, 'success': success})
        print(f"Server Names now: {self.mcp_servers}")
        if len(self.mcp_servers) >= 2:
            ## We stop the discovery if we have got at least 2 MCP/MQTT servers
            logger.info("Now that got 2 MCP/MQTT servers, stop discovery.")
            await self.server_discover_finish_snd.send('discovery_finished')

    async def init_mcp_server(self):
        servers = [ 
            {"command_or_url":f"mqtt://{os.getenv('MQTT_BROKER', 'localhost')}:1883", "args":[]},
            {"command_or_url":f'https://mcp.amap.com/sse?key={os.getenv("GAODE_KEY")}', "args":[]},
        ]
        all_tools = []
        for server in servers:
            command_or_url = server["command_or_url"]
            if command_or_url.startswith("mqtt"):
                ParsedUrl = urlparse(command_or_url)
                hostname = ParsedUrl.hostname
                port = ParsedUrl.port
                mqtt_client = await self.exit_stack.enter_async_context(
                    MqttTransportClient(
                        "test_client",
                        server_name_filter = 'sdv/#',
                        auto_connect_to_mcp_server = True,
                        on_mcp_server_discovered = self.on_mcp_server_discovered,
                        on_mcp_connect = self.on_mcp_connect,
                        mqtt_options = MqttOptions(
                            host = hostname,
                            port = port,
                        )
                    )
                )
                mqtt_client.start()
                async with self.server_discover_finish_rcv:
                    async for item in self.server_discover_finish_rcv:
                        if item == 'discovery_finished':
                            break
                for server in self.mcp_servers:
                    if not server['success']:
                        logger.error(f"Failed to initalize with MCP server: {server['server_name']}")
                        sys.exit(1)
                    logger.info(f"Initalized with MCP/MQTT server: {server['server_name']}")
                    mcp_client = mqtt_client.get_session(server['server_name'])
                    if mcp_client is None:
                        logger.error(f"Failed to get session for {server['server_name']}")
                        sys.exit(1)
                    mcp_tool = McpToolSpec(client=mcp_client)
                    tools = await mcp_tool.to_tool_list_async()
                    all_tools.extend(tools)
            else:
                mcp_client = BasicMCPClient(
                    command_or_url = command_or_url,
                    args = server["args"]
                )
                mcp_tool = McpToolSpec(client=mcp_client)
                tools = await mcp_tool.to_tool_list_async()
                all_tools.extend(tools)
        return all_tools

async def main():
    try:
        llm = SiliconFlow(api_key=os.getenv("SFAPI_KEY"),model=os.getenv("MODEL_NAME"),temperature=0.2,max_tokens=4000, timeout=180)
        w = DriverBehaviorFlow(timeout=None, llm=llm, verbose=True)
        ctx = Context(w)

        user_prompt = '''生成车辆编号为 00001 的驾驶行为报告'''
        handler = w.run(user_input=user_prompt, ctx=ctx)

        async for ev in handler.stream_events():
            if isinstance(ev, ProgressEvent):
               cprint(ev.msg)
        await handler
    except Exception as e:
        cprint(f"An error occurred: {str(e)}\n")
        cprint("Full stack trace:\n")
        cprint(traceback.format_exc())
        raise

if __name__ == "__main__":
    anyio.run(main)