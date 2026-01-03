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

"""Defines the data structures for the semantic representation of the database schema."""

import json
from enum import Enum
from typing import Optional
from dataclasses import dataclass, field


class PrivacyLevel(Enum):
    """
    Defines the data sensitivity levels for columns.

    Used to inform downstream consumers (like LLMs or BI tools) about
    the accessibility and security requirements of specific data points.
    """

    PUBLIC = "public"
    RESTRICTED = "restricted"
    CONFIDENTIAL = "confidential"


class RelationshipType(Enum):
    """
    Specifies the cardinality of a database relationship.

    Helps in determining how to construct joins and aggregate data.
    """

    ONE_TO_MANY = "one-to-many"
    MANY_TO_ONE = "many-to-one"
    MANY_TO_MANY = "many-to-many"


@dataclass
class Column:
    # pylint: disable=R0902
    """
    Represents a database column with enriched semantic metadata.

    Attributes:
        name: The physical name of the column in the database.
        data_type: The normalized data type (e.g., VARCHAR, INTEGER).
        description: A human-readable explanation of the column's content.
        privacy_level: The sensitivity classification of the data.
        sample_values: A list of example data points to help clarify the content.
        synonyms: Alternative terms for the column name.
        is_foreign_key: Boolean flag indicating if this column links to another table.
        references: The target table and column (format: 'table.column') if a foreign key.
        application_rules: Specific business logic or constraints applied to this column.
    """

    name: str
    data_type: str
    description: str
    privacy_level: PrivacyLevel
    sample_values: Optional[list[str]] = None
    synonyms: Optional[list[str]] = None
    is_foreign_key: bool = False
    references: Optional[str] = None  # Format: table.column
    application_rules: Optional[list[str]] = None


@dataclass
class Table:
    # pylint: disable=R0902
    """
    Represents a database table enriched with semantic and contextual information.

    By capturing application and business contexts, this class helps disambiguate
    entities that might have generic names but specific roles in different domains.

    Attributes:
        name: The physical name of the table in the database.
        description: A human-readable explanation of the table's purpose.
        columns: A list of Column objects belonging to this table.
        primary_key: The name of the primary key column.
        synonyms: Alternative names for the entity represented by the table.
        sql_filters: Default SQL fragments for filtering or security.
        application_context: The functional area of the application using this table.
        business_context: The business domain or logic this table serves.
    """

    name: str
    description: str
    columns: list[Column]
    primary_key: str
    synonyms: Optional[list[str]] = None
    sql_filters: Optional[list[str]] = None
    application_context: Optional[str] = None
    business_context: Optional[str] = None


@dataclass
class Relationship:
    """
    Represents a semantic link between two database tables.

    Attributes:
        from_table: The name of the source table.
        to_table: The name of the target table.
        join_condition: The SQL fragment defining how the tables link.
        relationship_type: The cardinality of the link.
        description: A plain-language explanation of the relationship logic.
    """

    from_table: str
    to_table: str
    join_condition: str
    relationship_type: (
        RelationshipType  # Example: "one-to-many", "many-to-one", "many-to-many"
    )
    description: str


@dataclass
class SemanticLayer:
    """
    The central repository for all semantic metadata extracted from the database.

    This class serves as the final output of the synchronization process,
    containing structured information about tables, their relationships,
    and a global application glossary. It provides methods for serializing
    this metadata to JSON for use by external tools or LLMs.
    """

    tables: dict[str, Table] = field(default_factory=dict)
    relationships: list[Relationship] = field(default_factory=list)
    application_glossary: dict[str, str] = field(default_factory=dict)

    def add_table(self, table: Table):
        """
        Registers a new table definition in the semantic layer.

        Args:
            table: The Table object containing columns and semantic metadata.
        """
        self.tables[table.name] = table

    def add_relationship(self, relationship: Relationship):
        """
        Registers a relationship between two tables in the semantic layer.

        Args:
            relationship: The Relationship object defining the join logic and cardinality.
        """
        self.relationships.append(relationship)

    def to_dict(self) -> dict:
        """
        Converts the entire semantic layer into a nested dictionary structure.

        Returns:
            dict: A dictionary representation suitable for JSON serialization.
        """
        return {
            "tables": {
                name: {
                    "name": table.name,
                    "description": table.description,
                    "primary_key": table.primary_key,
                    "synonyms": table.synonyms,
                    "sql_filters": table.sql_filters,
                    "application_context": table.application_context,
                    "business_context": table.business_context,
                    "columns": [
                        {
                            "name": column.name,
                            "data_type": column.data_type,
                            "description": column.description,
                            "privacy_level": (
                                column.privacy_level.value
                                if isinstance(column.privacy_level, Enum)
                                else column.privacy_level
                            ),
                            "sample_values": column.sample_values,
                            "synonyms": column.synonyms,
                            "is_foreign_key": column.is_foreign_key,
                            "references": column.references,
                            "application_rules": column.application_rules,
                        }
                        for column in table.columns
                    ],
                }
                for name, table in self.tables.items()
            },
            "relationships": [
                {
                    "from_table": relationship.from_table,
                    "to_table": relationship.to_table,
                    "join_condition": relationship.join_condition,
                    "relationship_type": (
                        relationship.relationship_type.value
                        if isinstance(relationship.relationship_type, Enum)
                        else relationship.relationship_type
                    ),
                    "description": relationship.description,
                }
                for relationship in self.relationships
            ],
        }

    def to_json(self) -> str:
        """
        Exports the entire semantic layer as a formatted JSON string.

        Returns:
            str: Indented JSON string representing the semantic layer.
        """
        return json.dumps(self.to_dict(), indent=4)

    def save_to_file(self, file_path: str):
        """
        Serializes and saves the semantic layer to a JSON file.

        Args:
            file_path: The filesystem path where the JSON file will be created.
        """
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=4)
