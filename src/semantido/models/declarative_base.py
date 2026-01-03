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

"""Defines the standard and semantic-enabled SQLAlchemy declarative base classes."""

from sqlalchemy.orm import DeclarativeBase

from semantido.models.semantic_base import SemanticBase


class Base(DeclarativeBase):
    # pylint: disable=R0903
    """Default SQLAlchemy base class for declarative models."""


class SemanticDeclarativeBase(SemanticBase, DeclarativeBase):
    """Mixin for declarative models with semantic data support."""
