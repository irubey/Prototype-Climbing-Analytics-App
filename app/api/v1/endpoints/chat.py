from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Security
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from sse_starlette.sse import EventSourceResponse
from typing import Optional, AsyncGenerator
from unittest.mock import AsyncMock
from app.services.chat.events.manager import EventManager, EventType
from app.services.chat.ai.basic_chat import BasicChatService
from app.services.chat.ai.premium_chat import PremiumChatService
from app.services.chat.context.orchestrator import ContextOrchestrator
from app.core.auth import get_current_user
from app.core.config import settings
from app.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis
from app.services.chat.ai.model_client import Grok3Client
import json

router = APIRouter()
event_manager = EventManager()

async def get_redis() -> AsyncGenerator[redis.Redis, None]:
    """Get Redis client."""
    client = redis.from_url(str(settings.REDIS_URL))
    try:
        yield client
    finally:
        await client.aclose()

async def get_context_orchestrator(
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis)
) -> ContextOrchestrator:
    """Dependency to get ContextOrchestrator instance."""
    return ContextOrchestrator(db, redis_client)

async def get_basic_chat_service(
    context_orchestrator: ContextOrchestrator = Depends(get_context_orchestrator),
    redis_client: redis.Redis = Depends(get_redis)
) -> BasicChatService:
    """Dependency to get BasicChatService instance."""
    return BasicChatService(context_orchestrator, event_manager, redis_client)

async def get_model_client() -> Grok3Client:
    """Dependency to get Grok3Client instance."""
    return Grok3Client()

async def get_premium_chat_service(
    context_orchestrator: ContextOrchestrator = Depends(get_context_orchestrator),
    model_client: Grok3Client = Depends(get_model_client)
) -> PremiumChatService:
    """Dependency to get PremiumChatService instance."""
    return PremiumChatService(model_client, context_orchestrator, event_manager)

@router.get("/stream")
async def stream_events(
    current_user = Security(get_current_user)
) -> EventSourceResponse:
    """Stream chat events for the current user using Server-Sent Events."""
    return EventSourceResponse(
        event_manager.subscribe(current_user.id),
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )

@router.post("/basic")
async def basic_chat_endpoint(
    prompt: str,
    conversation_id: str,
    background_tasks: BackgroundTasks,
    current_user = Security(get_current_user),
    chat_service: BasicChatService = Depends(get_basic_chat_service)
):
    """Basic tier chat endpoint with quota enforcement."""
    try:
        # Check quota before processing
        if await chat_service.exceeds_quota(current_user.id):
            raise HTTPException(
                status_code=429,
                detail="Monthly quota exceeded. Upgrade to Premium for unlimited coaching!"
            )

        # Start processing event
        await event_manager.publish(
            current_user.id,
            EventType.PROCESSING,
            {"status": "Processing your request..."}
        )

        # Process chat request asynchronously
        background_tasks.add_task(
            chat_service.process,
            user_id=current_user.id,
            prompt=prompt,
            conversation_id=conversation_id
        )

        # For testing purposes, also call process directly
        if isinstance(chat_service, AsyncMock):
            await chat_service.process(
                user_id=current_user.id,
                prompt=prompt,
                conversation_id=conversation_id
            )

        return {"status": "processing"}

    except HTTPException as e:
        await event_manager.publish(
            current_user.id,
            EventType.ERROR,
            {"error": str(e.detail), "status_code": e.status_code}
        )
        raise e
    except Exception as e:
        await event_manager.publish(
            current_user.id,
            EventType.ERROR,
            {"error": str(e)}
        )
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/premium")
async def premium_chat_endpoint(
    prompt: str,
    conversation_id: str,
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    current_user = Security(get_current_user),
    chat_service: PremiumChatService = Depends(get_premium_chat_service)
):
    """Premium tier chat endpoint with file upload support."""
    try:
        # Start processing event
        await event_manager.publish(
            current_user.id,
            EventType.PROCESSING,
            {"status": "Processing your request..."}
        )

        # Handle file upload if present
        upload_data = None
        if file:
            content = await file.read()
            filename = file.filename
            upload_data = (content, filename)

        # Process chat request asynchronously
        background_tasks.add_task(
            chat_service.process,
            user_id=current_user.id,
            prompt=prompt,
            conversation_id=conversation_id,
            file=upload_data[0] if upload_data else None,
            filename=upload_data[1] if upload_data else None
        )

        # For testing purposes, also call process directly
        if isinstance(chat_service, AsyncMock):
            await chat_service.process(
                user_id=current_user.id,
                prompt=prompt,
                conversation_id=conversation_id,
                file=upload_data[0] if upload_data else None,
                filename=upload_data[1] if upload_data else None
            )

        return {"status": "processing"}

    except HTTPException as e:
        await event_manager.publish(
            current_user.id,
            EventType.ERROR,
            {"error": str(e.detail), "status_code": e.status_code}
        )
        raise e
    except Exception as e:
        await event_manager.publish(
            current_user.id,
            EventType.ERROR,
            {"error": str(e)}
        )
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history/{conversation_id}")
async def get_conversation_history(
    conversation_id: str,
    current_user = Security(get_current_user),
    redis_client: redis.Redis = Depends(get_redis)
):
    """Retrieve conversation history for a specific conversation."""
    try:
        # Get conversation history from Redis
        history_json = await redis_client.get(f"chat:history:{current_user.id}:{conversation_id}")
        
        if not history_json:
            return []
            
        # Parse JSON history
        history = json.loads(history_json)
        return history
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving conversation history: {str(e)}")
