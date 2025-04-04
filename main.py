from typing import Any, Dict, List, Optional
import json
import os
import uuid
import asyncio
import base64
from pathlib import Path

import httpx
from google.cloud import dialogflow_cx_v3
from google.oauth2 import service_account
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("dialogflow-cx")

class DialogflowCXClient:
    """Helper class to manage Dialogflow CX interactions."""
    
    def __init__(self, project_id: str, location: str, agent_id: str, credentials_path: Optional[str] = None):
        """Initialize the Dialogflow CX client.
        
        Args:
            project_id: Google Cloud project ID
            location: Location of the agent (e.g., 'us-central1')
            agent_id: ID of the Dialogflow CX agent
            credentials_path: Path to service account credentials file
        """
        self.project_id = project_id
        self.location = location
        self.agent_id = agent_id
        
        if credentials_path and os.path.exists(credentials_path):
            credentials = service_account.Credentials.from_service_account_file(credentials_path)
            self.sessions_client = dialogflow_cx_v3.SessionsClient(credentials=credentials)
        else:
            # Use default credentials
            self.sessions_client = dialogflow_cx_v3.SessionsClient()
            
        self.agent_path = f"projects/{project_id}/locations/{location}/agents/{agent_id}"
    
    def create_session_path(self, session_id: Optional[str] = None) -> str:
        """Create a session path for the agent.
        
        Args:
            session_id: Optional session ID. If not provided, a UUID is generated.
            
        Returns:
            Session path string
        """
        if not session_id:
            session_id = str(uuid.uuid4())
        
        return f"{self.agent_path}/sessions/{session_id}"
    
    async def detect_intent(self, session_id: str, text: str, language_code: str = "en-US") -> Dict[str, Any]:
        """Detect intent from text input.
        
        Args:
            session_id: Session ID
            text: User input text
            language_code: Language code
            
        Returns:
            Dictionary containing the response
        """
        session_path = self.create_session_path(session_id)
        
        text_input = dialogflow_cx_v3.TextInput(text=text)
        query_input = dialogflow_cx_v3.QueryInput(
            text=text_input,
            language_code=language_code
        )
        
        request = dialogflow_cx_v3.DetectIntentRequest(
            session=session_path,
            query_input=query_input
        )
        
        # Convert synchronous call to async
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, 
            lambda: self.sessions_client.detect_intent(request)
        )
        
        return self._process_response(response)
    
    async def detect_intent_audio(self, 
                                 session_id: str, 
                                 audio_content: bytes, 
                                 sample_rate_hertz: int = 16000,
                                 audio_encoding: str = "AUDIO_ENCODING_LINEAR_16",
                                 language_code: str = "en-US") -> Dict[str, Any]:
        """Detect intent from audio input.
        
        Args:
            session_id: Session ID
            audio_content: Audio content bytes
            sample_rate_hertz: Sample rate of the audio
            audio_encoding: Audio encoding format
            language_code: Language code
            
        Returns:
            Dictionary containing the response
        """
        session_path = self.create_session_path(session_id)
        
        # Convert audio encoding string to enum
        encoding_enum = getattr(dialogflow_cx_v3.AudioEncoding, audio_encoding)
        
        audio_input = dialogflow_cx_v3.AudioInput(
            config=dialogflow_cx_v3.InputAudioConfig(
                audio_encoding=encoding_enum,
                sample_rate_hertz=sample_rate_hertz,
                single_utterance=True
            ),
            audio=audio_content
        )
        
        query_input = dialogflow_cx_v3.QueryInput(
            audio=audio_input,
            language_code=language_code
        )
        
        request = dialogflow_cx_v3.DetectIntentRequest(
            session=session_path,
            query_input=query_input
        )
        
        # Convert synchronous call to async
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, 
            lambda: self.sessions_client.detect_intent(request)
        )
        
        return self._process_response(response)
    
    async def match_intent(self, session_id: str, text: str, language_code: str = "en-US") -> Dict[str, Any]:
        """Match intent without affecting the session.
        
        Args:
            session_id: Session ID
            text: User input text
            language_code: Language code
            
        Returns:
            Dictionary containing the response
        """
        session_path = self.create_session_path(session_id)
        
        text_input = dialogflow_cx_v3.TextInput(text=text)
        query_input = dialogflow_cx_v3.QueryInput(
            text=text_input,
            language_code=language_code
        )
        
        request = dialogflow_cx_v3.MatchIntentRequest(
            session=session_path,
            query_input=query_input
        )
        
        # Convert synchronous call to async
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, 
            lambda: self.sessions_client.match_intent(request)
        )
        
        return {
            "matches": [
                {
                    "intent": match.intent.display_name if match.intent else "No intent",
                    "confidence": match.confidence,
                    "parameters": self._extract_parameters(match.parameters)
                }
                for match in response.matches
            ],
            "current_page": response.current_page.display_name
        }

    def _process_response(self, response: dialogflow_cx_v3.DetectIntentResponse) -> Dict[str, Any]:
        """Process and format the detect intent response.
        
        Args:
            response: The DetectIntentResponse object
            
        Returns:
            Dictionary with formatted response data
        """
        query_result = response.query_result
        
        # Extract response messages
        messages = []
        for msg in query_result.response_messages:
            if msg.text:
                messages.append({"type": "text", "content": "\n".join(msg.text.text)})
            elif msg.payload:
                payload_dict = dict(msg.payload)
                messages.append({"type": "payload", "content": payload_dict})
        
        # Check for end_interaction signal
        has_end_interaction = any("end_interaction" in str(msg) for msg in query_result.response_messages)
        
        # Extract intent info
        intent_info = None
        if query_result.match.intent:
            intent_info = {
                "name": query_result.match.intent.display_name,
                "confidence": query_result.match.confidence
            }
        
        # Extract parameters
        parameters = self._extract_parameters(query_result.parameters)
        
        return {
            "messages": messages,
            "intent": intent_info,
            "parameters": parameters,
            "current_page": query_result.current_page.display_name,
            "transcript": query_result.transcript,
            "end_interaction": has_end_interaction
        }
    
    def _extract_parameters(self, parameters):
        """Extract and format parameters from the response."""
        if not parameters:
            return {}
        
        param_dict = {}
        for key, value in parameters.items():
            # Handle different types of parameter values
            if hasattr(value, 'string_value'):
                param_dict[key] = value.string_value
            elif hasattr(value, 'number_value'):
                param_dict[key] = value.number_value
            elif hasattr(value, 'bool_value'):
                param_dict[key] = value.bool_value
            elif hasattr(value, 'struct_value'):
                param_dict[key] = dict(value.struct_value)
            else:
                param_dict[key] = str(value)
        
        return param_dict
# Create a global DialogflowCX client
DIALOGFLOW_CLIENT = None

@mcp.tool()
async def initialize_dialogflow(
    project_id: str, 
    location: str, 
    agent_id: str, 
    credentials_path: Optional[str] = None
) -> str:
    """Initialize the Dialogflow CX client.
    
    Args:
        project_id: Google Cloud project ID
        location: Location of the agent (e.g., 'us-central1')
        agent_id: ID of the Dialogflow CX agent
        credentials_path: Optional path to service account credentials file
    """
    global DIALOGFLOW_CLIENT
    
    try:
        DIALOGFLOW_CLIENT = DialogflowCXClient(
            project_id=project_id,
            location=location,
            agent_id=agent_id,
            credentials_path=credentials_path
        )
        return f"Dialogflow CX client initialized for agent: {agent_id}"
    except Exception as e:
        return f"Error initializing Dialogflow CX client: {str(e)}"

@mcp.tool()
async def detect_intent(
    text: str, 
    session_id: Optional[str] = None, 
    language_code: str = "en-US"
) -> Dict[str, Any]:
    """Detect intent from text input.
    
    Args:
        text: User input text
        session_id: Optional session ID. If not provided, a random UUID is generated
        language_code: Language code (default: en-US)
    """
    global DIALOGFLOW_CLIENT
    
    if not DIALOGFLOW_CLIENT:
        return {"error": "Dialogflow CX client not initialized. Call initialize_dialogflow first."}
    
    if not session_id:
        session_id = str(uuid.uuid4())
    
    try:
        response = await DIALOGFLOW_CLIENT.detect_intent(
            session_id=session_id,
            text=text,
            language_code=language_code
        )
        
        # Add session_id to the response for future reference
        response["session_id"] = session_id
        return response
    except Exception as e:
        return {"error": f"Error detecting intent: {str(e)}"}
@mcp.tool()
async def detect_intent_from_audio(
    audio_file_path: str,
    session_id: Optional[str] = None,
    sample_rate_hertz: int = 16000,
    audio_encoding: str = "AUDIO_ENCODING_LINEAR_16",
    language_code: str = "en-US"
) -> Dict[str, Any]:
    """Detect intent from an audio file.
    
    Args:
        audio_file_path: Path to audio file
        session_id: Optional session ID. If not provided, a random UUID is generated
        sample_rate_hertz: Sample rate of the audio
        audio_encoding: Audio encoding format
        language_code: Language code (default: en-US)
    """
    global DIALOGFLOW_CLIENT
    
    if not DIALOGFLOW_CLIENT:
        return {"error": "Dialogflow CX client not initialized. Call initialize_dialogflow first."}
    
    if not session_id:
        session_id = str(uuid.uuid4())
    
    try:
        # Read audio file
        with open(audio_file_path, 'rb') as audio_file:
            audio_content = audio_file.read()
        
        response = await DIALOGFLOW_CLIENT.detect_intent_audio(
            session_id=session_id,
            audio_content=audio_content,
            sample_rate_hertz=sample_rate_hertz,
            audio_encoding=audio_encoding,
            language_code=language_code
        )
        
        # Add session_id to the response for future reference
        response["session_id"] = session_id
        return response
    except Exception as e:
        return {"error": f"Error detecting intent from audio: {str(e)}"}

@mcp.tool()
async def detect_intent_from_base64(
    audio_base64: str,
    session_id: Optional[str] = None,
    sample_rate_hertz: int = 16000,
    audio_encoding: str = "AUDIO_ENCODING_LINEAR_16",
    language_code: str = "en-US"
) -> Dict[str, Any]:
    """Detect intent from base64 encoded audio.
    
    Args:
        audio_base64: Base64 encoded audio content
        session_id: Optional session ID. If not provided, a random UUID is generated
        sample_rate_hertz: Sample rate of the audio
        audio_encoding: Audio encoding format
        language_code: Language code (default: en-US)
    """
    global DIALOGFLOW_CLIENT
    
    if not DIALOGFLOW_CLIENT:
        return {"error": "Dialogflow CX client not initialized. Call initialize_dialogflow first."}
    
    if not session_id:
        session_id = str(uuid.uuid4())
    
    try:
        # Decode base64 audio
        audio_content = base64.b64decode(audio_base64)
        
        response = await DIALOGFLOW_CLIENT.detect_intent_audio(
            session_id=session_id,
            audio_content=audio_content,
            sample_rate_hertz=sample_rate_hertz,
            audio_encoding=audio_encoding,
            language_code=language_code
        )
        
        # Add session_id to the response for future reference
        response["session_id"] = session_id
        return response
    except Exception as e:
        return {"error": f"Error detecting intent from base64 audio: {str(e)}"}


@mcp.tool()
async def match_intent(
    text: str, 
    session_id: Optional[str] = None, 
    language_code: str = "en-US"
) -> Dict[str, Any]:
    """Match intent without affecting the session.
    
    Args:
        text: User input text
        session_id: Optional session ID. If not provided, a random UUID is generated
        language_code: Language code (default: en-US)
    """
    global DIALOGFLOW_CLIENT
    
    if not DIALOGFLOW_CLIENT:
        return {"error": "Dialogflow CX client not initialized. Call initialize_dialogflow first."}
    
    if not session_id:
        session_id = str(uuid.uuid4())
    
    try:
        response = await DIALOGFLOW_CLIENT.match_intent(
            session_id=session_id,
            text=text,
            language_code=language_code
        )
        
        # Add session_id to the response for future reference
        response["session_id"] = session_id
        return response
    except Exception as e:
        return {"error": f"Error matching intent: {str(e)}"}

@mcp.tool()
async def create_webhook_response(
    fulfillment_response: Dict[str, Any]
) -> Dict[str, Any]:
    """Create a response for a Dialogflow CX webhook request.
    
    Args:
        fulfillment_response: The response to send back
    
    Returns:
        Properly formatted webhook response for Dialogflow CX
    """
    try:
        # Format the response according to Dialogflow CX webhook format
        response = {"fulfillmentResponse": {}}
        
        # Add messages if provided
        if "messages" in fulfillment_response:
            response["fulfillmentResponse"]["messages"] = []
            for msg in fulfillment_response["messages"]:
                if isinstance(msg, str):
                    # Simple text message
                    response["fulfillmentResponse"]["messages"].append({
                        "text": {"text": [msg]}
                    })
                elif isinstance(msg, dict) and "text" in msg:
                    # Already formatted text message
                    response["fulfillmentResponse"]["messages"].append({
                        "text": {"text": [msg["text"]]}
                    })
                elif isinstance(msg, dict) and "payload" in msg:
                    # Custom payload
                    response["fulfillmentResponse"]["messages"].append({
                        "payload": msg["payload"]
                    })
        
        # Add parameter updates if provided
        if "parameter_updates" in fulfillment_response:
            response["sessionInfo"] = {
                "parameters": fulfillment_response["parameter_updates"]
            }
        
        # Add page info for page transitions
        if "target_page" in fulfillment_response:
            response["targetPage"] = fulfillment_response["target_page"]
        
        # Add target flow for flow transitions
        if "target_flow" in fulfillment_response:
            response["targetFlow"] = fulfillment_response["target_flow"]
        
        return response
    except Exception as e:
        return {"error": f"Error creating webhook response: {str(e)}"}

@mcp.tool()
async def parse_webhook_request(request_json: str) -> Dict[str, Any]:
    """Parse a Dialogflow CX webhook request.
    
    Args:
        request_json: JSON string of the webhook request
        
    Returns:
        Dictionary with parsed webhook request data
    """
    try:
        request_data = json.loads(request_json)
        
        # Extract useful information from the request
        session = request_data.get("sessionInfo", {})
        intent = request_data.get("intentInfo", {})
        params = session.get("parameters", {})
        
        # Extract current page info
        page_info = request_data.get("pageInfo", {})
        current_page = page_info.get("displayName", "")
        
        # Extract messages from previous turn if available
        messages = []
        for msg in request_data.get("messages", []):
            if "text" in msg:
                messages.append({"type": "text", "content": msg["text"]["text"]})
            elif "payload" in msg:
                messages.append({"type": "payload", "content": msg["payload"]})
        
        return {
            "session_id": session.get("session", ""),
            "intent_name": intent.get("displayName", ""),
            "parameters": params,
            "current_page": current_page,
            "messages": messages,
            "raw_request": request_data  # Include the full request for reference
        }
    except Exception as e:
        return {"error": f"Error parsing webhook request: {str(e)}"}

@mcp.tool()
async def check_end_interaction(response: Dict[str, Any]) -> bool:
    """Check if the response contains an end_interaction signal.
    
    Args:
        response: The response from detect_intent
        
    Returns:
        True if end_interaction was triggered, False otherwise
    """
    return response.get("end_interaction", False)

if __name__ == "__main__":
    # Print startup message
    print("Dialogflow CX MCP server starting...", flush=True)
    
    # Initialize and run the server
    mcp.run(transport='stdio')

