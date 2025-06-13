Setup and Run Instructions (MCP Server)
Here's how to set up and run your application using the new MCP server architecture. This approach is more scalable and robust.

1. Project Structure
Your project folder should be organized like this. The new chainlit.md file is now a crucial part of the setup.

your-project-root/
├── .env
├── app.py
├── requirements.txt
├── chainlit.md
└── mcp/
    └── openmetadata/
        ├── src/
        │   ├── config.py
        │   ├── main.py
        │   ├── openmetadata.py
        │   ├── server.py
        │   ├── __init__.py  (can be empty)
        │   └── mcp_components/
        │       ├── resources.py
        │       ├── tools.py
        │       └── __init__.py  (can be empty)
        ├── __main__.py
        └── README.md

Place app.py, requirements.txt, and the new chainlit.md in your project's root directory.

Ensure your MCP server code is located under mcp/openmetadata/.

2. Environment Variables
Your .env file needs to contain the credentials for both your LLM and the OpenMetadata instance. When you run the application, Chainlit will automatically make these variables available to the MCP server subprocess.

# LLM Credentials (OpenAI or Azure OpenAI)
# If using Azure, you'll need to set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY
OPENAI_API_KEY="your_api_key_here"

# OpenMetadata Credentials (for the MCP Server)
OPENMETADATA_HOST="https://your-openmetadata-host"
OPENMETADATA_JWT_TOKEN="your-jwt-token"

Note: The openai library automatically detects Azure credentials if you set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY. If you are using standard OpenAI, OPENAI_API_KEY is sufficient.

3. Installation
Install all the required packages, including openai, from the updated requirements.txt file:

pip install -r requirements.txt

4. Running the Application
Start your application with the same command. Chainlit will now automatically read chainlit.md and start your MCP server as a background process, connecting it to your chatbot.

chainlit run app.py -w
