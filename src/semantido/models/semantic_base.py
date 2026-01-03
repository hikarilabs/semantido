# Copyright 2025 Dragos Crintea - HikariLabs LTD
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Provides the base mixin for integrating SQLAlchemy models with the semantic layer."""

from semantido.generators.semantic_layer import SemanticLayer


class SemanticBase:
    """
    A mixin class that adds semantic layer capabilities to SQLAlchemy models.

    This mixin provides utility methods to automatically bridge SQLAlchemy's
    internal schema metadata with the semantic layer, allowing for easy
    synchronization of table and relationship definitions.

    Examples:
        ```python
        from sqlalchemy.orm import DeclarativeBase
        from semantido.models.semantic_base import SemanticBase

        class Base(SemanticBase, DeclarativeBase):
            pass
        ```
    """

    @classmethod
    def get_semantic_bridge(cls):
        # pylint: disable=C0415
        """
        Retrieves or initializes the `SQLAlchemySemanticBridge` for this base class.

        This method performs a lazy initialization of the bridge by traversing
        the Method Resolution Order (MRO) to find the SQLAlchemy registry.

        Returns:
            SQLAlchemySemanticBridge: The bridge instance associated with this model hierarchy.
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
        """
        Synchronizes the semantic layer with the current state of all mapped models.

        This method clears existing semantic metadata and re-extracts all tables,
        columns, and relationships from the SQLAlchemy registry.

        Returns:
            SemanticLayer: The updated semantic layer containing the synchronized metadata.
        """
        bridge = cls.get_semantic_bridge()
        return bridge.sync_from_models()
