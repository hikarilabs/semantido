from sqlalchemy import Column, Integer, String
from semantido.decorators.semantic_table import semantic_table
from semantido.models.declarative_base import SemanticDeclarativeBase


def test_semantic_table_decorator_metadata():
    """Test that the decorator correctly attaches metadata to a class."""

    @semantic_table(
        description="Core user profiles",
        synonyms=["accounts", "clients"],
        application_context="User Management System",
        business_context="Customer Base",
        sql_filters=["is_active = True"]
    )
    class DecoratedModel:
        pass

    assert DecoratedModel.__semantic_description__ == "Core user profiles"
    assert DecoratedModel.__semantic_synonyms__ == ["accounts", "clients"]
    assert DecoratedModel.__semantic_application_context__ == "User Management System"
    assert DecoratedModel.__semantic_business_context__ == "Customer Base"
    assert DecoratedModel.__semantic_sql_filters__ == ["is_active = True"]


def test_semantic_table_integration_with_bridge():
    """Test that the bridge correctly extracts data from a decorated SQLAlchemy model."""

    @semantic_table(
        description="Product inventory",
        synonyms=["stock", "items"],
        business_context="Supply Chain"
    )
    class Product(SemanticDeclarativeBase):
        __tablename__ = "products"
        id = Column(Integer, primary_key=True)
        name = Column(String)

    # Trigger sync
    semantic_layer = Product.sync_semantic_layer()

    # Verify the bridge picked up the decorator values
    assert "products" in semantic_layer.tables
    table = semantic_layer.tables["products"]

    assert table.description == "Product inventory"
    assert table.synonyms == ["stock", "items"]
    assert table.business_context == "Supply Chain"


def test_semantic_table_optional_parameters():
    """Test the decorator works fine with only mandatory description."""

    @semantic_table(description="Minimal table")
    class MinimalModel:
        pass

    assert MinimalModel.__semantic_description__ == "Minimal table"
    assert MinimalModel.__semantic_synonyms__ is None
    assert MinimalModel.__semantic_business_context__ is None