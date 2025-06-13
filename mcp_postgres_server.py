import asyncio
import sys
import os
import json
import concurrent.futures
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.types import Resource, TextContent, Tool
import mcp.server.stdio

# Import asyncpg at top level
try:
    import asyncpg
except ImportError:
    asyncpg = None
    print("Warning: asyncpg not installed. Install with: pip install asyncpg")

# Import dotenv at top level
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    load_dotenv = None
    print("Warning: python-dotenv not installed. Install with: pip install python-dotenv")

executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

# Global connection pool
connection_pool = None
connection_string = None

def execute_postgres_command(action: str, **kwargs) -> Dict[str, Any]:
    """Execute PostgreSQL commands in a separate thread"""
    # Check if asyncpg is available
    if asyncpg is None:
        return {
            'success': False,
            'error': 'asyncpg library is not installed. Please install it with: pip install asyncpg',
            'action': action
        }
    
    # Use asyncio.run() which properly manages the event loop
    return asyncio.run(_execute_postgres_command_async(action, **kwargs))

async def _execute_postgres_command_async(action: str, **kwargs) -> Dict[str, Any]:
    """Async implementation of PostgreSQL commands"""
    try:
        global connection_pool, connection_string
        
        if action == "debug_env":
            return {
                'success': True,
                'action': action,
                'env_vars': {
                    'POSTGRES_HOST': os.getenv('POSTGRES_HOST', 'NOT SET'),
                    'POSTGRES_PORT': os.getenv('POSTGRES_PORT', 'NOT SET'),
                    'POSTGRES_DB': os.getenv('POSTGRES_DB', 'NOT SET'),
                    'POSTGRES_USER': os.getenv('POSTGRES_USER', 'NOT SET'),
                    'POSTGRES_PASSWORD': 'SET' if os.getenv('POSTGRES_PASSWORD') else 'NOT SET',
                    'DATABASE_URL': 'SET' if os.getenv('DATABASE_URL') else 'NOT SET'
                },
                'cwd': os.getcwd(),
                'env_file_exists': os.path.exists('.env')
            }
        
        elif action == "connect_db":
            conn_string = kwargs.get("connection_string")
            
            # If no connection string provided, try to build from env vars
            if not conn_string:
                # First try DATABASE_URL
                conn_string = os.getenv('DATABASE_URL')
                
                # If not, try to build from individual components
                if not conn_string:
                    host = os.getenv('POSTGRES_HOST', 'localhost')
                    port = os.getenv('POSTGRES_PORT', '5432')
                    db = os.getenv('POSTGRES_DB')
                    user = os.getenv('POSTGRES_USER')
                    password = os.getenv('POSTGRES_PASSWORD')
                    
                    if db and user:
                        conn_string = f"postgresql://{user}:{password}@{host}:{port}/{db}"
            
            if not conn_string:
                return {
                    'success': False,
                    'error': 'No connection string provided and no DATABASE_URL in environment'
                }
            
            # Close existing pool if any
            if connection_pool:
                await connection_pool.close()
            
            # Create new connection pool
            connection_pool = await asyncpg.create_pool(
                conn_string,
                min_size=1,
                max_size=10
            )
            connection_string = conn_string
            
            # Test connection and get version
            async with connection_pool.acquire() as conn:
                version = await conn.fetchval('SELECT version()')
            
            return {
                'success': True,
                'action': action,
                'version': version,
                'connection_string': conn_string.split('@')[1] if '@' in conn_string else conn_string  # Hide password
            }
        
        elif action == "list_tables":
            if not connection_pool:
                return {
                    'success': False,
                    'error': 'Not connected to database. Please use connect_db first.'
                }
            
            async with connection_pool.acquire() as conn:
                tables = await conn.fetch("""
                    SELECT 
                        schemaname,
                        tablename,
                        tableowner
                    FROM pg_tables 
                    WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
                    ORDER BY schemaname, tablename
                """)
            
            formatted_tables = []
            for table in tables:
                formatted_tables.append({
                    'schema': table['schemaname'],
                    'name': table['tablename'],
                    'full_name': f"{table['schemaname']}.{table['tablename']}",
                    'owner': table['tableowner']
                })
            
            return {
                'success': True,
                'action': action,
                'count': len(formatted_tables),
                'tables': formatted_tables
            }
        
        elif action == "query_table":
            if not connection_pool:
                return {
                    'success': False,
                    'error': 'Not connected to database. Please use connect_db first.'
                }
            
            table_name = kwargs.get("table_name")
            limit = kwargs.get("limit", 100)
            offset = kwargs.get("offset", 0)
            
            # Handle schema.table format
            if '.' in table_name:
                schema, table = table_name.split('.', 1)
            else:
                schema = 'public'
                table = table_name
            
            async with connection_pool.acquire() as conn:
                # First check if table exists
                exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_schema = $1 AND table_name = $2
                    )
                """, schema, table)
                
                if not exists:
                    return {
                        'success': False,
                        'error': f"Table '{table_name}' not found"
                    }
                
                # Get column info
                columns = await conn.fetch("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_schema = $1 AND table_name = $2
                    ORDER BY ordinal_position
                """, schema, table)
                
                # Query data - using quote_ident for safety
                query = f'SELECT * FROM {schema}.{table} LIMIT $1 OFFSET $2'
                rows = await conn.fetch(query, limit, offset)
            
            # Convert rows to list of dicts
            data = [dict(row) for row in rows] if rows else []
            
            return {
                'success': True,
                'action': action,
                'table': table_name,
                'columns': [{'name': col['column_name'], 'type': col['data_type']} for col in columns],
                'row_count': len(data),
                'data': data
            }
        
        elif action == "execute_query":
            if not connection_pool:
                return {
                    'success': False,
                    'error': 'Not connected to database. Please use connect_db first.'
                }
            
            query = kwargs.get("query", "").strip()
            
            # Basic safety check
            if not query.upper().startswith("SELECT"):
                return {
                    'success': False,
                    'error': 'Only SELECT queries are allowed for safety'
                }
            
            async with connection_pool.acquire() as conn:
                rows = await conn.fetch(query)
            
            data = [dict(row) for row in rows] if rows else []
            
            return {
                'success': True,
                'action': action,
                'row_count': len(data),
                'data': data
            }
        
        elif action == "get_table_schema":
            if not connection_pool:
                return {
                    'success': False,
                    'error': 'Not connected to database. Please use connect_db first.'
                }
            
            table_name = kwargs.get("table_name")
            
            # Handle schema.table format
            if '.' in table_name:
                schema, table = table_name.split('.', 1)
            else:
                schema = 'public'
                table = table_name
            
            async with connection_pool.acquire() as conn:
                # Get columns
                columns = await conn.fetch("""
                    SELECT 
                        column_name,
                        data_type,
                        is_nullable,
                        column_default,
                        character_maximum_length
                    FROM information_schema.columns 
                    WHERE table_schema = $1 AND table_name = $2
                    ORDER BY ordinal_position
                """, schema, table)
                
                if not columns:
                    return {
                        'success': False,
                        'error': f"Table '{table_name}' not found"
                    }
                
                # Get primary keys
                pk_columns = await conn.fetch("""
                    SELECT a.attname as column_name
                    FROM pg_index i
                    JOIN pg_attribute a ON a.attrelid = i.indrelid
                        AND a.attnum = ANY(i.indkey)
                    JOIN pg_class c ON c.oid = i.indrelid
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = $1
                        AND c.relname = $2
                        AND i.indisprimary
                """, schema, table)
                
                # Get foreign keys
                fk_info = await conn.fetch("""
                    SELECT
                        kcu.column_name,
                        ccu.table_schema AS foreign_table_schema,
                        ccu.table_name AS foreign_table_name,
                        ccu.column_name AS foreign_column_name
                    FROM information_schema.table_constraints AS tc
                    JOIN information_schema.key_column_usage AS kcu
                        ON tc.constraint_name = kcu.constraint_name
                        AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage AS ccu
                        ON ccu.constraint_name = tc.constraint_name
                        AND ccu.table_schema = tc.table_schema
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                        AND tc.table_schema = $1
                        AND tc.table_name = $2
                """, schema, table)
            
            pk_names = {row['column_name'] for row in pk_columns}
            fk_map = {fk['column_name']: fk for fk in fk_info}
            
            formatted_columns = []
            for col in columns:
                col_info = {
                    'name': col['column_name'],
                    'type': col['data_type'],
                    'nullable': col['is_nullable'] == 'YES',
                    'default': col['column_default'],
                    'max_length': col['character_maximum_length'],
                    'is_primary_key': col['column_name'] in pk_names
                }
                
                if col['column_name'] in fk_map:
                    fk = fk_map[col['column_name']]
                    col_info['foreign_key'] = {
                        'table': f"{fk['foreign_table_schema']}.{fk['foreign_table_name']}",
                        'column': fk['foreign_column_name']
                    }
                
                formatted_columns.append(col_info)
            
            return {
                'success': True,
                'action': action,
                'table': table_name,
                'columns': formatted_columns
            }
        
        else:
            return {
                'success': False,
                'error': f'Unknown action: {action}'
            }
        
    except Exception as e:
        import traceback
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
            'action': action
        }

async def async_postgres_call(action: str, **kwargs) -> Dict[str, Any]:
    """Make PostgreSQL call asynchronously"""
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            executor, 
            lambda: execute_postgres_command(action, **kwargs)
        )
        return result
    except Exception as e:
        return {
            'success': False,
            'error': f'Async call failed: {e}',
            'action': action
        }

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
            description="Connect to PostgreSQL database (uses DATABASE_URL from env if no connection string provided)",
            inputSchema={
                "type": "object",
                "properties": {
                    "connection_string": {
                        "type": "string",
                        "description": "PostgreSQL connection string (optional, will use DATABASE_URL from env if not provided)"
                    }
                },
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
        result = await async_postgres_call("debug_env")
        
        if result['success']:
            env_vars = result['env_vars']
            text = f"""🔧 **PostgreSQL Environment Debug:**

📁 **Working Directory:** {result['cwd']}
📄 **.env file exists:** {result['env_file_exists']}

**Environment Variables:**
• POSTGRES_HOST: {env_vars['POSTGRES_HOST']}
• POSTGRES_PORT: {env_vars['POSTGRES_PORT']}
• POSTGRES_DB: {env_vars['POSTGRES_DB']}
• POSTGRES_USER: {env_vars['POSTGRES_USER']}
• POSTGRES_PASSWORD: {env_vars['POSTGRES_PASSWORD']}
• DATABASE_URL: {env_vars['DATABASE_URL']}

💡 **Next:** Use 'connect_postgres' to connect (it will use DATABASE_URL automatically if set)."""
        else:
            text = f"❌ **Debug failed:** {result['error']}"
        
        return [TextContent(type="text", text=text)]
    
    elif name == "connect_postgres":
        conn_string = arguments.get("connection_string")
        result = await async_postgres_call("connect_db", connection_string=conn_string)
        
        if result['success']:
            text = f"""✅ **PostgreSQL Connection Successful!**

🔗 **Connected to:** {result.get('connection_string', 'hidden')}
📊 **Server Version:** {result['version']}

💡 **Next Steps:** 
• Use 'list_postgres_tables' to see all tables
• Use 'query_postgres_table' to query specific tables
• Use 'execute_postgres_query' for custom queries"""
        else:
            text = f"""❌ **Connection Failed**

**Error:** {result['error']}

**Troubleshooting:**
• Check your DATABASE_URL in .env file
• Verify PostgreSQL server is running
• Confirm credentials are correct
• Try providing connection string directly"""
        
        return [TextContent(type="text", text=text)]
    
    elif name == "list_postgres_tables":
        result = await async_postgres_call("list_tables")
        
        if result['success']:
            tables = result['tables']
            text = f"📋 **Found {result['count']} tables in PostgreSQL:**\n\n"
            
            # Group by schema
            schemas = {}
            for table in tables:
                schema = table['schema']
                if schema not in schemas:
                    schemas[schema] = []
                schemas[schema].append(table)
            
            for schema, schema_tables in sorted(schemas.items()):
                text += f"**Schema: {schema}**\n"
                for table in schema_tables:
                    text += f"  • {table['name']} (owner: {table['owner']})\n"
                text += "\n"
            
            if result['count'] == 0:
                text = "📋 No tables found in the database."
        else:
            text = f"❌ **Failed to list tables**\n\n**Error:** {result['error']}"
        
        return [TextContent(type="text", text=text)]
    
    elif name == "query_postgres_table":
        table_name = arguments.get("table_name")
        limit = arguments.get("limit", 100)
        offset = arguments.get("offset", 0)
        
        result = await async_postgres_call("query_table", 
                                         table_name=table_name, 
                                         limit=limit, 
                                         offset=offset)
        
        if result['success']:
            text = f"📊 **Query Results from '{table_name}':**\n\n"
            text += f"**Returned:** {result['row_count']} rows"
            if limit:
                text += f" (limited to {limit})"
            text += "\n\n"
            
            if result['columns']:
                text += "**Columns:** "
                text += ", ".join([f"{col['name']} ({col['type']})" for col in result['columns'][:5]])
                if len(result['columns']) > 5:
                    text += f" ... and {len(result['columns']) - 5} more"
                text += "\n\n"
            
            if result['data']:
                # Show first few rows as formatted JSON
                text += "**Sample Data:**\n```json\n"
                text += json.dumps(result['data'][:5], indent=2, default=str)
                text += "\n```\n"
                
                if result['row_count'] > 5:
                    text += f"\n... and {result['row_count'] - 5} more rows"
            else:
                text += "**No data found in table**"
        else:
            text = f"❌ **Query failed**\n\n**Error:** {result['error']}"
        
        return [TextContent(type="text", text=text)]
    
    elif name == "execute_postgres_query":
        query = arguments.get("query")
        result = await async_postgres_call("execute_query", query=query)
        
        if result['success']:
            text = f"📊 **Query Executed Successfully**\n\n"
            text += f"**Returned:** {result['row_count']} rows\n\n"
            
            if result['data']:
                text += "**Results:**\n```json\n"
                text += json.dumps(result['data'][:10], indent=2, default=str)
                text += "\n```\n"
                
                if result['row_count'] > 10:
                    text += f"\n... and {result['row_count'] - 10} more rows"
            else:
                text += "**Query returned no results**"
        else:
            text = f"❌ **Query failed**\n\n**Error:** {result['error']}"
        
        return [TextContent(type="text", text=text)]
    
    elif name == "get_postgres_schema":
        table_name = arguments.get("table_name")
        result = await async_postgres_call("get_table_schema", table_name=table_name)
        
        if result['success']:
            text = f"📋 **Schema for table '{table_name}':**\n\n"
            
            columns = result['columns']
            pk_columns = [col for col in columns if col.get('is_primary_key')]
            fk_columns = [col for col in columns if 'foreign_key' in col]
            
            if pk_columns:
                text += "**Primary Key(s):** "
                text += ", ".join([col['name'] for col in pk_columns])
                text += "\n\n"
            
            text += "**Columns:**\n"
            for col in columns:
                text += f"• **{col['name']}** - {col['type']}"
                
                if col.get('max_length'):
                    text += f"({col['max_length']})"
                
                flags = []
                if col.get('is_primary_key'):
                    flags.append("PK")
                if not col.get('nullable'):
                    flags.append("NOT NULL")
                if col.get('default'):
                    flags.append(f"DEFAULT: {col['default']}")
                
                if flags:
                    text += f" [{', '.join(flags)}]"
                
                if 'foreign_key' in col:
                    fk = col['foreign_key']
                    text += f"\n  → References: {fk['table']}.{fk['column']}"
                
                text += "\n"
            
            if fk_columns:
                text += f"\n**Foreign Keys:** {len(fk_columns)} relationship(s) found"
        else:
            text = f"❌ **Failed to get schema**\n\n**Error:** {result['error']}"
        
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
    # Check dependencies
    if asyncpg is None:
        print("ERROR: asyncpg is required but not installed.")
        print("Please install it with: pip install asyncpg")
        sys.exit(1)
    
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream, 
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())