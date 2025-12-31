from semantido.generators.semantic_layer import SemanticLayer


class SemanticBase:
    """
    Mixin adding semantic layer capabilities to SQLAlchemy models

    Usage:
        class Base(SemanticBase, DeclarativeBase):
            ...
    """

    @classmethod
    def get_semantic_bridge(cls):
        """
        Get or create a semantic bridge for this base.
        :return:
        """
        from semantido.generators.semantic_bridge import SQLAlchemySemanticBridge

        if not hasattr(cls, "_semantic_bridge"):
            for base in cls.__mro__:
                if hasattr(base, "registry"):
                    cls._semantic_bridge = SQLAlchemySemanticBridge(base)
                    break

        return cls._semantic_bridge

    @classmethod
    def sync_semantic_layer(cls) -> "SemanticLayer":
        """Sync the semantic layer with current model definitions"""
        bridge = cls.get_semantic_bridge()
        return bridge.sync_from_models()