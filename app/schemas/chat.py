"""
Chat message and settings schemas.

This module defines Pydantic models for chat functionality, including:
- Message handling
- Chat history
- User settings
- Onboarding data
"""
import sys
# Core imports that don't create cycles
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, UUID4, model_validator
from datetime import datetime, timezone

# Local imports with tracking
from app.core.logging import logger
from app.models.enums import (
    SessionLength,
    SleepScore,
    NutritionScore
)




class Message(BaseModel):
    """Schema for individual chat messages in conversation history."""
    role: str = Field(
        ...,
        pattern="^(user|assistant|system)$",
        description="Message role (user/assistant/system)"
    )
    content: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Message content"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Message timestamp"
    )



class ChatHistoryCreate(BaseModel):
    """Schema for creating a new chat history entry."""
    user_id: UUID4 = Field(..., description="ID of the user")
    conversation_id: Optional[str] = Field(
        None,
        max_length=50,
        description="Conversation identifier"
    )
    role: str = Field(
        ...,
        pattern="^(user|assistant|system)$",
        description="Message role (user/assistant/system)"
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Message content"
    )


class ChatHistoryResponse(ChatHistoryCreate):
    """Schema for chat history response with metadata."""
    id: UUID4 = Field(..., description="Chat history entry ID")
    created_at: datetime = Field(..., description="Message creation timestamp")




class ChatMessage(BaseModel):
    """Schema for incoming chat messages with context."""
    user_prompt: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="User's message"
    )
    conversation_history: List[Message] = Field(
        default_factory=list,
        max_length=50,
        description="Previous messages in conversation"
    )
    conversation_id: Optional[str] = Field(
        None,
        max_length=50,
        description="Unique conversation identifier"
    )
    custom_context: Optional[str] = Field(
        None,
        max_length=2000,
        description="Additional context for the message"
    )
    is_first_message: bool = Field(
        False,
        description="Whether this is the first message in conversation"
    )
    use_reasoner: bool = Field(
        False,
        description="Whether to use advanced reasoning (premium only)"
    )

    @model_validator(mode="after")
    def validate_history_length(self) -> "ChatMessage":
        """Validate conversation history length."""
        if len(self.conversation_history) > 50:
            raise ValueError("Conversation history cannot exceed 50 messages")
        return self


class ChatResponse(BaseModel):
    """Schema for chat response with reasoning and context."""
    response: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="AI response message"
    )
    reasoning: Optional[str] = Field(
        None,
        max_length=2000,
        description="Reasoning behind the response (premium only)"
    )
    context: Optional[str] = Field(
        None,
        max_length=2000,
        description="Additional context used for response"
    )
    messages_remaining: Optional[int] = Field(
        None,
        ge=0,
        description="Remaining messages for basic tier"
    )
    conversation_id: Optional[str] = Field(
        None,
        max_length=50,
        description="Conversation identifier"
    )


class OnboardingData(BaseModel):
    """Schema for chat onboarding data with climbing profile."""
    user_summary: str = Field(
        ...,
        max_length=2000,
        description="Summary of user's climbing profile"
    )
    climbing_stats: Dict[str, Any] = Field(
        ...,
        description="User's climbing statistics"
    )
    recent_activity: List[Dict[str, Any]] = Field(
        ...,
        max_length=10,
        description="Recent climbing activity"
    )
    preferences: Dict[str, Any] = Field(
        ...,
        description="User's climbing preferences"
    )
    session_length: Optional[SessionLength] = Field(
        None,
        description="Typical climbing session length"
    )
    sleep_score: Optional[SleepScore] = Field(
        None,
        description="User's sleep quality score"
    )
    nutrition_score: Optional[NutritionScore] = Field(
        None,
        description="User's nutrition quality score"
    )

    @model_validator(mode="after")
    def validate_activity_length(self) -> "OnboardingData":
        """Validate recent activity length."""
        if len(self.recent_activity) > 10:
            raise ValueError("Recent activity cannot exceed 10 items")
        return self


class ChatSettings(BaseModel):
    """Schema for chat settings and limits."""
    use_reasoner: bool = Field(
        False,
        description="Whether to use advanced reasoning"
    )
    daily_message_limit: Optional[int] = Field(
        None,
        ge=0,
        description="Daily message limit (None for premium)"
    )
    messages_remaining: Optional[int] = Field(
        None,
        ge=0,
        description="Remaining messages today"
    )
    conversation_retention_days: Optional[int] = Field(
        None,
        ge=1,
        le=90,
        description="Number of days to retain chat history"
    )

    @model_validator(mode="after")
    def validate_limits(self) -> "ChatSettings":
        """Validate message limits."""
        if (self.daily_message_limit is not None and 
            self.messages_remaining is not None and
            self.messages_remaining > self.daily_message_limit):
            raise ValueError("Remaining messages cannot exceed daily limit")
        return self


class ConversationSummary(BaseModel):
    """Schema for conversation list summary."""
    conversation_id: str = Field(..., description="Unique conversation identifier")
    last_updated: datetime = Field(..., description="Timestamp of the last message in the conversation")
    preview: str = Field(..., description="First few sentences of the conversation")

    class Config:
        orm_mode = True # Enable ORM mode for automatic mapping

# Log module initialization complete
logger.info(
    "Chat schemas module loaded",
    extra={
        "module_name": __name__,
        "schemas_defined": [
            cls.__name__ for cls in [
                Message, ChatHistoryCreate, ChatHistoryResponse,
                ChatMessage, ChatResponse, OnboardingData, ChatSettings,
                ConversationSummary
            ]
        ]
    }
) 