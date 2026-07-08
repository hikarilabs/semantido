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

"""Defines the data structures for the semantic representation of the database schema."""

import json
from enum import Enum
from typing import Optional, Any
from dataclasses import dataclass, field
from typing_extensions import deprecated


class PrivacyLevel(Enum):
    """
    Defines the data sensitivity levels for columns.

    Used to inform downstream consumers (like LLMs or BI tools) about
    the accessibility and security requirements of specific data points.
    """

    PUBLIC = "public"
    INTERNAL = "internal"
    RESTRICTED = "restricted"
    CONFIDENTIAL = "confidential"


class TimeGrain(Enum):
    """Native resolution of a time dimension — the floor for GROUP BY."""

    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"

    def __lt__(self, other: "TimeGrain") -> bool:
        order = list(type(self))
        return order.index(self) < order.index(other)


class RelationshipType(Enum):
    """
    Specifies the cardinality of a database relationship.

    Helps in determining how to construct joins and aggregate data.
    """

    ONE_TO_ONE = "one-to-one"
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
        application_rules: Specific business logic or constraints are applied to this column.
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

    # OSI Extended Field
    is_time_dimension: Optional[bool] = False
    time_grain: Optional[TimeGrain] = None


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
        schema: The database schema to which the table belongs.
        synonyms: Alternative names for the entity represented by the table.
        sql_filters: Default SQL fragments for filtering or security.
        application_context: The functional area of the application using this table.
        business_context: The business domain or logic this table serves.
    """

    name: str
    description: str
    columns: list[Column]
    primary_key: Optional[str]
    schema: Optional[str] = None
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

    tables: dict[str, Table] = field(default_factory=dict[str, Table])
    relationships: list[Relationship] = field(default_factory=list[Relationship])
    application_glossary: dict[str, str] = field(default_factory=dict[dict, str])

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

    @staticmethod
    def _remove_empty_values(obj):
        """
        Recursively removes keys with None, empty lists, or empty dicts from a dictionary.

        This helps produce cleaner JSON output by eliminating null and empty collection values.

        Args:
            obj: A dictionary, list, or primitive value to clean.

        Returns:
            The cleaned object where an empty value is removed.
        """
        if isinstance(obj, dict):
            return {
                k: SemanticLayer._remove_empty_values(v)
                for k, v in obj.items()
                if v is not None and v != [] and v != {}
            }

        if isinstance(obj, list):
            return [
                SemanticLayer._remove_empty_values(item)
                for item in obj
                if item is not None and item != [] and item != {}
            ]

        return obj

    def to_dict(self, include_empty: bool = False) -> dict[str, Any]:
        """
        Converts the entire semantic layer into a nested dictionary structure.

        Args:
            include_empty: If False (default), removes null and empty collection values.
                          If True, includes all values as-is.

        Returns:
            dict: A dictionary representation suitable for JSON serialization.
        """
        raw_dict = {
            "tables": {
                name: {
                    "name": table.name,
                    "description": table.description,
                    "primary_key": table.primary_key,
                    "schema": table.schema,
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

        if include_empty:
            return raw_dict

        return self._remove_empty_values(raw_dict)

    @deprecated(
        "Use to_json() from semantido.exporters. Will be removed in future versions."
    )
    def to_json(self, include_empty: bool = False) -> str:
        """
        Exports the entire semantic layer as a formatted JSON string.

        Args:
            include_empty: If False (default), removes null and empty collection values.
                          If True, includes all values as-is.

        Returns:
            str: Indented JSON string representing the semantic layer.
        """
        return json.dumps(self.to_dict(include_empty=include_empty), indent=4)

    @deprecated(
        "Use to_file() from semantido.exporters. Will be removed in future versions."
    )
    def to_file(self, file_path: str, include_empty: bool = False):
        """
        Serializes and saves the semantic layer to a JSON file.

        Args:
            file_path: The filesystem path where the JSON file will be created.
            include_empty: If False (default), removes null and empty collection values.
                          If True, includes all values as-is.
        """
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(include_empty=include_empty), f, indent=4)
