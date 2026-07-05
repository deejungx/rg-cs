import time
import json
import uuid
from datetime import datetime, timezone
from celery import Task
from worker import celery_app
from config import settings
from logger import get_logger
from core.monitoring import measure_execution
from schemas.agent_request import Message
from config import settings
from logger import get_logger
from services.manage_session import save_message
from services.telerivet_service import TelerivetService
from services.structure_response import get_structured_response
from src.symbio_agents.crew import Symbio_Agents
from schemas.agent_response import (
    AgentMessage,
    Message,
    MessageMetadata,
)

logger = get_logger(__name__)

# Initialize TelerivetService
telerivet_service = TelerivetService(
    api_key=settings.telerivet_api_key, project_id=settings.telerivet_project_id
)

def _process_crew_response(
    agent_response, message_metadata: MessageMetadata
) -> Message:
    if isinstance(agent_response, AgentMessage):
        assistant_message = agent_response
    else:
        json_dict = getattr(agent_response, "json_dict", None)
        if json_dict and isinstance(json_dict, dict):
            message_payload = json_dict
        else:
            message_payload = agent_response

        if hasattr(message_payload, "model_dump"):
            message_payload = message_payload.model_dump()

        assistant_message = AgentMessage(**message_payload)

    return Message(

        type=assistant_message.type,
        data=assistant_message.data,
        metadata=message_metadata,
    )

def process_agent_response(assistant_message: dict, user_id: str, agent_id: str):
    """
    Pure logic for processing agent response. 
    Exceptions are allowed to bubble up so Celery can catch them for retries.
    """
    logger.info(f"Processing agent response for user: {user_id} agent: {agent_id}")
    
    # Extract data from assistant_message
    msg_type = assistant_message.get("type")
    data = assistant_message.get("data", {})
    msg_content = data.get("content", "")

    if msg_content:
        msg_content = msg_content.rstrip()

    media_urls = []
    button_url = ""
    button_text = ""
    route_params = {}

    # Handle Message Types
    if msg_type == "media":
        media = data.get("media", {})
        if media.get("link"):
            media_urls.append(media.get("link"))
            
    elif msg_type == "link_button":
        link_button = data.get("link_button", {})
        if link_button:
            button_url = link_button.get("url") or ""
            button_text = link_button.get("button_text") or ""
            # WhatsApp/Telerivet typically has a 20-char limit for buttons
            text_slice = button_text[:20]
            route_params = {
                "common": {"link_button": {"text": text_slice, "url": button_url}}
            }
            
    elif msg_type == "location_request":
        route_params = {"whatsapp": {"request_location": True}}

    # Send message via Telerivet
    if not settings.debug_mode:
        logger.info(f"Sending message via TelerivetService to {user_id}")
        # If this service fails, it raises an exception which triggers the Celery retry
        telerivet_service.send_message(
                    content=msg_content,
                    contact_id=user_id,
                    route_id="PN0f8b06a3dd112209",
                    route_params=route_params,
                    media_urls=media_urls,
                )
    else:
        logger.info("Debug mode enabled. Skipping Telerivet message send.")

    # Save the message to the database
    save_message(
        user_id=user_id,
        agent_id=agent_id,
        role="agent",
        message=data
    )
    logger.info(f"Assistant Message saved to database for user {user_id}")
    
    return "Success"


def handle_response_failure(self,
    exc,
    task_id,
    args,
    kwargs,
    einfo,):
    """
    Custom handler for failure in sending messages via TelerivetService.
    """
    # Extract data safely from either kwargs or args
    user_id = kwargs.get('user_id') or args[1]
    logger.info(
       f"Sending default fallback message to user {user_id} after {self.request.retries} retries."
    )

    # Trigger a final fallback message to the user
    try:
        if not settings.debug_mode:
            telerivet_service.send_message(
                    content="I'm sorry, I'm having trouble processing your request. Please try again later.",
                    contact_id=user_id,
                    route_id="PN0f8b06a3dd112209",
                )
            
    except Exception as fallback_err:
        logger.error(f"Critical: Fallback message failed: {fallback_err}")

@celery_app.task(
    name="agent_tasks.handle_response",
    bind=True,                # 'self' is passed as the first argument
    queue="agent_tasks",
    autoretry_for=(Exception,), 
    retry_backoff=1,       # Exponential backoff (1s, 2s, 4s...)
    retry_jitter=True,        # Prevents "thundering herd" by adding randomness
    max_retries=5,
    on_failure=handle_response_failure,
)
@measure_execution
def handle_response(self, assistant_message, user_id: str, agent_id: str):
    """
    Celery task wrapper for agent response processing.
    """
    if not assistant_message:
        logger.error(f"No result received from agent for user {user_id}")
        return "No result"

    logger.info(f"Task {self.request.id} triggered: Processing response for user {user_id}")
    
    # We call the logic function. If it raises an Exception, 
    # autoretry_for will catch it and schedule a retry.
    return process_agent_response(assistant_message, user_id, agent_id)

@celery_app.task(name="agent_tasks.process_message", queue="agent_tasks", bind=True, max_retries=None)
@measure_execution
def process_message(
    self,
    user_id: str,
    agent_id: str,
    message_data: dict,
    request_context: dict = None,
    agent_context: dict = None,
    previous_messages: list = None,
    memory: str = None
):
    """
    Celery task to process a single message immediately.
    Returns the assistant message as a dict.
    """
    logger.info(f"Task started for user_id={user_id} agent_id={agent_id}")
    if request_context:
        logger.info(f"Request Context: {request_context}")

    try:
        message_data = Message(**message_data)
        logger.info(f"Processing message: {message_data.data.content[:50]}...")
        user_question = message_data.data.content

        if not agent_context:
            logger.error(f"Config not provided for agent {agent_id}")
            return None
            

        # Execute logic directly (sync)
        return execute_agent_logic(
            user_id, agent_id, user_question, agent_context, previous_messages, memory
        )

    except Exception as e:
        logger.error(f"Error in process_message task: {e}")
        return None


def execute_agent_logic(
    user_id, agent_id, user_question, ctx, previous_messages, memory
):
    # 1. Setup Metadata
    timestamp = datetime.now(timezone.utc)
    message_metadata = MessageMetadata(
        timestamp=timestamp,
        message_id=str(uuid.uuid4()),
    )

    # 2. Execute Crew
    try:
        symbio_agent = Symbio_Agents(tools=ctx["tools"], agent_context=ctx)
        agent_response = symbio_agent.crew().kickoff(
            inputs={
                "user_question": user_question,
                "message_metadata": message_metadata.model_dump(mode="json"),
                "history": previous_messages or [],
                "memory": memory,
                # "org_name": ctx["org_name"],
                # "org_description": ctx["org_description"],
                # "org_url": ctx["org_url"],
                "persona": ctx["persona"],
                "task": ctx["task"],
                "language": ctx["language"],
                "tone": ctx["tone"],
                "agent_name": ctx["agent_name"],
                "org_id": ctx["organization_id"],
                "user_id": user_id,
                "agent_id": agent_id,
                "source_urls": ctx["source_urls"],
                "tools": ", ".join(ctx["tools"]),
            }
        )

        structured_response = get_structured_response(f"{agent_response}")
        assistant_message_with_metadata = _process_crew_response(
            structured_response, message_metadata
        )

        logger.info("Task completed successfully.")
        
        # Return the result as a dict so it can be serialized back to the caller
        return assistant_message_with_metadata.model_dump(mode="json")

    except Exception as e:
        logger.error(f"Crew execution failed: {e}")
        return None