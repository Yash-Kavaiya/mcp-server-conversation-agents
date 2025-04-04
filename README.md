# Dialogflow CX MCP Server

A Model Control Protocol (MCP) server implementation for Dialogflow CX, enabling seamless integration between AI assistants and Google's Dialogflow CX conversational platform.

## Overview

This project provides a set of tools that allow AI assistants to interact with Dialogflow CX agents, enabling them to:

- Initialize Dialogflow CX clients
- Detect and match intents from text input
- Process audio input for speech recognition
- Handle webhook requests and responses
- Manage conversation sessions

## Requirements

- Python 3.12 or higher
- Google Cloud project with Dialogflow CX enabled
- Dialogflow CX agent

## Installation

### Using Docker

```bash
# Clone the repository
git clone https://github.com/Yash-Kavaiya/mcp-server-conversation-agents.git
cd mcp-server-conversation-agents

# Build the Docker image
docker build -t dialogflow-cx-mcp .

# Run the container
docker run -it dialogflow-cx-mcp
```

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/Yash-Kavaiya/mcp-server-conversation-agents.git
cd mcp-server-conversation-agents

# Create a virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install the package
pip install -e .
```

## Configuration

You'll need to provide the following configuration parameters:

- `dialogflowApiKey`: Your Dialogflow API key
- `projectId`: Google Cloud project ID
- `location`: Location of the Dialogflow agent (e.g., "us-central1")
- `agentId`: The ID of your Dialogflow CX agent

These can be set as environment variables:

```bash
export DIALOGFLOW_API_KEY=your_api_key
export PROJECT_ID=your_project_id
export LOCATION=your_location
export AGENT_ID=your_agent_id
```

## Usage

The MCP server exposes the following tools for AI assistants:

### initialize_dialogflow

Initialize the Dialogflow CX client with your project details.

```python
await initialize_dialogflow(
    project_id="your-project-id",
    location="us-central1",
    agent_id="your-agent-id",
    credentials_path="/path/to/credentials.json"  # Optional
)
```

### detect_intent

Detect intent from text input.

```python
response = await detect_intent(
    text="Hello, how can you help me?",
    session_id="user123",  # Optional
    language_code="en-US"  # Optional
)
```

### detect_intent_from_audio

Process audio files to detect intent.

```python
response = await detect_intent_from_audio(
    audio_file_path="/path/to/audio.wav",
    session_id="user123",  # Optional
    sample_rate_hertz=16000,  # Optional
    audio_encoding="AUDIO_ENCODING_LINEAR_16",  # Optional
    language_code="en-US"  # Optional
)
```

### match_intent

Match intent without affecting the conversation session.

```python
response = await match_intent(
    text="What are your hours?",
    session_id="user123",  # Optional
    language_code="en-US"  # Optional
)
```

### Webhook Handling

Parse webhook requests and create webhook responses:

```python
# Parse a webhook request
parsed_request = await parse_webhook_request(request_json)

# Create a webhook response
response = await create_webhook_response({
    "messages": ["Hello! How can I help you today?"],
    "parameter_updates": {"user_name": "John"}
})
```

## Smithery Integration

This project is configured to work with [Smithery.ai](https://smithery.ai/), which allows for easy deployment and management of MCP servers.

## License

[MIT License](LICENSE)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
