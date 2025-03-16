from sqlalchemy.orm import declarative_base, declared_attr
from sqlalchemy import Column, Integer, MetaData
from typing import Any, Dict
from loguru import logger

# Create a unified metadata object for both entity and association tables
metadata = MetaData()

class BaseMixin:
    """
    Base mixin providing common functionality for all models.
    """
    @declared_attr
    def __tablename__(cls) -> str:
        """Generate table name from class name."""
        return cls.__name__.lower()

    def model_dump(self, exclude: set = None) -> Dict[str, Any]:
        """Convert model instance to dictionary."""
        exclude = exclude or set()
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
            if column.name not in exclude
        }

    def update(self, **kwargs: Any) -> None:
        """Update model instance with given attributes."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    @classmethod
    def get_fields(cls) -> set:
        """Get all field names for the model."""
        return {column.name for column in cls.__table__.columns}

    def __repr__(self) -> str:
        """String representation of the model."""
        attrs = []
        for primary_key in self.__table__.primary_key.columns:
            if hasattr(self, primary_key.name):
                attrs.append(f"{primary_key.name}={getattr(self, primary_key.name)}")
        return f"<{self.__class__.__name__}({', '.join(attrs)})>"

class EntityMixin(BaseMixin):
    """
    Mixin for entity tables that require an auto-incrementing primary key.
    """
    id = Column(Integer, primary_key=True, autoincrement=True)

class AssociationMixin(BaseMixin):
    """
    Mixin for association tables that use composite primary keys.
    No auto-incrementing id column is provided.
    """
    pass

# Create the declarative bases with shared metadata
EntityBase = declarative_base(cls=EntityMixin, metadata=metadata)
AssociationBase = declarative_base(cls=AssociationMixin, metadata=metadata)

logger.info(f"EntityBase instance created: {id(EntityBase)}")
logger.info(f"AssociationBase instance created: {id(AssociationBase)}")
logger.info(f"Shared metadata instance created: {id(metadata)}")
logger.info(f"EntityBase registry: {id(EntityBase.registry)}")
logger.info(f"AssociationBase registry: {id(AssociationBase.registry)}") 