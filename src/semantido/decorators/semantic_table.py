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
    time_dimension: Optional[str] = None,
    concept: Optional[str] = None,
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
        time_dimension: Name of the column that is the table's primary
            business time axis. Equivalent to setting
            ``__semantic_time_dimension__`` on the class body; passing both
            with different values raises ``ValueError``.
        concept: Identifier of a registered business concept this table
            realizes. Resolved against the ``ConceptRegistry`` passed to
            ``sync_semantic_layer`` — sync fails if the id is unknown.

    Examples:
        ```python
        @semantic_table(
            description="User information and login profile",
            synonyms=["user profile", "client"],
            application_context="Registered users on the platform",
            time_dimension="created_at")
        class User(Base):
            __tablename__ = "users"
            id = Column(Integer, primary_key=True)
            created_at = Column(DateTime)
        ```
    """

    def decorator(cls):
        if time_dimension is not None:
            # Only a dunder set directly on this class body conflicts;
            # values inherited from a mixin or base are overridable.
            own = cls.__dict__.get("__semantic_time_dimension__")
            if own is not None and own != time_dimension:
                raise ValueError(
                    f"{cls.__name__}: time_dimension={time_dimension!r} on "
                    f"@semantic_table conflicts with "
                    f"__semantic_time_dimension__ = {own!r} on the class body"
                )
            cls.__semantic_time_dimension__ = time_dimension

        if concept is not None:
            own_concept = cls.__dict__.get("__semantic_concept__")
            if own_concept is not None and own_concept != concept:
                raise ValueError(
                    f"{cls.__name__}: concept={concept!r} on "
                    f"@semantic_table conflicts with "
                    f"__semantic_concept__ = {own_concept!r} on the class body"
                )
            cls.__semantic_concept__ = concept

        cls.__semantic_description__ = description
        cls.__semantic_synonyms__ = synonyms
        cls.__semantic_sql_filters__ = sql_filters
        cls.__semantic_application_context__ = application_context
        cls.__semantic_business_context__ = business_context
        return cls

    return decorator
