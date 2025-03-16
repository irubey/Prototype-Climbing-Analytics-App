"""
Database package initialization.
Exports core database functionality and models.
"""

from app.db.base_class import EntityBase, AssociationBase
from app.db.init_db import init_db, dispose_db
from app.db.session import (
    DatabaseSessionManager,
    sessionmanager,
    get_db,
    create_all,
    drop_all
)

__all__ = [
    # Base class and registry
    "EntityBase",
    "AssociationBase",
    
    # Database initialization and cleanup
    "init_db",
    "dispose_db",
    
    # Session management
    "DatabaseSessionManager",
    "sessionmanager",
    "get_db",
    "create_all",
    "drop_all"
]
