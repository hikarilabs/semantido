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

"""Extracts and synchronizes semantic metadata from SQLAlchemy models into a unified layer."""

from typing import Type

from sqlalchemy import (
    DateTime,
    Date,
)

from semantido.generators.semantic_layer import (
    SemanticLayer,
    Column,
    Table,
    Relationship,
    RelationshipType,
)
from semantido.generators.utils import check_grain_supported_by_type

from semantido.generators.utils.sqlalchemy_mapping import (
    map_sqlalchemy_type,
    build_join_condition,
    extract_column_metadata,
    resolve_foreign_key,
    extract_table_metadata,
)


class SQLAlchemySemanticBridge:
    """
    Bridge between SQLAlchemy models and the semantic layer.

    This class serves as the extraction engine that inspects SQLAlchemy's internal
    registry to generate a structured `SemanticLayer`. It handles the conversion of
    SQL types to normalized types, builds join conditions for relationships, and
    retrieves semantic metadata attached via decorators.
    """

    def __init__(self, base):
        self.base = base
        self.semantic_layer = SemanticLayer()
        self._model_registry: dict[str, Type] = {}

    def get_semantic_layer(self) -> SemanticLayer:
        """
        Retrieves the current semantic layer instance.

        Returns:
            SemanticLayer: The object containing extracted table and relationship metadata.
        """
        return self.semantic_layer

    def sync_from_models(self) -> SemanticLayer:
        """
        Extracts schema and semantic information from all mapped models.

        This method clears any previously cached metadata and performs a full scan
        of the SQLAlchemy registry to rebuild the semantic layer.

        Returns:
            SemanticLayer: The fully populated semantic layer.
        """
        self.semantic_layer.tables.clear()
        self.semantic_layer.relationships.clear()
        self._model_registry.clear()

        # Get all mapped classes
        for mapper in self.base.registry.mappers:
            clazz = mapper.class_
            table_name = str(mapper.persist_selectable.name)

            # Add the current mapped table to the model registry
            self._model_registry[table_name] = clazz

            try:
                # Extract table information
                table = self._extract_table(clazz, mapper)
                self.semantic_layer.add_table(table)

                # Extract table relationships
                relationships = self._extract_relationships(clazz, mapper)
                for relationship in relationships:
                    self.semantic_layer.add_relationship(relationship)

            except Exception as exc:
                raise RuntimeError(
                    f"Failed to extract semantic metadata for model "
                    f"'{clazz.__name__}' (table: '{table_name}')"
                ) from exc

        return self.semantic_layer

    @staticmethod
    def _extract_table(clazz: Type, mapper) -> Table:
        """
        Transforms an SQLAlchemy mapped class into a semantic Table definition.

        Args:
            clazz: The Python class representing the model.
            mapper: The SQLAlchemy Mapper object containing low-level schema info.

        Returns:
            Table: A semantic representation of the table and its metadata.
        """
        table_name = str(mapper.persist_selectable.name)
        schema = (
            str(mapper.persist_selectable.schema)
            if mapper.persist_selectable.schema
            else None
        )
        meta = extract_table_metadata(clazz, table_name)

        # time dimension if declared must be of a Date or DateTime type
        time_dimension = meta["time_dimension"]
        if time_dimension is not None:
            if time_dimension not in mapper.columns:
                raise ValueError(
                    f"{clazz.__name__} time dimension: {time_dimension} "
                    f"must be a column in the table"
                )

            if not isinstance(mapper.columns[time_dimension].type, (Date, DateTime)):
                raise ValueError(
                    f"{clazz.__name__} time dimension: {time_dimension} "
                    f"must be of a Date or DateTime type"
                )

        primary_keys = [key.name for key in mapper.primary_key]
        primary_key = primary_keys[0] if primary_keys else None

        columns = []

        for name, prop in mapper.columns.items():
            name = str(name)
            column = SQLAlchemySemanticBridge._extract_column(clazz, name, prop)
            if name == meta["time_dimension"]:
                column.is_time_dimension = True
            columns.append(column)

        return Table(
            name=table_name,
            description=meta["description"],
            columns=columns,
            primary_key=primary_key,
            schema=schema,
            synonyms=meta["synonyms"],
            sql_filters=meta["sql_filters"],
            application_context=meta["application_context"],
            business_context=meta["business_context"],
            time_dimension=meta["time_dimension"],
        )

    @staticmethod
    def _extract_column(clazz: Type, column_name: str, prop) -> Column:
        """
        Extracts semantic metadata and schema info for a specific column.

        Time metadata contract:
            <col>._is_time_dimension: bool marks a (secondary) business time axis
            The table PRIMARY axis is declared once on the table decorator, and it's
            applied by _extract_table
            <col>_time_grain accepts a TimeGrain enum, and declaring a grain lower than
            the table e.g., HOUR on a DATE column will emit a UserWarning

        Args:
            clazz: The model class where the column is defined.
            column_name: The name of the column attribute.
            prop: The SQLAlchemy column metadata or property.

        Returns:
            Column: The semantic Column object.
        """
        meta = extract_column_metadata(clazz, column_name)
        data_type = map_sqlalchemy_type(prop.type)
        is_fk, references = resolve_foreign_key(prop)

        # value check for time grain for durration inconsistencies
        if meta["time_grain"] is not None:
            check_grain_supported_by_type(
                clazz, column_name, meta["time_grain"], prop.type
            )

        return Column(
            name=column_name,
            data_type=data_type,
            description=meta["description"],
            privacy_level=meta["privacy_level"],
            sample_values=meta["sample_values"],
            synonyms=meta["synonyms"],
            is_foreign_key=is_fk,
            references=references,
            application_rules=meta["application_rules"],
            is_time_dimension=meta["is_time_dimension"],
            time_grain=meta["time_grain"],
        )

    @staticmethod
    def _extract_relationships(clazz, mapper) -> list[Relationship]:
        """Inspects an SQLAlchemy mapped class and its mapper to extract
         semantic relationship metadata.

        This method iterates through all relationships defined on the SQLAlchemy model,
        identifying the target tables, determining the cardinality (One-to-Many vs. Many-to-One),
        builds the SQL join conditions, and retrieves any custom descriptions defined on the class.

        Args:
            clazz: The SQLAlchemy model class to inspect.
            mapper: The SQLAlchemy Mapper object associated with the class.

        Returns:
            list: A list of Relationship objects representing the semantic links to other tables.
        """

        _direction_map = {
            "ONETOMANY": RelationshipType.ONE_TO_MANY,
            "MANYTOONE": RelationshipType.MANY_TO_ONE,
            "ONETOONE": RelationshipType.ONE_TO_ONE,
            "MANYTOMANY": RelationshipType.MANY_TO_MANY,
        }

        relationships = []
        for relationship_name, relationship_meta in mapper.relationships.items():
            target = relationship_meta.mapper
            target_table = str(target.persist_selectable.name)
            source_table = str(mapper.persist_selectable.name)

            direction_name = relationship_meta.direction.name

            relationship_type = _direction_map.get(relationship_meta.direction.name)
            if relationship_type is None:
                raise ValueError(
                    f"Unknown relationship direction '{direction_name}' "
                    f"for relationship '{relationship_name}' on '{source_table}'"
                )

            join_condition = build_join_condition(relationship_meta)

            description = getattr(
                clazz,
                f"{relationship_name}_relationship_description",
                f"Relationship between {source_table} and {target_table}",
            )

            relationships.append(
                Relationship(
                    from_table=source_table,
                    to_table=target_table,
                    join_condition=join_condition,
                    relationship_type=relationship_type,
                    description=description,
                )
            )

        return relationships
