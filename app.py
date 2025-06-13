import chainlit as cl
import os
from openai import AsyncAzureOpenAI
from dotenv import load_dotenv
import traceback
import json
from mcp import ClientSession

load_dotenv()

mcp_tools = {}
mcp_sessions = {}

@cl.on_chat_start
async def start_chat():
    """
    Initializes the chat session, checks for Azure credentials,
    and prepares the conversation history.
    """
    print("Chat session starting...")
    
    cl.user_session.set("history", [])

    required_vars = ["AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_DEPLOYMENT_NAME"]
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        await cl.Message(
            content=f"**Error:** Missing Azure OpenAI environment variables: {', '.join(missing_vars)}. Please ensure they are in your `.env` file."
        ).send()
        return

    print(f"Azure OpenAI Endpoint: {os.environ.get('AZURE_OPENAI_ENDPOINT')}")
    print(f"Deployment Name: {os.environ.get('AZURE_OPENAI_DEPLOYMENT_NAME')}")
    print(f"API Version: {os.environ.get('AZURE_OPENAI_API_VERSION', '2024-02-01')}")

    await cl.Message(
        content="""Hello!"""
    ).send()

@cl.on_mcp_connect
async def on_mcp_connect(connection, session: ClientSession):
    """Handle MCP server connection"""
    print(f"MCP connection established: {connection.name}")
    
    try:
        result = await session.list_tools()
        print(f"Found {len(result.tools)} tools from {connection.name}")
        
        tools = []
        for tool in result.tools:
            tool_info = {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema,
            }
            tools.append(tool_info)
            print(f"   - {tool.name}: {tool.description}")
        
        mcp_tools[connection.name] = tools
        mcp_sessions[connection.name] = session
        
        user_mcp_tools = cl.user_session.get("mcp_tools", {})
        user_mcp_tools[connection.name] = tools
        cl.user_session.set("mcp_tools", user_mcp_tools)
        
        await cl.Message(
            content=f"Successfully connected to **{connection.name}** MCP server!\n\nAvailable tools:\n" + 
                   "\n".join([f"• **{tool['name']}**: {tool['description']}" for tool in tools])
        ).send()
        
    except Exception as e:
        print(f"Error connecting to MCP server {connection.name}: {e}")
        await cl.Message(
            content=f"Error connecting to MCP server {connection.name}: {str(e)}"
        ).send()

@cl.on_mcp_disconnect
async def on_mcp_disconnect(connection):
    """Handle MCP server disconnection"""
    print(f"MCP connection closed: {connection.name}")
    
    if connection.name in mcp_tools:
        del mcp_tools[connection.name]
    if connection.name in mcp_sessions:
        del mcp_sessions[connection.name]
    
    user_mcp_tools = cl.user_session.get("mcp_tools", {})
    if connection.name in user_mcp_tools:
        del user_mcp_tools[connection.name]
    cl.user_session.set("mcp_tools", user_mcp_tools)
    
    await cl.Message(
        content=f"Disconnected from **{connection.name}** MCP server."
    ).send()

def find_mcp_for_tool(tool_name: str) -> str:
    """Find which MCP connection provides a specific tool"""
    for mcp_name, tools in mcp_tools.items():
        for tool in tools:
            if tool["name"] == tool_name:
                return mcp_name
    return None

@cl.step(type="tool")
async def call_mcp_tool(tool_name: str, tool_input: dict):
    """Execute an MCP tool"""
    print(f"Calling MCP tool: {tool_name} with input: {tool_input}")
    
    mcp_name = find_mcp_for_tool(tool_name)
    if not mcp_name:
        raise ValueError(f"No MCP connection found for tool: {tool_name}")
    
    session = mcp_sessions.get(mcp_name)
    if not session:
        raise ValueError(f"No active session for MCP connection: {mcp_name}")
    
    try:
        result = await session.call_tool(tool_name, tool_input)
        print(f"Tool {tool_name} executed successfully")
        return result
    except Exception as e:
        print(f"Error executing tool {tool_name}: {e}")
        raise

@cl.on_message
async def main(message: cl.Message):
    """
    Handles incoming messages, calls the Azure OpenAI LLM with MCP tools available.
    """
    history = cl.user_session.get("history")
    history.append({"role": "user", "content": message.content})

    try:
        client = AsyncAzureOpenAI(
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01"),
        )

        print(f"Making request to Azure OpenAI with {len(history)} messages")
        print(f"Message content: {message.content}")
        
        openai_tools = []
        user_mcp_tools = cl.user_session.get("mcp_tools", {})
        
        for mcp_name, tools in user_mcp_tools.items():
            for tool in tools:
                openai_tool = {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool["input_schema"]
                    }
                }
                openai_tools.append(openai_tool)
        
        print(f"Available tools: {len(openai_tools)}")
        for tool in openai_tools:
            print(f"   - {tool['function']['name']}")
        
        request_params = {
            "messages": history,
            "model": os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME"),
        }
        
        if openai_tools:
            request_params["tools"] = openai_tools
            request_params["tool_choice"] = "auto"
        
        response = await client.chat.completions.create(**request_params)

        print(f"Received response from Azure OpenAI")
        response_message = response.choices[0].message
        
        if hasattr(response_message, 'tool_calls') and response_message.tool_calls:
            print(f"Tool calls detected: {len(response_message.tool_calls)}")
            
            history.append(response_message.model_dump())
            
            for tool_call in response_message.tool_calls:
                tool_name = tool_call.function.name
                tool_input = json.loads(tool_call.function.arguments)
                
                print(f"   - Executing tool: {tool_name}")
                
                try:
                    tool_result = await call_mcp_tool(tool_name, tool_input)
                    
                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(tool_result.content[0].text if tool_result.content else "Tool executed successfully")
                    })
                    
                except Exception as e:
                    print(f"Tool execution failed: {e}")
                    history.append({
                        "role": "tool", 
                        "tool_call_id": tool_call.id,
                        "content": f"Error executing tool: {str(e)}"
                    })
            
            final_response = await client.chat.completions.create(
                messages=history,
                model=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME"),
            )
            
            final_message = final_response.choices[0].message
            history.append(final_message.model_dump())
            
            await cl.Message(content=final_message.content).send()
            
        else:
            print("No tool calls in response")
            history.append(response_message.model_dump())
            await cl.Message(content=response_message.content).send()

    except Exception as e:
        error_details = traceback.format_exc()
        print(f"Full error details: {error_details}")
        await cl.Message(content=f"An error occurred: {str(e)}\n\nFull error: {error_details}").send()