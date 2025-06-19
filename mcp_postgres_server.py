import asyncio
import sys
import os
import json
from typing import Any, Dict, List, Optional
import logging
from concurrent.futures import ThreadPoolExecutor

from mcp.server import Server
from mcp.types import Resource, TextContent, Tool
import mcp.server.stdio

try:
    import asyncpg
except ImportError:
    print("Warning: asyncpg not installed. Install with: pip install asyncpg")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed. Install with: pip install python-dotenv")

class PostgresManager:
    """
    A class to manage the asyncpg connection pool.
    """
    _pool = None

    @classmethod
    async def get_pool(cls) -> asyncpg.Pool:
        """
        Initializes and returns the connection pool using the MCP_POSTGRES_URL.
        """
        if cls._pool is None:
            conn_string = os.getenv('MCP_POSTGRES_URL')
            if not conn_string:
                raise ValueError("MCP_POSTGRES_URL is not set in the environment.")
            cls._pool = await asyncpg.create_pool(conn_string, min_size=1, max_size=10)
            logging.info("PostgreSQL connection pool created successfully.")
        return cls._pool

async def execute_query(query: str, *args):
    """
    Executes a query using the connection pool.
    """
    pool = await PostgresManager.get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(query, *args)

async def execute_query_and_return_dict(query: str, *args):
    """
    Executes a query and returns the result as a list of dictionaries.
    """
    rows = await execute_query(query, *args)
    return [dict(row) for row in rows]


app = Server("postgresql-mcp")


@app.list_tools()
async def handle_list_tools() -> List[Tool]:
    """List available PostgreSQL tools"""
    return [
        Tool(
            name="debug_postgres_env",
            description="Debug PostgreSQL environment variables",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="connect_postgres",
            description="Connect to PostgreSQL database (uses MCP_POSTGRES_URL from env)",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="list_postgres_tables",
            description="List all tables in the connected PostgreSQL database",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="query_postgres_table",
            description="Query data from a specific table",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Name of the table (can include schema like 'public.users')"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum rows to return",
                        "default": 100
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Number of rows to skip",
                        "default": 0
                    }
                },
                "required": ["table_name"]
            }
        ),
        Tool(
            name="execute_postgres_query",
            description="Execute a custom SELECT query",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SQL SELECT query to execute"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_postgres_schema",
            description="Get detailed schema information for a table",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Name of the table (can include schema)"
                    }
                },
                "required": ["table_name"]
            }
        )
    ]

@app.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle PostgreSQL tool calls"""

    if name == "debug_postgres_env":
        url = os.getenv("MCP_POSTGRES_URL")
        if url:
            parts = url.split('@')
            user_pass = parts[0].split('//')[1]
            user = user_pass.split(':')[0]
            masked_url = f"postgresql://{user}:[REDACTED]@{parts[1]}"
            text = f"✅ `MCP_POSTGRES_URL` is set:\n`{masked_url}`"
        else:
            text = "❌ `MCP_POSTGRES_URL` is NOT set in the environment."
        return [TextContent(type="text", text=text)]


    if name == "connect_postgres":
        try:
            version_row = await execute_query('SELECT version()')
            version = version_row[0]['version'] if version_row else "N/A"

            url = os.getenv("MCP_POSTGRES_URL", "")
            masked_url = "Not set"
            if url:
                parts = url.split('@')
                host_part = parts[1] if len(parts) > 1 else ""
            else:
                host_part = "N/A"


            text = f"""✅ **PostgreSQL Connection Successful!**

🔗 **Connected to:** `{host_part}`
📊 **Server Version:** {version}

💡 **Next Steps:**
• Use `list_postgres_tables` to see all tables.
• Use `query_postgres_table` to query specific tables.
• Use `execute_postgres_query` for custom queries."""
        except Exception as e:
            text = f"""❌ **Connection Failed**

**Error:** `{e}`

**Troubleshooting:**
• Check your `MCP_POSTGRES_URL` in the `.env` file.
• Verify your PostgreSQL server is running and accessible.
• Confirm your credentials are correct."""
        return [TextContent(type="text", text=text)]


    if name == "list_postgres_tables":
        try:
            tables = await execute_query_and_return_dict("""
                SELECT
                    schemaname,
                    tablename
                FROM pg_tables
                WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
                ORDER BY schemaname, tablename;
            """)

            if not tables:
                 return [TextContent(type="text", text="No tables found in the public schema.")]

            schema_map = {}
            for table in tables:
                schema = table['schemaname']
                if schema not in schema_map:
                    schema_map[schema] = []
                schema_map[schema].append(table['tablename'])

            text = f"📋 **Found {len(tables)} tables in your database:**\n\n"
            for schema, table_list in schema_map.items():
                text += f"**Schema: `{schema}`**\n"
                text += "\n".join([f"- `{table}`" for table in table_list])
                text += "\n\n"


        except Exception as e:
            text = f"❌ **Failed to list tables**\n\n**Error:** {e}"
        return [TextContent(type="text", text=text)]

    if name == "query_postgres_table":
        try:
            table_name = arguments.get("table_name")
            limit = arguments.get("limit", 10)
            offset = arguments.get("offset", 0)

            if not table_name or not all(c.isalnum() or c in ('.', '_') for c in table_name):
                return [TextContent(type="text", text="Invalid table name.")]

            query = f'SELECT * FROM {table_name} LIMIT $1 OFFSET $2'
            results = await execute_query_and_return_dict(query, limit, offset)

            if not results:
                return [TextContent(type="text", text=f"No results from `{table_name}` or table is empty.")]

            headers = results[0].keys()
            header_line = "| " + " | ".join(headers) + " |"
            separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"
            body_lines = []
            for row in results:
                body_lines.append("| " + " | ".join(str(v) for v in row.values()) + " |")

            text = f"**Query Results for `{table_name}`:**\n\n" + "\n".join([header_line, separator_line] + body_lines)

        except Exception as e:
             text = f"❌ **Failed to query table `{table_name}`**\n\n**Error:** {e}"
        return [TextContent(type="text", text=text)]


    if name == "execute_postgres_query":
        try:
            query = arguments.get("query", "")
            if not query.strip().upper().startswith("SELECT"):
                return [TextContent(type="text", text="❌ **Security Error:** Only `SELECT` statements are allowed.")]

            results = await execute_query_and_return_dict(query)
            if not results:
                return [TextContent(type="text", text="Query executed successfully, but returned no results.")]

            headers = results[0].keys()
            header_line = "| " + " | ".join(headers) + " |"
            separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"
            body_lines = []
            for row in results:
                body_lines.append("| " + " | ".join(str(v) for v in row.values()) + " |")

            text = f"**Custom Query Results:**\n\n" + "\n".join([header_line, separator_line] + body_lines)

        except Exception as e:
            text = f"❌ **Failed to execute query**\n\n**Error:** {e}"
        return [TextContent(type="text", text=text)]

    if name == "get_postgres_schema":
        try:
            table_name = arguments.get("table_name", "")
            schema, table = table_name.split('.') if '.' in table_name else ('public', table_name)

            query = """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = $1 AND table_name = $2
            ORDER BY ordinal_position;
            """
            results = await execute_query_and_return_dict(query, schema, table)

            if not results:
                return [TextContent(type="text", text=f"Could not find schema for table `{table_name}`.")]


            headers = results[0].keys()
            header_line = "| " + " | ".join(headers) + " |"
            separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"
            body_lines = []
            for row in results:
                body_lines.append("| " + " | ".join(str(v) if v is not None else "NULL" for v in row.values()) + " |")

            text = f"**Schema for `{table_name}`:**\n\n" + "\n".join([header_line, separator_line] + body_lines)

        except Exception as e:
            text = f"❌ **Failed to get schema for `{table_name}`**\n\n**Error:** {e}"
        return [TextContent(type="text", text=text)]

    else:
        return [TextContent(type="text", text=f"❌ Unknown tool: {name}")]


@app.list_resources()
async def handle_list_resources() -> List[Resource]:
    """List available PostgreSQL resources"""
    return [
        Resource(
            uri="postgresql://mcp",
            name="PostgreSQL MCP Server",
            description="PostgreSQL database access via MCP"
        )
    ]

async def main():
    """Main entry point for the PostgreSQL MCP server"""
    logging.basicConfig(level=logging.INFO)

    await PostgresManager.get_pool()

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting PostgreSQL MCP server.")
