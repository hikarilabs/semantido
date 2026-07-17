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

"""Exports a SemanticLayer to the Open Semantic Interchange (OSI) format.

OSI (https://open-semantic-interchange.org, core spec v0.2.x) is a
vendor-neutral YAML interchange format for semantic models, backed by
Snowflake, Databricks, dbt Labs, Salesforce and 50+ other organizations.
This module lets semantido act as an OSI model converter: semantics are
authored code-native next to the SQLAlchemy models (the inner loop) and
emitted as OSI YAML for the wider stack to consume (the outer loop).

Mapping summary::

    SemanticLayer OSI
    -------------            ---
    Table                    dataset (source = schema.table)
    Column                   field (ANSI_SQL expression)
    Relationship             (deduplicated, direction-agnostic)
    application_context      dataset ai_context.instructions
    business_context         dataset ai_context.instructions
    synonyms                 ai_context.synonyms
    time_dimension           field dimension.is_time + PRIMARY marker
    PrivacyLevel             SEMANTIDO custom_extensions (no OSI core field)
    sample_values            SEMANTIDO custom_extensions
    sql_filters              SEMANTIDO custom_extensions
    application_rules        field ai_context.instructions
    application_glossary     model ai_context.instructions
    Table.concept            dataset SEMANTIDO custom_extensions
    Column.concept           field SEMANTIDO custom_extensions
    ConceptRegistry          model SEMANTIDO custom_extensions (subset)

Time-dimension policy

* The table's declared ``time_dimension`` column is flagged
  ``dimension.is_time: true`` and marked as the PRIMARY time axis in
  ``ai_context`` plus an `` SEMANTIDO `` extension (OSI core has no
  primary-axis or grain concept).
* Columns with ``is_time_dimension=True`` are flagged as secondary axes.
* Remaining temporal columns (DATE/TIMESTAMP) are flagged unless their
  name matches the audit-column pattern (created_at, updated_at, ...),
  in which case the dimension block is suppressed and an explicit
  "do not use as a time axis" instruction is emitted instead. This keeps
  the export's signal-to-noise high for agentic consumers.

Usage:

    from semantido.exporters import to_osi_yaml

    layer = MyBase.sync_semantic_layer()
    to_osi_yaml(layer, model_name="core_banking", path="model.osi.yaml")

PyYAML is an optional dependency (``pip install semantido[osi]``);
``to_osi_dict`` works without it.
"""

import json
import re
from typing import Any, Optional

from semantido.generators.semantic_layer import (
    Column,
    PrivacyLevel,
    Relationship,
    RelationshipType,
    SemanticLayer,
    Table,
)

# Must match the `const` in osi-schema.json exactly; the schema pins the
# full version string including pre-release tags.
OSI_SPEC_VERSION = "0.2.0.dev0"
DEFAULT_DIALECT = "ANSI_SQL"
VENDOR = "SEMANTIDO"

#: SemanticLayer normalized types considered temporal.
TEMPORAL_TYPES = frozenset({"DATE", "TIMESTAMP"})

# Column names that are almost always operational/audit timestamps rather
# than business time axes. Overridable per export call.
DEFAULT_AUDIT_PATTERN = re.compile(
    r"(^|_)(created|updated|modified|inserted|deleted|loaded|ingested|"
    r"processed|sync(ed)?|etl)(_at|_on|_ts|_time|_timestamp|_date)?$",
    re.IGNORECASE,
)


def _vendor_extension(payload: dict[str, Any]) -> dict[str, str]:
    """Wraps semantido metadata as a spec-conformant custom extension.

    The OSI schema requires custom extensions to be exactly
    ``{vendor_name: str, data: str}`` where ``data`` is a serialized JSON
    string; flattened keys fail schema validation.
    """
    return {
        "vendor_name": VENDOR,
        "data": json.dumps(payload, sort_keys=True, default=str),
    }


def to_osi_dict(
    semantic_layer: SemanticLayer,
    model_name: str,
    description: Optional[str] = None,
    instructions: Optional[str] = None,
    audit_pattern: re.Pattern = DEFAULT_AUDIT_PATTERN,
) -> dict:
    """Converts a SemanticLayer into an OSI semantic model document.

    Args:
        semantic_layer: The synchronized layer, e.g., from `sync_semantic_layer()`.
        model_name: The OSI `semantic_model` name.
        description: Optional model-level description.
        instructions: Optional model-level `ai_context` instructions.
        audit_pattern: Regex deciding which temporal columns are demoted to
            audit timestamps. Pass `re.compile(r"$^")` to disable demotion.

    Returns:
        dict: The OSI document, ready for YAML/JSON serialization.
    """
    model: dict[str, Any] = {"name": model_name}
    if description:
        model["description"] = description

    ai_context: dict[str, Any] = {}
    ai_bits = [instructions] if instructions else []
    if semantic_layer.application_glossary:
        glossary = "; ".join(
            f"{term}: {meaning}"
            for term, meaning in semantic_layer.application_glossary.items()
        )
        ai_bits.append(f"Glossary — {glossary}")
    if ai_bits:
        ai_context["instructions"] = " ".join(ai_bits)
    if ai_context:
        model["ai_context"] = ai_context

    model_ext: dict[str, Any] = {"exporter": "semantido.exporters.osi"}
    referenced = {
        table.concept for table in semantic_layer.tables.values() if table.concept
    } | {
        column.concept
        for table in semantic_layer.tables.values()
        for column in table.columns
        if column.concept
    }
    if semantic_layer.concept_registry is not None and referenced:
        # Embed only the closure of referenced concepts, so a large
        # organization-wide registry does not bloat every model export.
        model_ext["concept_registry"] = semantic_layer.concept_registry.subset(
            referenced
        ).to_dict()
    model["custom_extensions"] = [_vendor_extension(model_ext)]

    model["datasets"] = [
        _table_to_dataset(table, audit_pattern)
        for table in semantic_layer.tables.values()
    ]

    relationships = _relationships_to_osi(semantic_layer.relationships)
    if relationships:
        model["relationships"] = relationships

    return {"version": OSI_SPEC_VERSION, "semantic_model": [model]}


def to_osi_yaml(
    semantic_layer: SemanticLayer,
    model_name: str,
    path: Optional[str] = None,
    **kwargs,
) -> str:
    """Serializes a SemanticLayer to OSI YAML, optionally writing it to a file.

    Requires PyYAML (``pip install semantido[osi]``).

    Args:
        semantic_layer: The synchronized layer.
        model_name: The OSI `semantic_model` name.
        path: Optional filesystem path to also write the YAML to.
        **kwargs: Forwarded to `to_osi_dict`.

    Returns:
        str: The OSI document as YAML text.
    """
    try:
        import yaml  # pylint: disable=C0415
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "PyYAML is required for OSI YAML export. "
            "Install it with: pip install semantido[osi]"
        ) from exc

    doc = to_osi_dict(semantic_layer, model_name=model_name, **kwargs)
    text = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=88)
    if path is not None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    return text


# --------------------------------------------------------------------------- #
# Tables -> datasets                                                          #
# --------------------------------------------------------------------------- #
def _table_to_dataset(table: Table, audit_pattern: re.Pattern) -> dict:
    dataset: dict[str, Any] = {
        "name": table.name,
        "source": f"{table.schema}.{table.name}" if table.schema else table.name,
    }
    if table.primary_key:
        dataset["primary_key"] = list(table.primary_key)
    if table.unique_keys:
        # OSI Foundation section 6.4 infers relationship cardinality from
        # declared keys; omitting a unique key degrades every relationship
        # targeting those columns to worst-case N:N.
        dataset["unique_keys"] = [list(key) for key in table.unique_keys]
    if table.description:
        dataset["description"] = table.description

    instructions = " ".join(
        bit for bit in (table.application_context, table.business_context) if bit
    )
    ai_context: dict[str, Any] = {}
    if instructions:
        ai_context["instructions"] = instructions
    if table.synonyms:
        ai_context["synonyms"] = table.synonyms
    if ai_context:
        dataset["ai_context"] = ai_context

    dataset_ext: dict[str, Any] = {}
    if table.sql_filters:
        dataset_ext["sql_filters"] = table.sql_filters
    if table.concept:
        dataset_ext["concept"] = table.concept
    if dataset_ext:
        dataset["custom_extensions"] = [_vendor_extension(dataset_ext)]

    dataset["fields"] = [
        _column_to_field(column, table, audit_pattern) for column in table.columns
    ]
    return dataset


def _column_to_field(column: Column, table: Table, audit_pattern: re.Pattern) -> dict:
    field: dict[str, Any] = {
        "name": column.name,
        "expression": {
            "dialects": [{"dialect": DEFAULT_DIALECT, "expression": column.name}]
        },
    }
    if column.description:
        field["description"] = column.description

    is_primary = column.name == table.time_dimension
    is_temporal = column.data_type in TEMPORAL_TYPES
    is_audit = is_temporal and bool(audit_pattern.search(column.name))
    is_time = is_primary or column.is_time_dimension or (is_temporal and not is_audit)

    ai_bits = _build_time_field(field, column, is_primary, is_time, is_audit)
    if column.application_rules:
        ai_bits.extend(column.application_rules)

    ai_context: dict[str, Any] = {}
    if column.synonyms:
        ai_context["synonyms"] = column.synonyms
    if ai_bits:
        ai_context["instructions"] = " ".join(ai_bits)
    if ai_context:
        field["ai_context"] = ai_context

    extension = _build_field_extension(column, is_primary)
    if extension:
        field["custom_extensions"] = [_vendor_extension(extension)]

    return field


def _build_time_field(
    field: dict,
    column: Column,
    is_primary: bool,
    is_time: bool,
    is_audit: bool,
) -> list[str]:
    """Populates the ``dimension`` block and returns time-related ``ai_bits``."""
    ai_bits: list[str] = []
    if is_time:
        field["dimension"] = {"is_time": True}
        if is_primary:
            ai_bits.append("PRIMARY time dimension for this dataset.")
            if column.time_grain:
                ai_bits.append(f"Native grain: {column.time_grain.value}.")
    elif is_audit:
        ai_bits.append(
            "Operational audit timestamp — do not use as a time axis for "
            "business questions."
        )
    return ai_bits


def _build_field_extension(column: Column, is_primary: bool) -> dict[str, Any]:
    """Builds the vendor extension dict for a field (empty dict when nothing to add)."""
    extension: dict[str, Any] = {}
    if column.privacy_level and column.privacy_level != PrivacyLevel.PUBLIC:
        extension["privacy_level"] = column.privacy_level.value
    if column.sample_values:
        extension["sample_values"] = column.sample_values
    if is_primary:
        extension["is_primary_time_dimension"] = True
    if column.time_grain:
        extension["time_grain"] = column.time_grain.value
    if column.concept:
        extension["concept"] = column.concept
    return extension


# --------------------------------------------------------------------------- #
# Relationships                                                               #
# --------------------------------------------------------------------------- #
def _relationships_to_osi(relationships: list[Relationship]) -> list[dict]:
    """Converts relationships, deduplicating the two ORM directions.

    SQLAlchemy emits both sides of a bidirectional relationship (ONE_TO_MANY
    and MANY_TO_ONE). OSI relationships are join definitions, so only one is
    exported per join condition.
    """
    seen: set[frozenset] = set()
    result = []
    for rel in relationships:
        pairs = _parse_join_condition(rel.join_condition)
        key = frozenset(frozenset(pair) for pair in pairs)
        if key in seen:
            continue
        seen.add(key)

        # OSI section 4.4 requires `from` = many/FK side, `to` = one/PK-UK
        # side. SQLAlchemy declares each relationship on the class that owns
        # the attribute, so a parent-declared one-to-many arrives inverted;
        # normalize it here (many-to-one from the FK side is the same edge).
        # This also makes deduplication independent of ORM iteration order.
        from_table, to_table = rel.from_table, rel.to_table
        relationship_type = rel.relationship_type
        if relationship_type is RelationshipType.ONE_TO_MANY:
            from_table, to_table = to_table, from_table
            relationship_type = RelationshipType.MANY_TO_ONE

        from_columns, to_columns = [], []
        for left, right in pairs:
            if _table_of(left) == from_table:
                from_columns.append(_column_of(left))
                to_columns.append(_column_of(right))
            else:
                from_columns.append(_column_of(right))
                to_columns.append(_column_of(left))

        entry: dict[str, Any] = {
            "name": f"{from_table}_to_{to_table}",
            "from": from_table,
            "to": to_table,
            "from_columns": from_columns,
            "to_columns": to_columns,
        }
        if rel.description:
            # The schema has no `description` on relationships; ai_context
            # is the conformant home for join semantics prose.
            entry["ai_context"] = {"instructions": rel.description}
        if relationship_type:
            entry["custom_extensions"] = [
                _vendor_extension({"relationship_type": relationship_type.value})
            ]
        result.append(entry)
    return result


def _parse_join_condition(join_condition: str) -> list[tuple[str, str]]:
    """Parses 'a.b = c.d AND e.f = g.h' into [('a.b', 'c.d'), ('e.f', 'g.h')]."""
    pairs = []
    for clause in join_condition.split(" AND "):
        left, _, right = clause.partition("=")
        pairs.append((left.strip(), right.strip()))
    return pairs


def _table_of(qualified: str) -> str:
    """'schema.table.column' or 'table.column' -> 'table'."""
    parts = qualified.split(".")
    return parts[-2] if len(parts) >= 2 else qualified


def _column_of(qualified: str) -> str:
    """'schema.table.column' -> 'column'."""
    return qualified.split(".")[-1]
