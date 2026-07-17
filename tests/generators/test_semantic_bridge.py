from sqlalchemy import Column, Integer
from semantido.models.declarative_base import SemanticDeclarativeBase
from semantido.generators.semantic_layer import PrivacyLevel, RelationshipType


def test_semantic_layer_generation_from_sqlalchemy(models):
    """
    Test that the semantic layer is correctly generated from
    SQLAlchemy models using the SemanticDeclarativeBase.
    """

    # Trigger the sync via the bridge
    semantic_layer = models["User"].sync_semantic_layer()

    # Verify Tables
    assert "users" in semantic_layer.tables
    assert "posts" in semantic_layer.tables

    users_table = semantic_layer.tables["users"]
    assert users_table.description == "Standard user account table"
    assert users_table.primary_key == ["id"]

    # Verify Columns and Metadata
    username_col = next(c for c in users_table.columns if c.name == "username")
    assert username_col.description == "The unique login name of the user"
    assert username_col.data_type == "VARCHAR"
    assert username_col.privacy_level == PrivacyLevel.PUBLIC

    # Verify Relationships
    assert len(semantic_layer.relationships) > 0

    # Find the relationship from posts to users
    post_to_user = next(
        r
        for r in semantic_layer.relationships
        if r.from_table == "posts" and r.to_table == "users"
    )
    assert post_to_user.relationship_type == RelationshipType.MANY_TO_ONE
    assert "posts.user_id = users.id" in post_to_user.join_condition
    assert post_to_user.description == "The user who wrote this post"


def test_to_json_export():
    """Verify that the generated bridge data can be exported to JSON."""

    class SimpleModel(SemanticDeclarativeBase):
        __tablename__ = "simple"
        id = Column(Integer, primary_key=True)

    sl = SimpleModel.sync_semantic_layer()
    json_data = sl.to_json()

    assert '"name": "simple"' in json_data
    import json as _json

    parsed = _json.loads(json_data)
    assert parsed["tables"]["users"]["primary_key"] == ["id"]
