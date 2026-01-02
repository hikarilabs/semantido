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

from sqlalchemy.orm import DeclarativeBase

from semantido.models.semantic_base import SemanticBase


class Base(DeclarativeBase):
    # pylint: disable=R0903
    """Default SQLAlchemy base class for declarative models."""


class SemanticDeclarativeBase(SemanticBase, DeclarativeBase):
    """Mixin for declarative models with semantic data support."""
