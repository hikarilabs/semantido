from typing import Type, Text

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
    Extracts schema information and keeps the semantic layer in sync when underlying model changes.
    """

    def __init__(self, base):
        """

        :param base:
        """
        self.base = base
        self.semantic_layer = SemanticLayer()
        self._model_registry: dict[str, Type] = {}

    def sync_from_models(self) -> SemanticLayer:
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

    def _extract_table(self, clazz: Type, mapper) -> Table:
        """

        :param clazz:
        :param mapper:
        :return:
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
            column = self._extract_column(clazz, name, prop)
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

    def _extract_column(self, clazz: Type, column_name: str, prop) -> Column:
        """

        :param clazz:
        :param name: Column Name
        :param prop: Column Metadata
        :return:
        """
        sql_column_meta = prop

        data_type = SQLAlchemySemanticBridge._map_SQLAlchemy_type(sql_column_meta.type)
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

    def _extract_relationships(self, clazz, mapper) -> list[Relationship]:
        """
        Extracts relationship information between tables
        :param clazz:
        :param mapper:
        :return:
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
    def _map_SQLAlchemy_type(sql_type) -> str:
        """Utility function mapping SQLAlchemy types to PG type"""
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
    def _build_join_condition(relationship_meta):
        local_cols = []
        remote_cols = []

        for local, remote in relationship_meta.local_remote_pairs:
            local_cols.append(f"{local.table.name}.{local.name}")
            remote_cols.append(f"{remote.table.name}.{remote.name}")

        conditions = [
            f"{local} = {remote}" for local, remote in zip(local_cols, remote_cols)
        ]

        return " AND ".join(conditions)

    def get_semantic_layer(self) -> SemanticLayer:
        """Getter function for the current semantic layer"""
        return self.semantic_layer
