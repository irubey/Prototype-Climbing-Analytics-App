"""
Schema package for Send Sage application.

This package defines all Pydantic models used for:
- Data validation
- API request/response models
- Database model serialization
- Configuration settings
"""

# Authentication schemas
from app.schemas.auth import (
    UserTier,
    PaymentStatus,
    UserBase,
    UserCreate,
    UserLogin,
    UserResponse,
    Token,
    TokenData,
    PasswordReset,
    PasswordUpdate
)

# Chat and messaging schemas
from app.schemas.chat import (
    ChatHistoryCreate,
    ChatHistoryResponse,
    ChatMessage,
    ChatResponse,
    ChatSettings,
    OnboardingData,
    SessionLength,
    SleepScore,
    NutritionScore
)

# Climbing data schemas
from app.schemas.data import (
    BinnedCode,
    PyramidInput,
    PerformanceData,
    TickCreate,
    TickResponse,
    BatchTickCreate,
    RefreshStatus,
    Tag,
    TagCreate,
    TagResponse,
    UserTicksWithTags,
    BulkTagUpdate,
    GradeConversion,
    GradeConversionResponse,
    DataImportStatus
)

# Logbook connection schemas
from app.schemas.logbook_connection import (
    ConnectionStatus,
    SyncFrequency,
    LogbookAuth,
    LogbookConnection,
    LogbookConnectionCreate,
    LogbookConnectionUpdate,
    SyncConfig,
    SyncStatus
)

# Payment and subscription schemas
from app.schemas.payment import (
    StripeCheckoutSession,
    StripeWebhookEvent,
    PaymentDetails,
    PricingInfo,
    SubscriptionUpdate,
    PaymentMethodUpdate,
    BillingPortalSession
)

# User profile schemas
from app.schemas.user import (
    UserProfile,
    UserProfileUpdate,
    ClimberSummaryBase,
    ClimberSummaryCreate,
    ClimberSummaryUpdate,
    ClimberSummaryResponse
)

# Visualization schemas
from app.schemas.visualization import (
    TickData,
    DashboardBaseMetrics,
    HardSend,
    DashboardPerformanceMetrics,
    PerformancePyramidData,
    BaseVolumeData,
    ProgressionData,
    LocationAnalysis,
    PerformanceCharacteristics
)

__all__ = [
    # Auth schemas
    "UserTier", "PaymentStatus", "UserBase", "UserCreate", "UserLogin",
    "UserResponse", "Token", "TokenData", "PasswordReset", "PasswordUpdate",
    
    # Chat schemas
    "ChatHistoryCreate", "ChatHistoryResponse", "ChatMessage", "ChatResponse",
    "ChatSettings", "OnboardingData", "SessionLength", "SleepScore", "NutritionScore",
    
    # Data schemas
    "BinnedCode", "PyramidInput", "PerformanceData", "TickCreate", "TickResponse",
    "BatchTickCreate", "RefreshStatus", "Tag", "TagCreate", "TagResponse",
    "UserTicksWithTags", "BulkTagUpdate", "GradeConversion", "GradeConversionResponse",
    "DataImportStatus",
    
    # Logbook schemas
    "ConnectionStatus", "SyncFrequency", "LogbookAuth", "LogbookConnection",
    "LogbookConnectionCreate", "LogbookConnectionUpdate", "SyncConfig", "SyncStatus",
    
    # Payment schemas
    "StripeCheckoutSession", "StripeWebhookEvent", "PaymentDetails", "PricingInfo",
    "SubscriptionUpdate", "PaymentMethodUpdate", "BillingPortalSession",
    
    # User schemas
    "UserProfile", "UserProfileUpdate", "ClimberSummaryBase", "ClimberSummaryCreate",
    "ClimberSummaryUpdate", "ClimberSummaryResponse",
    
    # Visualization schemas
    "TickData", "DashboardBaseMetrics", "HardSend", "DashboardPerformanceMetrics",
    "PerformancePyramidData", "BaseVolumeData", "ProgressionData", "LocationAnalysis",
    "PerformanceCharacteristics"
]
