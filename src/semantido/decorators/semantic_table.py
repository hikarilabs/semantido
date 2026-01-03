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
