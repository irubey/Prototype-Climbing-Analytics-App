"""
Schemas for external logbook connections and data synchronization.

This module defines Pydantic models for:
- External logbook authentication
- Connection status and metadata
- Data sync configuration and status
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, HttpUrl, model_validator
from enum import Enum

from app.models.enums import LogbookType, ConnectionStatus, SyncFrequency


class LogbookAuth(BaseModel):
    """Schema for external logbook authentication."""
    logbook_type: LogbookType = Field(..., description="Type of logbook service")
    auth_token: str = Field(
        ...,
        min_length=32,
        max_length=512,
        description="Authentication token"
    )
    refresh_token: Optional[str] = Field(
        None,
        min_length=32,
        max_length=512,
        description="Refresh token"
    )
    token_expiry: Optional[datetime] = Field(
        None,
        description="Token expiration timestamp"
    )
    scopes: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Authorized scopes"
    )




    @model_validator(mode="after")
    def validate_tokens(self) -> "LogbookAuth":
        """Validate token expiry and scopes."""
        if self.token_expiry and self.token_expiry < datetime.now(timezone.utc):
            raise ValueError("Token has already expired")
        if not self.scopes:
            raise ValueError("At least one scope must be specified")
        return self

class LogbookConnection(BaseModel):
    """Schema for external logbook connection details."""
    logbook_type: LogbookType = Field(..., description="Type of logbook service")
    user_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="External user identifier"
    )
    username: Optional[str] = Field(
        None,
        max_length=100,
        description="External username"
    )
    profile_url: Optional[HttpUrl] = Field(
        None,
        description="URL to external profile"
    )
    status: ConnectionStatus = Field(
        ...,
        description="Current connection status"
    )
    sync_frequency: SyncFrequency = Field(
        default=SyncFrequency.MANUAL,
        description="Data sync frequency"
    )
    last_sync: Optional[datetime] = Field(
        None,
        description="Last successful sync"
    )
    next_sync: Optional[datetime] = Field(
        None,
        description="Next scheduled sync"
    )
    error_count: int = Field(
        default=0,
        ge=0,
        le=1000,
        description="Number of sync errors"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional connection metadata"
    )



    @model_validator(mode="after")
    def validate_sync_times(self) -> "LogbookConnection":
        """Validate sync schedule timestamps."""
        if (self.last_sync and self.next_sync and 
            self.last_sync > self.next_sync):
            raise ValueError("Next sync must be after last sync")
        if self.status == ConnectionStatus.ACTIVE and not self.username:
            raise ValueError("Active connections must have a username")
        return self

class LogbookConnectionCreate(BaseModel):
    """Schema for creating a new logbook connection."""
    logbook_type: LogbookType = Field(..., description="Type of logbook service")
    auth_data: LogbookAuth = Field(..., description="Authentication data")
    sync_frequency: Optional[SyncFrequency] = Field(
        None,
        description="Desired sync frequency"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional connection metadata"
    )

class LogbookConnectionUpdate(BaseModel):
    """Schema for updating an existing connection."""
    sync_frequency: Optional[SyncFrequency] = Field(
        None,
        description="New sync frequency"
    )
    status: Optional[ConnectionStatus] = Field(
        None,
        description="New connection status"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Updated metadata"
    )

class SyncConfig(BaseModel):
    """Schema for data sync configuration."""
    include_private: bool = Field(
        default=False,
        description="Include private ticks"
    )
    include_projects: bool = Field(
        default=True,
        description="Include project ticks"
    )
    max_ticks: Optional[int] = Field(
        None,
        gt=0,
        le=10000,
        description="Maximum ticks to sync"
    )
    start_date: Optional[datetime] = Field(
        None,
        description="Start date for sync"
    )
    end_date: Optional[datetime] = Field(
        None,
        description="End date for sync"
    )
    disciplines: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Disciplines to include"
    )

    @model_validator(mode="after")
    def validate_date_range(self) -> "SyncConfig":
        """Validate sync date range."""
        if (self.start_date and self.end_date and 
            self.start_date > self.end_date):
            raise ValueError("End date must be after start date")
        if self.start_date and self.start_date > datetime.now(timezone.utc):
            raise ValueError("Start date cannot be in the future")
        return self

class SyncStatus(BaseModel):
    """Schema for data sync operation status."""
    connection_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Connection identifier"
    )
    sync_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Sync operation identifier"
    )
    status: str = Field(
        ...,
        pattern="^(pending|in_progress|completed|failed)$",
        description="Current sync status"
    )
    total_ticks: int = Field(
        ...,
        ge=0,
        description="Total ticks to sync"
    )
    synced_ticks: int = Field(
        ...,
        ge=0,
        description="Ticks synced so far"
    )
    errors: List[Dict[str, Any]] = Field(
        default_factory=list,
        max_length=1000,
        description="Sync errors"
    )
    warnings: List[Dict[str, Any]] = Field(
        default_factory=list,
        max_length=1000,
        description="Sync warnings"
    )
    started_at: datetime = Field(..., description="Sync start time")
    completed_at: Optional[datetime] = Field(
        None,
        description="Sync completion time"
    )


    @model_validator(mode="after")
    def validate_sync_status(self) -> "SyncStatus":
        """Validate sync operation data."""
        if self.synced_ticks > self.total_ticks:
            raise ValueError("Synced ticks cannot exceed total ticks")
        if (self.completed_at and self.started_at and 
            self.completed_at < self.started_at):
            raise ValueError("Completion time cannot be before start time")
        return self
    
class LogbookConnectPayload(BaseModel):
    """Schema for logbook connection payload."""
    source: str = Field(..., description="Source of the logbook connection")
    profile_url: Optional[HttpUrl] = Field(None, description="URL to external profile")
    username: Optional[str] = Field(None, description="External username")
    password: Optional[str] = Field(None, description="External password")

class IngestionType(str, Enum):
    """Enum for logbook ingestion types."""
    MOUNTAIN_PROJECT = "mountain_project"
    EIGHT_A_NU = "eight_a_nu"
