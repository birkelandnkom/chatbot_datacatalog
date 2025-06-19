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

SYSTEM_PROMPT = """Du er en spesialisert data-assistent for et internt bedriftsverktøy i Nasjonal kommunikasjonsmyndighet. DITT ENESTE FORMÅL er å svare på spørsmål om data ved hjelp av de tilgjengelige verktøyene.

Dine operasjonelle regler er:
1.  **Analyser og bruk Verktøy**: Når du mottar en forespørsel, er din første og eneste handling å avgjøre om et av verktøyene dine kan svare på den. Hvis et verktøy er relevant, MÅ du bruke det.
2.  **Håndter tvetydighet**: Hvis en brukers forespørsel er tvetydig, men virker relatert til ditt formål (f.eks. "vis meg dataene"), må du stille et oppklarende spørsmål for å hjelpe deg med å bruke riktig verktøy (f.eks. "Hvilken tabell er du interessert i?").
3.  **Svar på oppfølgingsspørsmål**: Du kan svare på oppfølgingsspørsmål om data du allerede har hentet, eller om kapasiteten til verktøyene dine (f.eks. "Kan du forklare det forrige resultatet?" eller "Hvilke verktøy har du?"). Bruk samtalehistorikken for å forstå konteksten.
4.  **Avvis spørsmål utenfor omfang**: Hvis en bruker stiller et spørsmål som helt klart ikke er relatert til ditt datahentingsformål (f.eks. "Hva er hovedstaden i Frankrike?" eller "Skriv et dikt til meg"), MÅ du svare med en av følgende setninger og ingenting annet:
    - "Jeg kan kun svare på spørsmål relatert til våre data. Vennligst still et spørsmål jeg kan svare på med verktøyene mine."
    - "Mitt formål er å assistere med dataforespørsler. Jeg kan ikke hjelpe med den forespørselen."
5.  **Vær konsis**: Ikke legg til unødvendig prat. Vær direkte og hjelpsom.
"""

@cl.on_chat_start
async def start_chat():
    """
    Initializes a new chat session.

    This function sets up the conversation history with a system prompt and
    validates that all required Azure OpenAI credentials are set in the
    environment.
    """
    print("Chat session starting...")
    
    cl.user_session.set("history", [{"role": "system", "content": SYSTEM_PROMPT}])

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
    """
    Handles a new MCP server connection.

    Fetches the list of available tools from the connected server, stores them
    in the global and user session state, and notifies the user.

    Args:
        connection: The MCP connection object provided by Chainlit.
        session: The active ClientSession for the connection.
    """
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
    """
    Handles an MCP server disconnection.

    Cleans up the disconnected server's tools and session from the global
    and user session state and notifies the user.

    Args:
        connection: The MCP connection object that was disconnected.
    """
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
    """
    Finds which MCP connection provides a specific tool.

    Args:
        tool_name: The name of the tool to find.

    Returns:
        The name of the MCP connection that provides the tool, or None if not found.
    """
    for mcp_name, tools in mcp_tools.items():
        for tool in tools:
            if tool["name"] == tool_name:
                return mcp_name
    return None

@cl.step(type="tool")
async def call_mcp_tool(tool_name: str, tool_input: dict):
    """
    Executes a specific tool on its corresponding MCP server.

    Args:
        tool_name: The name of the tool to execute.
        tool_input: The dictionary of arguments for the tool.

    Returns:
        A string containing the tool's output.

    Raises:
        ValueError: If no MCP connection is found for the tool or session.
    """
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
        return result.content[0].text if result.content else "Tool executed, but returned no content."
    except Exception as e:
        print(f"Error executing tool {tool_name}: {e}")
        raise

@cl.on_message
async def main(message: cl.Message):
    """
    Main message handler for the chatbot.

    This function receives a user message, prepares the context and available
    tools, calls the Azure OpenAI model, and then handles the model's response,
    which may include executing tool calls.
    
    Args:
        message: The user's incoming message object.
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
            
            tool_outputs = []
            for tool_call in response_message.tool_calls:
                tool_name = tool_call.function.name
                tool_input = json.loads(tool_call.function.arguments)
                
                print(f"   - Executing tool: {tool_name}")
                
                try:
                    tool_output = await call_mcp_tool(tool_name, tool_input)
                    tool_outputs.append({
                        "tool_call_id": tool_call.id,
                        "output": tool_output
                    })
                    
                except Exception as e:
                    print(f"Tool execution failed: {e}")
                    tool_outputs.append({
                        "tool_call_id": tool_call.id,
                        "output": f"Error executing tool: {str(e)}"
                    })
            
            # Om vi bruker en indirekte måte å oppsummere på får vi mer
            # konversasjonell chatbot - men den sliter med å formatere markdown
            # En direkte respons fra verktøyet er bedre til dette - men mindre konversasjonell
            # E.g. om den returnerer en tabell med 2000 rader vil den vise dette direkte i UI....

            # TODO: Forbedre den indirekte metoden til å bedre formatere responsen fra verktøyene
            # slik at den både kan vise markdown og ikke bare lage plaintext...

            # --- Direkte: Ikke oppsummer ---

            for tool_output_data in tool_outputs:
                await cl.Message(author=tool_name, content=tool_output_data["output"]).send()
                history.append({
                    "role": "tool",
                    "tool_call_id": tool_output_data["tool_call_id"],
                    "content": tool_output_data["output"]
                })
            
            # --- Indirekte: Lar AIen oppsummere (mer konversasjonell) ---
            # Dette sender tool-responsen tilbake til LLMen for en oppsummering
            
            # for tool_output_data in tool_outputs:
            #     history.append({
            #         "role": "tool",
            #         "tool_call_id": tool_output_data["tool_call_id"],
            #         "content": tool_output_data["output"]
            #     })

            # final_response = await client.chat.completions.create(
            #     messages=history,
            #     model=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME"),
            # )
            
            # final_message = final_response.choices[0].message
            # history.append(final_message.model_dump())
            # await cl.Message(content=final_message.content).send()            
        else:
            print("No tool calls in response")
            history.append(response_message.model_dump())
            await cl.Message(content=response_message.content).send()

    except Exception as e:
        error_details = traceback.format_exc()
        print(f"Full error details: {error_details}")
        await cl.Message(content=f"An error occurred: {str(e)}\n\nFull error: {error_details}").send()
