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

"""Defines the decorator for attaching semantic metadata to SQLAlchemy models."""

from typing import Optional


def semantic_table(
    description: str,
    synonyms: Optional[list[str]] = None,
    sql_filters: Optional[list[str]] = None,
    application_context: Optional[str] = None,
    business_context: Optional[str] = None,
):
    """A class decorator to enrich SQLAlchemy models with semantic metadata.

    This metadata is used by the `SQLAlchemySemanticBridge` to build a semantic layer,
    helping tools and LLMs understand the purpose, context, and filtering requirements
    of the underlying database table.Decorator for adding semantic information to SQLAlchemy models

    Args:
        description: A human-readable explanation of what the table represents.
        synonyms: Alternative names for the entity (e.g., ["client", "customer"]).
        sql_filters: A list of SQL fragments used for default filtering or row-level security.
        application_context: The technical or functional scope within the app.
        business_context: The business domain or logic this table belongs to.

    Examples:
        ```python
        @semantic_table(
            description="User information and login profile",
            synonyms=["user profile", "client"],
            application_context="Registered users on the platform"
        )
        class User(Base):
            __tablename__ = "users"
            id = Column(Integer, primary_key=True)
        ```
    """

    def decorator(cls):
        cls.__semantic_description__ = description
        cls.__semantic_synonyms__ = synonyms
        cls.__semantic_sql_filters__ = sql_filters
        cls.__semantic_application_context__ = application_context
        cls.__semantic_business_context__ = business_context
        return cls

    return decorator
