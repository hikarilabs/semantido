# Copyright (C) 2025 Dragos Crintea - HikariLabs LTD
#
# This program is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, version 3.
# You may obtain a copy of the License at:
#
#     https://spdx.org/licenses/GPL-3.0-only.html
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.

# You should have received a copy of the GNU General Public License along with this program.
# If not, see <https://www.gnu.org/licenses/>.

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
        """
        Retrieves or initializes the `SQLAlchemySemanticBridge` for this base class.

        This method performs a lazy initialization of the bridge by traversing
        the Method Resolution Order (MRO) to find the SQLAlchemy registry.

        Returns:
            SQLAlchemySemanticBridge: The bridge instance associated with this model hierarchy.
        """
        # pylint: disable=C0415
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
