from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date

from app.core.auth import (
    get_current_active_user,
    get_current_premium_user,
)
from app.core.logging import logger
from app.db.session import get_db
from app.models import User
from app.schemas.chat import (
    ChatMessage,
    ChatResponse,
    ChatSettings,
    OnboardingData
)
#TODO: from app.services.chat import (
#TODO:     ChatOrchestrator,
#TODO:     ContextFormatter,
#TODO:     DataIntegrator
#TODO: )

router = APIRouter()

BASIC_TIER_DAILY_MESSAGE_LIMIT = 25

@router.post("/message", response_model=ChatResponse)
async def chat_message(
    message: ChatMessage,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Process a chat message and return AI response.
    
    - Handles message limits for basic tier
    - Processes message through AI service
    - Returns formatted response with context
    """
    # Check daily message limit for basic tier
    if current_user.tier == "basic":
        today = date.today()
        
        # Reset counter if it's a new day
        if not current_user.last_message_date or current_user.last_message_date.date() != today:
            current_user.daily_message_count = 0
            current_user.last_message_date = today
            
        
        # Increment message count
        current_user.daily_message_count += 1
        db.add(current_user)
        await db.commit()
    
    #TODO: try:
        # Initialize chat services
        #TODO: orchestrator = ChatOrchestrator(
        #TODO:     db=db,
        #TODO:     context_formatter=ContextFormatter(),
        #TODO:     data_integrator=DataIntegrator()
        #TODO: )
        
        # Process message
        #TODO: response = await orchestrator.process_chat_message(
        #TODO:     user_id=str(current_user.id),
        #TODO:     message=message.user_prompt,
        #TODO:     conversation_history=message.conversation_history,
        #TODO:     custom_context=message.custom_context,
        #TODO:     is_first_message=message.is_first_message,
        #TODO:     use_reasoner=message.use_reasoner
        #TODO: )
        
        # Add messages remaining for basic tier
        #TODO: if current_user.tier == "basic":
        #TODO:     response.messages_remaining = BASIC_TIER_DAILY_MESSAGE_LIMIT - current_user.daily_message_count
        
        #TODO: return response
        
    #TODO: except Exception as e:
    #TODO:     logger.error(f"Error processing chat message: {e}")
    #TODO:     raise HTTPException(
    #TODO:         status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #TODO:         detail="Error processing your message"
    #TODO:     )

@router.post("/onboard", response_model=OnboardingData)
async def chat_onboard(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Initialize chat session with user data.
    
    - Processes user's climbing data
    - Sets up initial context
    - Returns personalized onboarding data
    """
    #TODO: try:
        # Initialize services
        #TODO: orchestrator = ChatOrchestrator(
        #TODO:     db=db,
        #TODO:     context_formatter=ContextFormatter(),
        #TODO:     data_integrator=DataIntegrator()
        #TODO: )
        
        # Process onboarding in background
        #TODO: onboarding_data = await orchestrator.process_onboarding(
        #TODO:     user_id=str(current_user.id)
        #TODO: )
        
        #TODO: return onboarding_data
        
    #TODO: except Exception as e:
    #TODO:     logger.error(f"Error during chat onboarding: {e}")
    #TODO:     raise HTTPException(
    #TODO:         status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #TODO:         detail="Error during onboarding process"
    #TODO:     )

@router.get("/settings", response_model=ChatSettings)
async def get_chat_settings(
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """Get user's chat settings."""
    return {
        "use_reasoner": current_user.tier == "premium",
        "daily_message_limit": None if current_user.tier == "premium" else BASIC_TIER_DAILY_MESSAGE_LIMIT,
        "messages_remaining": (
            None if current_user.tier == "premium"
            else BASIC_TIER_DAILY_MESSAGE_LIMIT - (current_user.daily_message_count or 0)
        )
    }

@router.put("/settings", response_model=ChatSettings)
async def update_chat_settings(
    settings: ChatSettings,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_premium_user)
) -> Any:
    """Update user's chat settings (premium only)."""
    try:
        # Only premium users can modify settings
        current_user.chat_settings = settings.model_dump()
        db.add(current_user)
        await db.commit()
        
        return settings
        
    except Exception as e:
        logger.error(f"Error updating chat settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating chat settings"
        ) 