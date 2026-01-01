import pytest
import json
from semantido.generators.semantic_layer import (
    SemanticLayer, Table, Column, Relationship, PrivacyLevel, RelationshipType
)


@pytest.fixture
def complex_semantic_layer():
    """Fixture to provide a SemanticLayer with multiple entities."""
    sl = SemanticLayer()

    # 1. Define Columns
    cols = [
        Column(
            name="id",
            data_type="INTEGER",
            description="Primary Key",
            privacy_level=PrivacyLevel.PUBLIC
        ),
        Column(
            name="email",
            data_type="VARCHAR",
            description="User Email",
            privacy_level=PrivacyLevel.CONFIDENTIAL,
            synonyms=["contact", "login"]
        )
    ]

    # 2. Add a Table
    user_table = Table(
        name="users",
        description="User registry",
        columns=cols,
        primary_key="id",
        business_context="Customer Data"
    )
    sl.add_table(user_table)

    # 3. Add a Relationship
    rel = Relationship(
        from_table="orders",
        to_table="users",
        join_condition="orders.user_id = users.id",
        relationship_type=RelationshipType.MANY_TO_ONE,
        description="Links orders to customers"
    )
    sl.add_relationship(rel)

    return sl


def test_semantic_layer_add_operations(complex_semantic_layer):
    """Verify that tables and relationships are stored correctly."""
    assert "users" in complex_semantic_layer.tables
    assert len(complex_semantic_layer.relationships) == 1
    assert complex_semantic_layer.relationships[0].from_table == "orders"


def test_semantic_layer_serialization(complex_semantic_layer):
    """Verify to_dict handles Enums and nested structures correctly."""
    result = complex_semantic_layer.to_dict()

    # Check Table Structure
    assert result["tables"]["users"]["name"] == "users"
    assert result["tables"]["users"]["business_context"] == "Customer Data"

    # Check Column Serialization (specifically Enum to string conversion)
    email_col = next(c for c in result["tables"]["users"]["columns"] if c["name"] == "email")
    assert email_col["privacy_level"] == "confidential"  # Should be string, not Enum object
    assert email_col["synonyms"] == ["contact", "login"]

    # Check Relationship Serialization
    rel = result["relationships"][0]
    assert rel["relationship_type"] == "many-to-one"  # Should be string, not Enum object


def test_semantic_layer_json_output(complex_semantic_layer):
    """Verify to_json produces valid, parsable JSON."""
    json_str = complex_semantic_layer.to_json()
    parsed = json.loads(json_str)

    assert "users" in parsed["tables"]
    assert len(parsed["relationships"]) == 1


def test_semantic_layer_persistence(complex_semantic_layer, tmp_path):
    """Verify save_to_file writes correctly to disk."""
    output_file = tmp_path / "semantic_layer.json"
    complex_semantic_layer.save_to_file(str(output_file))

    assert output_file.exists()
    with open(output_file, "r") as f:
        data = json.load(f)
        assert data["tables"]["users"]["name"] == "users"


def test_empty_semantic_layer():
    """Verify behavior of a fresh, empty layer."""
    sl = SemanticLayer()
    result = sl.to_dict()
    assert result["tables"] == {}
    assert result["relationships"] == []