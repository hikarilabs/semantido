import json
from enum import Enum
from typing import Optional
from dataclasses import dataclass, field


class PrivacyLevel(Enum):
    PUBLIC = "public"
    RESTRICTED = "restricted"
    CONFIDENTIAL = "confidential"


class RelationshipType(Enum):
    ONE_TO_MANY = "one-to-many"
    MANY_TO_ONE = "many-to-one"
    MANY_TO_MANY = "many-to-many"


@dataclass
class Column:
    """Represents a database column with semantic information"""

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
    """
    Represents a database table with semantic information.

    It captures both the application and business contexts in which this table is used.
    This aims to disambiguate the meaning of a table using generic words such as Account,
    which can represent different things given the application and/or business context.
    """

    name: str
    description: str
    columns: list[Column]
    primary_key: str
    synonyms: Optional[list[str]] = None
    sql_filters: Optional[list[str]] = None

    # application context in which this table is used
    application_context: Optional[str] = None

    # business context in which this table is used
    business_context: Optional[str] = None


@dataclass
class Relationship:
    """Represents a relationship between tables"""

    from_table: str
    to_table: str
    join_condition: str
    relationship_type: (
        RelationshipType  # Example: "one-to-many", "many-to-one", "many-to-many"
    )
    description: str


@dataclass
class SemanticLayer:
    """Main semantic layer containing all the database application schema context"""

    tables: dict[str, Table] = field(default_factory=dict)
    relationships: list[Relationship] = field(default_factory=list)
    application_glossary: dict[str, str] = field(default_factory=dict)

    def add_table(self, table: Table):
        """Add a table to the semantic layer"""
        self.tables[table.name] = table

    def add_relationship(self, relationship: Relationship):
        """Add a relationship between tables to the semantic layer"""
        self.relationships.append(relationship)

    def to_dict(self) -> dict:
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
                            "privacy_level": column.privacy_level.value
                            if isinstance(column.privacy_level, Enum)
                            else column.privacy_level,
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
                    "relationship_type": relationship.relationship_type.value
                    if isinstance(relationship.relationship_type, Enum)
                    else relationship.relationship_type,
                    "description": relationship.description,
                }
                for relationship in self.relationships
            ],
        }

    def to_json(self):
        """Export semantic layer as a JSON string"""
        return json.dumps(self.to_dict(), indent=4)

    def save_to_file(self, file_path: str):
        """Save semantic layer as a JSON file"""
        with open(file_path, "w") as f:
            json.dump(self.to_dict(), f, indent=4)
