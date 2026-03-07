from semantido import SemanticDeclarativeBase


def test_semantic_base(models):
    """
    Test that the semantic base is correctly initialized
    from all available SQLAlchemy models using the SemanticDeclarativeBase.
    A valid semantic layer containing the tables is returned.
    """

    semantic_layer = SemanticDeclarativeBase.sync_semantic_layer()

    assert "users" in semantic_layer.tables
    assert "posts" in semantic_layer.tables
