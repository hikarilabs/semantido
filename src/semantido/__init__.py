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

"""
This module provides the core functionality for Semantido, including decorators,
generators, and base classes for semantic data models.
"""
from semantido.decorators.semantic_table import semantic_table
from semantido.generators.semantic_bridge import SQLAlchemySemanticBridge
from semantido.generators.semantic_layer import SemanticLayer
from semantido.models.declarative_base import SemanticDeclarativeBase
from semantido.models.semantic_base import SemanticBase

__all__ = [
    "SemanticBase",
    "SemanticDeclarativeBase",
    "SemanticLayer",
    "SQLAlchemySemanticBridge",
    "semantic_table",
]
