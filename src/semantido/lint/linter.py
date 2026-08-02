"""Implementation of the semantido static linter. See package docstring."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Union


class Severity(Enum):
    """Finding severity. Errors should gate CI; warnings should not."""

    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class Finding:
    """One linter finding.

    Attributes:
        code: Stable check identifier (``SL001`` ... ``SL008``).
        severity: :class: `Severity` of the finding.
        location: Where the problem lives, as a dotted/physical path
            (e.g. ``"security_master.sql_filters[0]"``).
        message: Human-readable explanation with the offending text.
    """

    code: str
    severity: Severity
    location: str
    message: str

    def __str__(self) -> str:
        return f"{self.code} {self.severity.value:7s} {self.location}: {self.message}"


def _require_sqlglot():
    try:
        import sqlglot  # pylint: disable=C0415

        return sqlglot
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "sqlglot is required for semantido.lint. "
            "Install it with: pip install semantido[lint]"
        ) from exc


# --------------------------------------------------------------------- #
# Schema model shared by the checks                                      #
# --------------------------------------------------------------------- #


def _layer_schema(layer_dict: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Builds ``{table: {column: data_type}}`` from a serialized layer."""
    return {
        table_name: {
            column["name"]: (column.get("data_type") or "").upper()
            for column in table.get("columns", [])
        }
        for table_name, table in layer_dict.get("tables", {}).items()
    }


def _column_concepts(layer_dict: dict[str, Any]) -> dict[tuple[str, str], str]:
    """Builds ``{(table, column): concept_id}`` for concept-bound columns."""
    bound = {}
    for table_name, table in layer_dict.get("tables", {}).items():
        for column in table.get("columns", []):
            if concept := column.get("concept"):
                bound[(table_name, column["name"])] = concept
    return bound


def _parse(sqlglot, sql: str):
    """Parses one expression, rising on any error."""
    return sqlglot.parse_one(
        sql, dialect="postgres", error_level=sqlglot.ErrorLevel.RAISE
    )


def _column_refs(sqlglot, expression):
    """Yields ``(table_or_None, column_name)`` for every column node."""
    for node in expression.find_all(sqlglot.exp.Column):
        yield node.table or None, node.name


# --------------------------------------------------------------------- #
# Individual checks                                                      #
# --------------------------------------------------------------------- #


def _check_sql_filters(sqlglot, layer_dict, schema) -> list[Finding]:
    findings = []
    for table_name, table in layer_dict.get("tables", {}).items():
        own_columns = schema.get(table_name, {})
        for index, sql_filter in enumerate(table.get("sql_filters") or []):
            location = f"{table_name}.sql_filters[{index}]"
            try:
                expression = _parse(sqlglot, sql_filter)
            except Exception as exc:  # pylint: disable=W0703
                findings.append(
                    Finding(
                        "SL001",
                        Severity.ERROR,
                        location,
                        f"not parseable SQL: {sql_filter!r} "
                        f"({str(exc).splitlines()[0]})",
                    )
                )
                continue
            for ref_table, column_name in _column_refs(sqlglot, expression):
                target_table = ref_table or table_name
                if target_table not in schema:
                    findings.append(
                        Finding(
                            "SL002",
                            Severity.ERROR,
                            location,
                            f"references unknown table {target_table!r} "
                            f"in {sql_filter!r}",
                        )
                    )
                elif column_name not in (
                    own_columns if ref_table is None else schema[target_table]
                ):
                    findings.append(
                        Finding(
                            "SL002",
                            Severity.ERROR,
                            location,
                            f"references unknown column {column_name!r} "
                            f"in {sql_filter!r}",
                        )
                    )
    return findings


def _check_joins(
    sqlglot, layer_dict, schema, column_concepts, registry
) -> list[Finding]:
    findings = []
    grains = (
        {
            cid: concept.grain
            for cid, concept in registry.concepts.items()
            if concept.grain
        }
        if registry is not None
        else {}
    )
    for index, relationship in enumerate(layer_dict.get("relationships", [])):
        join_condition = relationship.get("join_condition", "")
        location = f"relationships[{index}]"
        try:
            expression = _parse(sqlglot, join_condition)
        except Exception as exc:  # pylint: disable=W0703
            findings.append(
                Finding(
                    "SL003",
                    Severity.ERROR,
                    location,
                    f"join condition not parseable: {join_condition!r} "
                    f"({str(exc).splitlines()[0]})",
                )
            )
            continue
        for ref_table, column_name in _column_refs(sqlglot, expression):
            if ref_table is None:
                findings.append(
                    Finding(
                        "SL003",
                        Severity.ERROR,
                        location,
                        f"unqualified column {column_name!r} in join "
                        f"condition {join_condition!r} — qualify every "
                        "column as table.column",
                    )
                )
            elif ref_table not in schema:
                findings.append(
                    Finding(
                        "SL003",
                        Severity.ERROR,
                        location,
                        f"unknown table {ref_table!r} in {join_condition!r}",
                    )
                )
            elif column_name not in schema[ref_table]:
                findings.append(
                    Finding(
                        "SL003",
                        Severity.ERROR,
                        location,
                        f"unknown column {ref_table}.{column_name} "
                        f"in {join_condition!r}",
                    )
                )

        # SL008 — grain-mismatched equality: for every `a = b` where both
        # sides are columns bound to concepts with declared grain, the
        # grains must agree verbatim.
        for equality in expression.find_all(sqlglot.exp.EQ):
            sides = []
            for side in (equality.left, equality.right):
                if isinstance(side, sqlglot.exp.Column) and side.table:
                    concept_id = column_concepts.get((side.table, side.name))
                    grain = grains.get(concept_id) if concept_id else None
                    sides.append((side.table, side.name, concept_id, grain))
            if len(sides) == 2 and sides[0][3] and sides[1][3]:
                if sides[0][3] != sides[1][3]:
                    findings.append(
                        Finding(
                            "SL008",
                            Severity.ERROR,
                            location,
                            f"grain-mismatched join: "
                            f"{sides[0][0]}.{sides[0][1]} is "
                            f"{sides[0][2]!r} (grain {sides[0][3]!r}) but "
                            f"{sides[1][0]}.{sides[1][1]} is "
                            f"{sides[1][2]!r} (grain {sides[1][3]!r}) — "
                            "equating identifiers at different grains "
                            "fans out or drops rows",
                        )
                    )
    return findings


_NUMERIC_TYPES = ("INT", "NUMERIC", "DECIMAL", "FLOAT", "DOUBLE", "REAL")
_BOOLEAN_TYPES = ("BOOL",)


def _check_sample_values(layer_dict) -> list[Finding]:
    findings = []
    for table_name, table in layer_dict.get("tables", {}).items():
        for column in table.get("columns", []):
            samples = column.get("sample_values") or []
            data_type = (column.get("data_type") or "").upper()
            location = f"{table_name}.{column['name']}.sample_values"
            for sample in samples:
                text = str(sample).strip()
                if any(t in data_type for t in _NUMERIC_TYPES):
                    try:
                        float(text)
                    except ValueError:
                        findings.append(
                            Finding(
                                "SL004",
                                Severity.WARNING,
                                location,
                                f"sample {sample!r} is not numeric but the "
                                f"column is declared {data_type}",
                            )
                        )
                elif any(t in data_type for t in _BOOLEAN_TYPES):
                    if text.lower() not in (
                        "true",
                        "false",
                        "0",
                        "1",
                        "t",
                        "f",
                    ):
                        findings.append(
                            Finding(
                                "SL004",
                                Severity.WARNING,
                                location,
                                f"sample {sample!r} is not boolean-like but "
                                f"the column is declared {data_type}",
                            )
                        )
    return findings


def _check_synonym_collisions(layer_dict, column_concepts) -> list[Finding]:
    findings = []
    table_claims: dict[str, list[str]] = {}
    column_claims: dict[str, list[tuple[str, Optional[str]]]] = {}
    for table_name, table in layer_dict.get("tables", {}).items():
        for synonym in table.get("synonyms") or []:
            table_claims.setdefault(synonym.strip().lower(), []).append(table_name)
        for column in table.get("columns", []):
            for synonym in column.get("synonyms") or []:
                column_claims.setdefault(synonym.strip().lower(), []).append(
                    (
                        f"{table_name}.{column['name']}",
                        column_concepts.get((table_name, column["name"])),
                    )
                )
    for synonym, table_claimants in sorted(table_claims.items()):
        if len(table_claimants) > 1:
            findings.append(
                Finding(
                    "SL005",
                    Severity.WARNING,
                    "tables",
                    f"synonym {synonym!r} is claimed by multiple tables: "
                    f"{', '.join(sorted(table_claimants))}",
                )
            )
    for synonym, column_claimants in sorted(column_claims.items()):
        if (
            len(column_claimants) > 1
            and len({concept for _, concept in column_claimants}) > 1
        ):
            findings.append(
                Finding(
                    "SL005",
                    Severity.WARNING,
                    "columns",
                    f"synonym {synonym!r} is claimed by columns bound to "
                    "different concepts: "
                    + ", ".join(
                        f"{path} ({concept})" for path, concept in column_claimants
                    ),
                )
            )
    return findings


def _check_undeclared_homonyms(registry) -> list[Finding]:
    if registry is None:
        return []
    from semantido.generators.concept_registry import (  # pylint: disable=C0415
        ConceptRelation,
    )

    findings = []
    for form, concept_ids in registry.find_homonyms().items():
        for i, first in enumerate(concept_ids):
            for second in concept_ids[i + 1 :]:
                declared = any(
                    relation == ConceptRelation.DISTINCT_FROM and target == second
                    for relation, target in registry.concepts[first].relations
                ) or any(
                    relation == ConceptRelation.DISTINCT_FROM and target == first
                    for relation, target in registry.concepts[second].relations
                )
                if not declared:
                    findings.append(
                        Finding(
                            "SL006",
                            Severity.WARNING,
                            f"registry.{first}",
                            f"shares surface form {form!r} with {second!r} "
                            "but no DISTINCT_FROM edge is declared — either "
                            "the homonym is accidental or the distinction "
                            "is undocumented",
                        )
                    )
    return findings


def _check_groundings(layer_dict, schema, registry, groundings) -> list[Finding]:
    from semantido.exporters.groundings_exporter import (  # pylint: disable=C0415
        load_groundings,
    )

    findings = []
    document = load_groundings(groundings)
    for concept_id, entry in document.get("groundings", {}).items():
        for table_name in entry.get("tables", []) or []:
            if table_name not in schema:
                findings.append(
                    Finding(
                        "SL007",
                        Severity.ERROR,
                        f"groundings.{concept_id}",
                        f"anchor table {table_name!r} no longer exists in the layer",
                    )
                )
        for anchor in entry.get("columns", []) or []:
            # rpartition: table names may themselves contain dots
            # (e.g., Kafka topic names like "etd.executions" modeled as
            # tables); only the final segment is the column.
            table_name, _, column_name = anchor.rpartition(".")
            if table_name not in schema or column_name not in schema.get(
                table_name, {}
            ):
                findings.append(
                    Finding(
                        "SL007",
                        Severity.ERROR,
                        f"groundings.{concept_id}",
                        f"anchor column {anchor!r} no longer exists in the layer",
                    )
                )
        recorded = entry.get("definition_checksum")
        if recorded and registry is not None:
            concept = registry.concepts.get(concept_id)
            if concept is None:
                findings.append(
                    Finding(
                        "SL007",
                        Severity.ERROR,
                        f"groundings.{concept_id}",
                        "concept no longer exists in the registry",
                    )
                )
            elif concept.definition_checksum != recorded:
                findings.append(
                    Finding(
                        "SL007",
                        Severity.ERROR,
                        f"groundings.{concept_id}",
                        "definition_checksum drift: the definition changed "
                        "after this grounding was recorded "
                        f"(recorded {recorded}, current "
                        f"{concept.definition_checksum}) — re-review the "
                        "binding and regenerate the groundings file",
                    )
                )
    return findings


# --------------------------------------------------------------------- #
# Entry point                                                            #
# --------------------------------------------------------------------- #


def lint_layer(
    layer,
    groundings: Union[str, dict[str, Any], None] = None,
) -> list[Finding]:
    """Runs all static checks against a semantic layer.

    Args:
        layer: The :class:`~semantido.SemanticLayer` to check. Its
            attached concept registry (if any) powers the homonym,
            checksum-drift, and grain checks.
        groundings: Optional groundings document — a path to a YAML file
            produced by: func:`semantido.exporters.to_groundings_file`, or an
            already-parsed dict. Enables the SL007 staleness check.

    Returns:
        list[Finding]: All findings, errors first, in deterministic order.
    """
    sqlglot = _require_sqlglot()
    layer_dict = layer.to_dict(include_empty=True)
    schema = _layer_schema(layer_dict)
    column_concepts = _column_concepts(layer_dict)
    registry = layer.concept_registry

    findings: list[Finding] = []
    findings += _check_sql_filters(sqlglot, layer_dict, schema)
    findings += _check_joins(sqlglot, layer_dict, schema, column_concepts, registry)
    findings += _check_sample_values(layer_dict)
    findings += _check_synonym_collisions(layer_dict, column_concepts)
    findings += _check_undeclared_homonyms(registry)
    if groundings is not None:
        findings += _check_groundings(layer_dict, schema, registry, groundings)

    return sorted(
        findings, key=lambda f: (f.severity.value, f.code, f.location, f.message)
    )
