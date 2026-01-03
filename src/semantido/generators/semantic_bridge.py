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
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    Date,
    Text,
    Numeric,
)

from semantido.generators.semantic_layer import (
    SemanticLayer,
    Column,
    Table,
    Relationship,
    PrivacyLevel,
    RelationshipType,
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
            table_name = mapper.persist_selectable.name

            # Add the current mapped table to the model registry
            self._model_registry[table_name] = clazz

            # Extract table information
            table = self._extract_table(clazz, mapper)
            self.semantic_layer.add_table(table)

            # Extract table relationships
            relationships = self._extract_relationships(clazz, mapper)
            for relationship in relationships:
                self.semantic_layer.add_relationship(relationship)

        return self.semantic_layer

    @staticmethod
    def _extract_table(clazz: Type, mapper) -> Table:
        """
        Transforms a SQLAlchemy mapped class into a semantic Table definition.

        Args:
            clazz: The Python class representing the model.
            mapper: The SQLAlchemy Mapper object containing low-level schema info.

        Returns:
            Table: A semantic representation of the table and its metadata.
        """

        table_name = mapper.persist_selectable.name

        description = getattr(clazz, "__semantic_description__", f"Table: {table_name}")
        synonyms = getattr(clazz, "__semantic_synonyms__", [])
        sql_filters = getattr(clazz, "__semantic_sql_filters__", [])
        application_context = getattr(clazz, "__semantic_application_context__", None)
        business_context = getattr(clazz, "__semantic_business_context__", None)

        primary_keys = [key.name for key in mapper.primary_key]
        primary_key = primary_keys[0] if primary_keys else None

        columns = []

        for name, prop in mapper.columns.items():
            column = SQLAlchemySemanticBridge._extract_column(clazz, name, prop)
            columns.append(column)

        return Table(
            name=table_name,
            description=description,
            columns=columns,
            primary_key=primary_key,
            synonyms=synonyms,
            sql_filters=sql_filters,
            application_context=application_context,
            business_context=business_context,
        )

    @staticmethod
    def _extract_column(clazz: Type, column_name: str, prop) -> Column:
        """
        Extracts semantic metadata and schema info for a specific column.

        Args:
            clazz: The model class where the column is defined.
            column_name: The name of the column attribute.
            prop: The SQLAlchemy column metadata or property.

        Returns:
            Column: The semantic Column object.
        """
        sql_column_meta = prop

        data_type = SQLAlchemySemanticBridge._map_sql_alchemy_type(sql_column_meta.type)
        description = getattr(
            clazz, f"{column_name}_description", f"Column: {column_name}"
        )
        privacy_level = getattr(
            clazz, f"{column_name}_privacy_level", PrivacyLevel.PUBLIC
        )
        sample_values = getattr(clazz, f"{column_name}_sample_values", None)
        synonyms = getattr(clazz, f"{column_name}_synonyms", [])
        application_rules = getattr(clazz, f"{column_name}_application_rules", [])

        # FK
        foreign_keys = len(sql_column_meta.foreign_keys) > 0
        references = None
        if foreign_keys:
            fk = list(sql_column_meta.foreign_keys)[0]
            references = f"{fk.column.table.name}.{fk.column.name}"

        return Column(
            name=column_name,
            data_type=data_type,
            description=description,
            privacy_level=privacy_level,
            sample_values=sample_values,
            synonyms=synonyms,
            is_foreign_key=foreign_keys,
            references=references,
            application_rules=application_rules,
        )

    @staticmethod
    def _extract_relationships(clazz, mapper) -> list[Relationship]:
        """Inspects a SQLAlchemy mapped class and its mapper to extract
         semantic relationship metadata.

        This method iterates through all relationships defined on the SQLAlchemy model,
        identifying the target tables, determining the cardinality (One-to-Many vs Many-to-One),
        builds the SQL join conditions, and retrieves any custom descriptions defined on the class.

        Args:
            clazz: The SQLAlchemy model class to inspect.
            mapper: The SQLAlchemy Mapper object associated with the class.

        Returns:
            list: A list of Relationship objects representing the semantic links to other tables.
        """

        relationships = []
        for relationship_name, relationship_meta in mapper.relationships.items():
            target = relationship_meta.mapper
            target_table = target.persist_selectable.name
            source_table = mapper.persist_selectable.name

            if relationship_meta.uselist:
                relationship_type = RelationshipType.ONE_TO_MANY
            else:
                relationship_type = RelationshipType.MANY_TO_ONE

            join_condition = SQLAlchemySemanticBridge._build_join_condition(
                relationship_meta
            )

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

    @staticmethod
    def _map_sql_alchemy_type(sql_type) -> str:
        """
        Maps SQLAlchemy types to Postgres types.

        Args:
            sql_type: The SQLAlchemy type instance

        Returns:
            str: A Postgres standardized type name (e.g., "INTEGER", "VARCHAR").
        """
        type_mapping = {
            String: "VARCHAR",
            Text: "TEXT",
            Integer: "INTEGER",
            Float: "FLOAT",
            Numeric: "DECIMAL",
            Boolean: "BOOLEAN",
            DateTime: "TIMESTAMP",
            Date: "DATE",
        }

        for sqlalchemy_type, pg_type in type_mapping.items():
            if isinstance(sql_type, sqlalchemy_type):
                return pg_type

        return str(sql_type)

    @staticmethod
    def _build_join_condition(relationship_meta) -> str:
        """Builds the join condition string for a given relationship metadata.

        Examples:
            If you have a relationship between a users table and a posts table where
            posts.user_id references users.id, the method returns:
            "users.id = posts.user_id"

            If the relationship involves multiple columns (a composite key), the method joins
            them with AND. For example, if a sales table joins a products table on both
            store_id and product_id the method returns:
            "products.store_id = sales.store_id AND products.product_id = sales.product_id"

        Args:
            relationship_meta (RelationshipMeta):
            The relationship metadata given by SQLAlchemy models.

        Returns:
            str: The join condition string for the given relationship metadata.

        """
        local_cols = []
        remote_cols = []

        for local, remote in relationship_meta.local_remote_pairs:
            local_cols.append(f"{local.table.name}.{local.name}")
            remote_cols.append(f"{remote.table.name}.{remote.name}")

        conditions = [
            f"{local} = {remote}" for local, remote in zip(local_cols, remote_cols)
        ]

        return " AND ".join(conditions)
