Chatbot for Data Catalog
This project implements a conversational AI chatbot using Chainlit to interact with your data catalog. The chatbot leverages the Model Context Protocol (MCP) to connect with various data sources, including an OpenMetadata instance and a PostgreSQL database.

Users can ask natural language questions about database tables and data assets, and the chatbot will use its integrated tools to find and return the relevant information.

Features
Conversational Interface: A user-friendly chat interface built with Chainlit.

Azure OpenAI Integration: Powered by Azure OpenAI's language models to understand queries and orchestrate tool usage.

OpenMetadata Tools: Connects to an OpenMetadata server to fetch information about data assets like tables, descriptions, and schemas.

PostgreSQL Tools: Directly connects to and queries a PostgreSQL database to retrieve live data, list tables, and describe schemas.

Modular MCP Architecture: The connection to data sources is handled by dedicated MCP servers (mcp_server.py for OpenMetadata and mcp_postgres_server.py for PostgreSQL), making the system extensible.

Project Structure
.
├── .chainlit/
│   └── config.toml      # Chainlit configuration, including MCP servers
├── mcp_modules/
│   └── openmetadata/    # Source code for the OpenMetadata MCP module
├── .env                 # Environment variables (you need to create this)
├── .gitignore
├── app.py               # The main Chainlit chatbot application
├── mcp_postgres_server.py # MCP server for PostgreSQL tools
├── mcp_server.py        # MCP server for OpenMetadata tools
├── requirements.txt     # Python dependencies
└── README.md            # This file

Setup and Installation
1. Clone the Repository
First, clone this repository to your local machine.

2. Create the Environment File
Create a file named .env in the root of the project and add the necessary credentials. The application uses these variables to connect to Azure OpenAI, OpenMetadata, and PostgreSQL.

# Azure OpenAI Credentials
AZURE_OPENAI_ENDPOINT="YOUR_AZURE_ENDPOINT"
AZURE_OPENAI_API_KEY="YOUR_AZURE_API_KEY"
AZURE_OPENAI_DEPLOYMENT_NAME="YOUR_DEPLOYMENT_NAME"

# OpenMetadata Credentials (for mcp_server.py)
OPENMETADATA_HOST="YOUR_OPENMETADATA_HOST_URL"
OPENMETADATA_JWT_TOKEN="YOUR_OPENMETADATA_JWT_TOKEN"

# PostgreSQL Connection (for mcp_postgres_server.py)
# Option 1: Using a connection string
DATABASE_URL="postgresql://USER:PASSWORD@HOST:PORT/DATABASE"

# Option 2: Using individual variables (if DATABASE_URL is not set)
# POSTGRES_HOST="localhost"
# POSTGRES_PORT="5432"
# POSTGRES_DB="your_database"
# POSTGRES_USER="your_user"
# POSTGRES_PASSWORD="your_password"

3. Configure MCP Servers
To allow Chainlit to run the data source servers, you need to add their configuration to the .chainlit/config.toml file. Add the following [mcp_servers] section to the end of your existing config.toml file:

# Add this section to your .chainlit/config.toml

[mcp_servers]

[mcp_servers.openmetadata]
# This command starts the OpenMetadata server
command = ["python", "mcp_server.py"]

[mcp_servers.postgresql]
# This command starts the PostgreSQL server
command = ["python", "mcp_postgres_server.py"]

Note: This configuration tells Chainlit to automatically start both mcp_server.py and mcp_postgres_server.py as background processes when you run the app.

4. Install Dependencies
Install the required Python packages from the requirements.txt file:

pip install -r requirements.txt

5. Run the Application
Start the Chainlit application with the following command. The -w flag enables auto-reloading, so the app will restart whenever you save a file.

chainlit run app.py -w

Once running, navigate to the local URL provided by Chainlit (usually http://localhost:8000) in your browser. The chatbot will automatically connect to the MCP servers, and you can start asking questions.

Available Tools
The chatbot has access to a variety of tools to answer your questions.

OpenMetadata Tools (mcp_server.py)
debug_env: Debugs environment variables for the OpenMetadata connection.

test_om_connection: Performs a quick test to check the connection to the OpenMetadata server.

list_om_tables: Lists available tables from the OpenMetadata catalog.

get_om_table: Fetches detailed information, including schema and descriptions, for a specific table.

PostgreSQL Tools (mcp_postgres_server.py)
debug_postgres_env: Debugs environment variables for the PostgreSQL connection.

connect_postgres: Establishes a connection to the PostgreSQL database.

list_postgres_tables: Lists all tables in the connected database.

query_postgres_table: Runs a SELECT * query on a specific table to view its data.

execute_postgres_query: Executes a custom (read-only SELECT) SQL query.

get_postgres_schema: Retrieves the detailed schema for a specific table, including columns, data types, and keys.