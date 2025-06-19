# Chatbot Data Catalog

A conversational AI chatbot built with Chainlit that provides natural language access to data. The chatbot integrates with OpenMetadata and PostgreSQL through Model Context Protocol (MCP).

## Project Structure

```
.
├── .chainlit/
│   └── config.toml           # Chainlit configuration, including MCP servers
├── mcp_modules/
│   └── openmetadata/         # Source code for the OpenMetadata MCP module
├── public/
│   └── custom.css            # Custom css code
│   └── theme.json            # Custom theme (modifying css)
├── .env                      # Environment variables (create this file)
├── .gitignore
├── app.py                    # Main Chainlit chatbot application
├── mcp_postgres_server.py    # MCP server for PostgreSQL tools
├── mcp_server.py             # MCP server for OpenMetadata tools
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

## Setup and Installation

### 1. Clone the Repository

```bash
git clone https://github.com/birkelandnkom/chatbot_datacatalog.git
cd chatbot_datacatalog
```

### 2. Create a Virtual Environment (Recommended)

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the root directory with the following variables:

```env
# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT="YOUR_AZURE_ENDPOINT"
AZURE_OPENAI_API_KEY="YOUR_AZURE_API_KEY"
AZURE_OPENAI_DEPLOYMENT_NAME="YOUR_DEPLOYMENT_NAME"

# OpenMetadata Configuration
OPENMETADATA_HOST="YOUR_OPENMETADATA_HOST_URL"
OPENMETADATA_JWT_TOKEN="YOUR_OPENMETADATA_JWT_TOKEN"

# PostgreSQL Configuration
MCP_POSTGRES_URL="postgresql://USER:PASSWORD@HOST:PORT/DATABASE"
```

### 5. Configure Chainlit config

Add the following configuration to `.chainlit/config.toml`:

```toml
[features.mcp.stdio]
    enabled = true
    allowed_executables = ["python"]
```

### 6. Run the Application

```bash
chainlit run app.py -w
```

The `-w` flag enables auto-reload for development. Navigate to `http://localhost:8000` to access the chatbot.

Add MCP servers using the commands

```bash
python mcp_postgres_server.py
```

```bash
python mcp_server.py
```

## Available Tools

### OpenMetadata Tools (`mcp_server.py`)

- **debug_env**: Debug environment variables for OpenMetadata connection
- **test_om_connection**: Test connection to OpenMetadata server
- **list_om_tables**: List available tables from the data catalog
- **get_om_table**: Get detailed information about a specific table

### PostgreSQL Tools (`mcp_postgres_server.py`)

- **debug_postgres_env**: Debug environment variables for PostgreSQL
- **connect_postgres**: Establish database connection
- **list_postgres_tables**: List all tables in the database
- **query_postgres_table**: Run SELECT queries on tables
- **execute_postgres_query**: Execute custom read-only SQL queries
- **get_postgres_schema**: Retrieve detailed schema information

## Security Considerations

- Store credentials in the `.env` file
- Never commit `.env` file to version control
- Use read-only database credentials


### Debug Mode

To enable debug mode and see more detailed logs:

```bash
chainlit run app.py -w --debug
```