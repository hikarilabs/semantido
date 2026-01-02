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

from typing import Optional


def semantic_table(
    description: str,
    synonyms: Optional[list[str]] = None,
    sql_filters: Optional[list[str]] = None,
    application_context: Optional[str] = None,
    business_context: Optional[str] = None,
):
    """
    Decorator for adding semantic information to SQLAlchemy models

    Usage:
        @semantic_table(
            description="User information and login profile",
            synonyms: ["user profile", "client"],
            application_context: "Registered users on the platform")
        class User(Base)
        ...
    """

    def decorator(cls):
        cls.__semantic_description__ = description
        cls.__semantic_synonyms__ = synonyms
        cls.__semantic_sql_filters__ = sql_filters
        cls.__semantic_application_context__ = application_context
        cls.__semantic_business_context__ = business_context
        return cls

    return decorator
