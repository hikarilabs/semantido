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

"""SQLAlchemy-specific utility functions for type mapping and join condition building."""

from typing import Type

from sqlalchemy import String, Integer, Float, Boolean, DateTime, Date, Text, Numeric

from semantido.generators.utils.time_grain import normalize_time_grain

##### Table Metadata Extraction


def extract_table_metadata(clazz: Type, table_name: str) -> dict:
    """
    Reads semantic metadata attributes from a mapped class.

    Args:
        clazz: The Python class representing the model.
        table_name: The physical table name, used as a fallback description.

    Returns:
        dict: A dictionary of semantic metadata fields.
    """
    return {
        "description": getattr(
            clazz, "__semantic_description__", f"Table: {table_name}"
        ),
        "synonyms": getattr(clazz, "__semantic_synonyms__", None) or [],
        "sql_filters": getattr(clazz, "__semantic_sql_filters__", None) or [],
        "application_context": getattr(clazz, "__semantic_application_context__", None),
        "business_context": getattr(clazz, "__semantic_business_context__", None),
        "time_dimension": getattr(clazz, "__semantic_time_dimension__", None),
        "concept": getattr(clazz, "__semantic_concept__", None),
    }


##### Column Metadata Extraction


def extract_column_metadata(clazz: Type, column_name: str) -> dict:
    """
    Reads semantic metadata attributes from a mapped class for a specific column.

    Args:
        clazz: The model class where the column is defined.
        column_name: The name of the column attribute.

    Returns:
        dict: A dictionary of semantic metadata fields for the column.
    """
    return {
        "description": getattr(
            clazz, f"{column_name}_description", f"Column: {column_name}"
        ),
        "privacy_level": getattr(clazz, f"{column_name}_privacy_level", None),
        "sample_values": getattr(clazz, f"{column_name}_sample_values", None),
        "synonyms": getattr(clazz, f"{column_name}_synonyms", []),
        "application_rules": getattr(clazz, f"{column_name}_application_rules", []),
        "is_time_dimension": bool(
            getattr(clazz, f"{column_name}_is_time_dimension", False)
        ),
        "time_grain": normalize_time_grain(
            clazz, column_name, getattr(clazz, f"{column_name}_time_grain", None)
        ),
        "concept": getattr(clazz, f"{column_name}_concept", None),
    }


def resolve_foreign_key(sql_column_meta) -> tuple[bool, str | None]:
    """
    Resolves foreign key information from an SQLAlchemy column.

    Args:
        sql_column_meta: The SQLAlchemy column metadata.

    Returns:
        tuple: (is_foreign_key, references) where references is 'table.column' or None.
    """
    is_fk = len(sql_column_meta.foreign_keys) > 0
    if not is_fk:
        return False, None

    fk = list(sql_column_meta.foreign_keys)[0]
    table_ref = (
        f"{fk.column.table.schema}.{fk.column.table.name}"
        if fk.column.table.schema
        else fk.column.table.name
    )
    return True, f"{table_ref}.{fk.column.name}"


def map_sqlalchemy_type(sql_type) -> str:
    """
    Maps SQLAlchemy types to Postgres types.

    Args:
        sql_type: The SQLAlchemy type instance.

    Returns:
        str: A Postgres standardized type name (e.g., "INTEGER", "VARCHAR").
    """
    type_mapping = {
        Text: "TEXT",
        String: "VARCHAR",
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


def build_join_condition(relationship_meta) -> str:
    """Builds the join condition string for a given relationship metadata.

    Examples:
        "users.id = posts.user_id"
        "public.users.id = blog.posts.user_id"
        "products.store_id = sales.store_id AND products.product_id = sales.product_id"

    Args:
        relationship_meta: The relationship metadata given by SQLAlchemy.

    Returns:
        str: The join condition string for the given relationship metadata.

    Raises:
        ValueError: If no local/remote column pairs are found.
    """
    local_cols = []
    remote_cols = []

    for local, remote in relationship_meta.local_remote_pairs:
        local_table = (
            f"{local.table.schema}.{local.table.name}"
            if local.table.schema
            else local.table.name
        )
        remote_table = (
            f"{remote.table.schema}.{remote.table.name}"
            if remote.table.schema
            else remote.table.name
        )
        local_cols.append(f"{local_table}.{local.name}")
        remote_cols.append(f"{remote_table}.{remote.name}")

    conditions = [
        f"{local} = {remote}" for local, remote in zip(local_cols, remote_cols)
    ]

    if not conditions:
        raise ValueError(
            f"Could not determine join condition for relationship "
            f"'{relationship_meta.key}': no local/remote column pairs found. "
            "Check if the relationship uses a secondary table or a custom primary join."
        )

    return " AND ".join(conditions)
