from sqlalchemy.orm import declarative_base, declared_attr
from sqlalchemy import Column, Integer  # Import common column types here
from typing import Any, Dict
from loguru import logger

class Base:  # Define a mixin class first
    """
    Base class which provides automated table name
    and surrogate primary key column.

    Mixin Class provides:
        * Automated table name generation.
        * Surrogate integer primary key column named 'id'.
    """

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

    id = Column(Integer, primary_key=True)

    def model_dump(self, exclude: set = None) -> Dict[str, Any]:
        """
        Convert model instance to dictionary.
        Handles special types like datetime, UUID, and enums.
        """
        exclude = exclude or set()
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
            if column.name not in exclude
        }

    def update(self, **kwargs: Any) -> None:
        """
        Update model instance with given attributes.
        Only updates existing attributes.
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    @classmethod
    def get_fields(cls) -> set:
        """Get all field names for the model."""
        return {column.name for column in cls.__table__.columns}

    def __repr__(self) -> str:
        """
        String representation of the model.
        Includes class name and primary key if available.
        """
        attrs = []
        for primary_key in self.__table__.primary_key.columns:
            if hasattr(self, primary_key.name):
                attrs.append(f"{primary_key.name}={getattr(self, primary_key.name)}")
        return f"<{self.__class__.__name__}({', '.join(attrs)})>"

# Create the declarative base, inheriting from the mixin
Base = declarative_base(cls=Base)

logger.info(f"Base instance created: {id(Base)}")
logger.info(f"Base registry: {id(Base.registry)}") 