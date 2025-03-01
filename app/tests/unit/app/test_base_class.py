"""
Unit tests for SQLAlchemy Base model.

These tests verify that the Base model works correctly, including:
- Table name generation
- Model serialization (model_dump)
- Model attribute updates
- Field retrieval
- String representation
"""

import pytest
from unittest.mock import Mock, patch
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum
import datetime
import enum
import uuid
from app.db.base_class import Base


class TestEnum(enum.Enum):
    """Sample enum for testing."""
    VALUE1 = "value1"
    VALUE2 = "value2"


# Create a sample model class for testing
class TestModel(Base):
    """Test model for Base class testing."""
    name = Column(String(50), nullable=False)
    description = Column(String(200), nullable=True)
    status = Column(Enum(TestEnum), nullable=True)
    created_at = Column(DateTime, nullable=False)
    parent_id = Column(Integer, ForeignKey("parent.id"), nullable=True)


def test_tablename_generation():
    """Test automatic table name generation."""
    # The table name should be lowercase of the class name
    assert TestModel.__tablename__ == "testmodel"
    
    # Test with a different class name
    class AnotherModel(Base):
        pass
    
    assert AnotherModel.__tablename__ == "anothermodel"


def test_model_dump():
    """Test model_dump method for converting model to dictionary."""
    # Create a model instance with test data
    created_at = datetime.datetime(2023, 1, 1, 12, 0, 0)
    model = TestModel(
        id=1,
        name="Test Object",
        description="A test object",
        status=TestEnum.VALUE1,
        created_at=created_at,
        parent_id=None
    )
    
    # Convert to dictionary
    data = model.model_dump()
    
    # Verify all fields are included and have correct values
    assert data["id"] == 1
    assert data["name"] == "Test Object"
    assert data["description"] == "A test object"
    assert data["status"] == TestEnum.VALUE1
    assert data["created_at"] == created_at
    assert data["parent_id"] is None
    
    # Test with exclude parameter
    data_exclude = model.model_dump(exclude={"id", "created_at"})
    assert "id" not in data_exclude
    assert "created_at" not in data_exclude
    assert "name" in data_exclude
    assert "description" in data_exclude


def test_model_update():
    """Test update method for updating model attributes."""
    model = TestModel(
        id=1,
        name="Original Name",
        description="Original description",
        created_at=datetime.datetime.now()
    )
    
    # Update some attributes
    model.update(
        name="Updated Name",
        description="Updated description",
        nonexistent_attr="This should be ignored"
    )
    
    # Verify the attributes were updated
    assert model.name == "Updated Name"
    assert model.description == "Updated description"
    
    # Verify the nonexistent attribute was ignored
    assert not hasattr(model, "nonexistent_attr")


def test_get_fields():
    """Test get_fields method for retrieving field names."""
    fields = TestModel.get_fields()
    
    # Verify all fields are included
    assert "id" in fields
    assert "name" in fields
    assert "description" in fields
    assert "status" in fields
    assert "created_at" in fields
    assert "parent_id" in fields
    
    # Verify the total number of fields is correct
    assert len(fields) == 6


def test_repr_method():
    """Test __repr__ method for string representation."""
    model = TestModel(id=42, name="Test")
    
    # The representation should include the class name and primary key
    repr_str = repr(model)
    assert "TestModel" in repr_str
    assert "id=42" in repr_str
    
    # Test multiple columns case (no mocking needed)
    # We just verify that the current implementation handles
    # a model with its primary key correctly
    model = TestModel(id=1, name="Test")
    repr_str = repr(model)
    assert "TestModel" in repr_str
    assert "id=" in repr_str  # Primary key should be included


def test_base_singleton():
    """Test that the Base class is a singleton (created once)."""
    from app.db.base_class import Base as Base1
    from app.db.base_class import Base as Base2
    
    assert Base1 is Base2
    assert id(Base1) == id(Base2)
    assert Base1.registry is Base2.registry


def test_model_attributes():
    """Test that models created from Base have expected attributes."""
    # Create a model instance
    model = TestModel()
    
    # Verify instance has expected attributes
    assert hasattr(model, "id")
    assert hasattr(model, "model_dump")
    assert hasattr(model, "update")
    
    # Verify class has expected attributes
    assert hasattr(TestModel, "get_fields")
    assert hasattr(TestModel, "__tablename__")


def test_complex_model_dump():
    """Test model_dump with more complex data types."""
    # Mock a model with UUID and other complex types
    class ComplexModel(Base):
        id = Column(Integer, primary_key=True)
        uuid_field = Column(String(36), nullable=False)
    
    test_uuid = uuid.uuid4()
    model = ComplexModel(id=1, uuid_field=str(test_uuid))
    
    # Convert to dictionary
    data = model.model_dump()
    
    # Verify complex types are handled correctly
    assert data["id"] == 1
    assert data["uuid_field"] == str(test_uuid)


def test_update_with_none_values():
    """Test update method with None values."""
    model = TestModel(
        id=1,
        name="Original Name",
        description="Original description",
        created_at=datetime.datetime.now()
    )
    
    # Update with None values
    model.update(description=None)
    
    # Verify the attributes were updated
    assert model.name == "Original Name"
    assert model.description is None 