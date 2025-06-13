# Chatbot Data Catalog

A conversational AI chatbot built with Chainlit that provides natural language access to your data catalog. The chatbot integrates with OpenMetadata and PostgreSQL databases through the Model Context Protocol (MCP), allowing users to explore data assets, schemas, and run queries through simple chat interactions.

## 🚀 Features

- **Conversational Interface**: User-friendly chat interface powered by Chainlit
- **Azure OpenAI Integration**: Natural language understanding and intelligent tool orchestration
- **OpenMetadata Integration**: Access data catalog information including tables, descriptions, and schemas
- **PostgreSQL Direct Access**: Query live data, list tables, and explore database schemas
- **Modular MCP Architecture**: Extensible design with dedicated MCP servers for each data source
- **Real-time Data Exploration**: Ask questions about your data and get instant responses

## 📁 Project Structure

```
.
├── .chainlit/
│   └── config.toml              # Chainlit configuration, including MCP servers
├── mcp_modules/
│   └── openmetadata/            # Source code for the OpenMetadata MCP module
├── .env                         # Environment variables (create this file)
├── .gitignore
├── app.py                       # Main Chainlit chatbot application
├── mcp_postgres_server.py       # MCP server for PostgreSQL tools
├── mcp_server.py               # MCP server for OpenMetadata tools
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## 🛠️ Setup and Installation

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
DATABASE_URL="postgresql://USER:PASSWORD@HOST:PORT/DATABASE"
```

### 5. Configure MCP Servers

Add the following configuration to `.chainlit/config.toml`:

```toml
[mcp_servers]

[mcp_servers.openmetadata]
command = ["python", "mcp_server.py"]

[mcp_servers.postgresql]
command = ["python", "mcp_postgres_server.py"]
```

### 6. Run the Application

```bash
chainlit run app.py -w
```

The `-w` flag enables auto-reload for development. Navigate to `http://localhost:8000` to access the chatbot.

## 🔧 Available Tools

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

## 💬 Usage Examples

Once the chatbot is running, you can ask questions like:

- "What tables are available in the data catalog?"
- "Show me the schema for the customer table"
- "List all tables in the PostgreSQL database"
- "Query the first 10 rows from the orders table"
- "What columns does the products table have?"
- "Execute a query to find all customers from Norway"

## 🔒 Security Considerations

- Store sensitive credentials securely in the `.env` file
- Never commit `.env` file to version control
- Use read-only database credentials when possible
- Implement proper authentication for production deployments

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is open source. Please check the repository for license information.

## 🐛 Troubleshooting

### Common Issues

1. **Connection errors**: Verify your `.env` file contains correct credentials
2. **MCP server not starting**: Ensure the `config.toml` file is properly configured
3. **Module not found errors**: Check that all dependencies are installed with `pip install -r requirements.txt`

### Debug Mode

To enable debug mode and see more detailed logs:

```bash
chainlit run app.py -w --debug
```

## 📞 Support

For issues, questions, or contributions, please open an issue on the [GitHub repository](https://github.com/birkelandnkom/chatbot_datacatalog/issues).