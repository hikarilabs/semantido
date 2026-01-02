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
        """Sync the semantic layer with current model definitions"""
        bridge = cls.get_semantic_bridge()
        return bridge.sync_from_models()
