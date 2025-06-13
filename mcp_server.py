import asyncio
import sys
import os
import json
import concurrent.futures
from typing import Any, Dict, List

from mcp.server import Server
from mcp.types import Resource, TextContent, Tool
import mcp.server.stdio

# Global executor for OpenMetadata calls
executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

def load_and_call_openmetadata(action: str, **kwargs) -> Dict[str, Any]:
    """Load OpenMetadata in a separate thread and make the call"""
    try:
        # Import everything we need at the top
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        
        # Add current directory to path for imports
        current_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, current_dir)
        
        from mcp_modules.openmetadata.src.config import Config
        from mcp_modules.openmetadata.src.openmetadata import OpenMetadataClient
        
        # Handle debug_env action first (before creating client)
        if action == "debug_env":
            return {
                'success': True,
                'action': action,
                'env_vars': {
                    'OPENMETADATA_HOST': os.getenv('OPENMETADATA_HOST', 'NOT SET'),
                    'OPENMETADATA_JWT_TOKEN': 'SET' if os.getenv('OPENMETADATA_JWT_TOKEN') else 'NOT SET',
                    'OPENMETADATA_USERNAME': os.getenv('OPENMETADATA_USERNAME', 'NOT SET'),
                    'OPENMETADATA_PASSWORD': 'SET' if os.getenv('OPENMETADATA_PASSWORD') else 'NOT SET'
                },
                'cwd': os.getcwd(),
                'env_file_exists': os.path.exists('.env')
            }
        
        # For other actions, create the client
        config = Config.from_env()
        client = OpenMetadataClient(
            host=config.OPENMETADATA_HOST,
            api_token=config.OPENMETADATA_JWT_TOKEN,
            username=config.OPENMETADATA_USERNAME,
            password=config.OPENMETADATA_PASSWORD,
        )
        
        # Execute the requested action
        if action == "list_tables":
            limit = kwargs.get("limit", 10)
            result = client.list_tables(limit=limit)
            
            # Format the response
            if isinstance(result, dict) and 'data' in result:
                tables = result['data']
                formatted_tables = []
                
                for table in tables:
                    # Clean up description
                    desc = table.get('description', 'No description')
                    if desc.startswith('<p>'):
                        import re
                        desc = re.sub(r'<[^>]+>', '', desc).strip()
                    if len(desc) > 100:
                        desc = desc[:100] + "..."
                    
                    formatted_tables.append({
                        'name': table.get('name', 'Unknown'),
                        'fqn': table.get('fullyQualifiedName', 'Unknown'),
                        'description': desc,
                        'id': table.get('id', 'Unknown')
                    })
                
                return {
                    'success': True,
                    'action': action,
                    'count': len(formatted_tables),
                    'tables': formatted_tables
                }
            else:
                return {
                    'success': False,
                    'error': f'Unexpected response format: {type(result)}',
                    'raw_data': str(result)[:200]
                }
        
        elif action == "get_table":
            table_name = kwargs.get("table_name")
            
            # Try different methods to get the table
            table_data = None
            method_used = None
            attempts = []
            
            try:
                # First try with the exact name provided
                table_data = client.get_table_by_name(table_name)
                method_used = "get_table_by_name (exact)"
                attempts.append("get_table_by_name - success")
            except Exception as e1:
                attempts.append(f"get_table_by_name - failed: {str(e1)[:50]}")
                
                try:
                    # If that fails, try with the full qualified name format
                    if '.' not in table_name:
                        # Try common FQN patterns
                        fqn_attempts = [
                            f"fivedigit.ekom24.public.{table_name}",
                            f"public.{table_name}",
                            f"ekom24.public.{table_name}"
                        ]
                        
                        for fqn in fqn_attempts:
                            try:
                                table_data = client.get_table_by_name(fqn)
                                method_used = f"get_table_by_name (FQN: {fqn})"
                                attempts.append(f"FQN {fqn} - success")
                                break
                            except Exception as e2:
                                attempts.append(f"FQN {fqn} - failed")
                                continue
                    
                    # If FQN attempts failed, try get_table with ID
                    if not table_data:
                        table_data = client.get_table(table_name)
                        method_used = "get_table (ID)"
                        attempts.append("get_table by ID - success")
                        
                except Exception as e3:
                    attempts.append(f"get_table by ID - failed: {str(e3)[:50]}")
                    return {
                        'success': False,
                        'error': f'Could not find table with any method. Last error: {e3}',
                        'table_name': table_name,
                        'attempts': attempts
                    }
            
            if table_data:
                # Clean description
                desc = table_data.get('description', 'No description')
                if desc.startswith('<p>'):
                    import re
                    desc = re.sub(r'<[^>]+>', '', desc).strip()
                
                # Extract columns if available
                columns = []
                if 'columns' in table_data:
                    for col in table_data['columns'][:10]:  # First 10 columns
                        columns.append({
                            'name': col.get('name', 'Unknown'),
                            'type': col.get('dataType', 'Unknown'),
                            'description': col.get('description', '')
                        })
                
                return {
                    'success': True,
                    'action': action,
                    'method_used': method_used,
                    'attempts': attempts,
                    'table': {
                        'name': table_data.get('name', 'Unknown'),
                        'fqn': table_data.get('fullyQualifiedName', 'Unknown'),
                        'description': desc,
                        'id': table_data.get('id', 'Unknown'),
                        'columns': columns,
                        'column_count': len(table_data.get('columns', []))
                    }
                }
            else:
                return {
                    'success': False,
                    'error': 'No data returned',
                    'table_name': table_name,
                    'method_used': method_used,
                    'attempts': attempts
                }
        
        elif action == "test_connection":
            # Simple connection test
            return {
                'success': True,
                'action': action,
                'host': config.OPENMETADATA_HOST,
                'client_methods': len([m for m in dir(client) if not m.startswith('_')])
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

async def async_openmetadata_call(action: str, **kwargs) -> Dict[str, Any]:
    """Make OpenMetadata call asynchronously"""
    loop = asyncio.get_event_loop()
    try:
        # Run in thread pool to avoid blocking - fix the argument passing
        result = await loop.run_in_executor(
            executor, 
            lambda: load_and_call_openmetadata(action, **kwargs)
        )
        return result
    except Exception as e:
        return {
            'success': False,
            'error': f'Async call failed: {e}',
            'action': action
        }

# Create server using the EXACT working pattern
app = Server("fixed-hybrid-openmetadata")

@app.list_tools()
async def handle_list_tools() -> List[Tool]:
    """List available tools - exact same as working server"""
    return [
        Tool(
            name="debug_env",
            description="Debug environment variables for OpenMetadata",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="test_om_connection",
            description="Test OpenMetadata connection (fast)",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="list_om_tables",
            description="List tables from OpenMetadata catalog",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of tables to return",
                        "default": 10
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_om_table",
            description="Get detailed information about a specific table",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Name of the table (e.g., 'ekomdata')"
                    }
                },
                "required": ["table_name"]
            }
        )
    ]

@app.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls - exact same pattern as working server"""
    
    if name == "debug_env":
        result = await async_openmetadata_call("debug_env")
        
        if result['success']:
            env_vars = result['env_vars']
            text = f"""🔍 **Environment Debug Information:**

📁 **Working Directory:** {result['cwd']}
📄 **.env file exists:** {result['env_file_exists']}

🔧 **Environment Variables:**
• OPENMETADATA_HOST: {env_vars['OPENMETADATA_HOST']}
• OPENMETADATA_JWT_TOKEN: {env_vars['OPENMETADATA_JWT_TOKEN']}
• OPENMETADATA_USERNAME: {env_vars['OPENMETADATA_USERNAME']}
• OPENMETADATA_PASSWORD: {env_vars['OPENMETADATA_PASSWORD']}

💡 **Next:** If host is still 'NOT SET', check your .env file path and format."""
        else:
            text = f"❌ **Debug failed:** {result['error']}"
        
        return [TextContent(type="text", text=text)]
    
    elif name == "test_om_connection":
        result = await async_openmetadata_call("test_connection")
        
        if result['success']:
            text = f"""✅ **OpenMetadata Connection Test Successful!**

🔗 **Host:** {result['host']}
🔧 **Client Methods:** {result['client_methods']}
⚡ **Status:** Ready to use

🎯 **Next Steps:** Try 'list_om_tables' to see your catalog!"""
        else:
            text = f"""❌ **Connection Test Failed**

**Error:** {result['error']}

**Troubleshooting:**
• Check your .env file configuration
• Verify OpenMetadata server is accessible
• Confirm JWT token is valid"""
        
        return [TextContent(type="text", text=text)]
    
    elif name == "list_om_tables":
        limit = arguments.get("limit", 10)
        result = await async_openmetadata_call("list_tables", limit=limit)
        
        if result['success']:
            tables = result['tables']
            text = f"📋 **Found {result['count']} tables in your OpenMetadata catalog:**\n\n"
            
            for table in tables:
                text += f"🔷 **{table['name']}**\n"
                text += f"   📍 Full path: `{table['fqn']}`\n"
                text += f"   📝 Description: {table['description']}\n"
                text += f"   🆔 ID: `{table['id'][:8]}...`\n\n"
            
            if result['count'] == 0:
                text = "📋 No tables found in your OpenMetadata catalog."
        else:
            text = f"❌ **Failed to list tables**\n\n**Error:** {result['error']}"
            if 'raw_data' in result:
                text += f"\n\n**Raw Response:** {result['raw_data']}"
        
        return [TextContent(type="text", text=text)]
    
    elif name == "get_om_table":
        table_name = arguments.get("table_name")
        result = await async_openmetadata_call("get_table", table_name=table_name)
        
        if result['success']:
            table = result['table']
            text = f"📊 **Table Details: {table['name']}**\n\n"
            text += f"📍 **Full Name:** `{table['fqn']}`\n"
            text += f"🆔 **ID:** `{table['id'][:8]}...`\n"
            text += f"📝 **Description:** {table['description']}\n"
            text += f"🔧 **Retrieved via:** {result['method_used']}\n\n"
            
            if table['columns']:
                text += f"📋 **Columns ({table['column_count']} total, showing first {len(table['columns'])}):**\n"
                for col in table['columns']:
                    text += f"   • **{col['name']}** ({col['type']})"
                    if col['description']:
                        text += f" - {col['description']}"
                    text += "\n"
                
                if table['column_count'] > len(table['columns']):
                    text += f"   ... and {table['column_count'] - len(table['columns'])} more columns\n"
            else:
                text += "📋 **No column information available**\n"
                
            # Add debugging info
            text += f"\n🔍 **Debug - Attempts made:** {', '.join(result.get('attempts', []))}"
        else:
            text = f"❌ **Failed to get table '{table_name}'**\n\n**Error:** {result['error']}"
            if 'attempts' in result:
                text += f"\n\n🔍 **Attempts made:** {', '.join(result['attempts'])}"
        
        return [TextContent(type="text", text=text)]
    
    else:
        return [TextContent(type="text", text=f"❌ Unknown tool: {name}")]

@app.list_resources()
async def handle_list_resources() -> List[Resource]:
    """List available resources - exact same as working server"""
    return [
        Resource(
            uri="openmetadata://fixed-hybrid",
            name="Fixed Hybrid OpenMetadata",
            description="OpenMetadata data with lazy loading (fixed version)"
        )
    ]

async def main():
    """Main function - EXACT same as working server"""
    # Use stdio transport for Chainlit - exact same pattern
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream, 
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())