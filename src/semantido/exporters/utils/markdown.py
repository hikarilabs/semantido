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

"""Utility module for rendering Markdown content."""


def render_column(col: dict, enriched: bool = True) -> list[str]:
    """Renders a single column as Markdown lines.

    Args:
        col: The column's ``to_dict()`` entry.
        enriched: If False (the *schema* tier), only structural facts are
            rendered: name, type, foreign-key target. If True (the
            *enriched* tier), semantic annotations are added —
            description, concept binding, samples, synonyms, time
            semantics, application rules.
    """
    lines = []
    col_name = col.get("name", "unknown")
    col_type = col.get("data_type", "unknown")
    privacy = col.get("privacy_level", "")
    is_fk = col.get("is_foreign_key", False)
    references = col.get("references", "")

    type_info = f"{col_type}, {privacy}" if (privacy and enriched) else col_type
    line_parts = [f"- **{col_name}** ({type_info})"]
    if is_fk and references:
        line_parts.append(f"ForeignKey → {references}")
    lines.append(" ".join(line_parts))

    if not enriched:
        return lines

    if col_desc := col.get("description"):
        lines.append(f"  - {col_desc}")
    if col_concept := col.get("concept"):
        lines.append(f"  - *Concept*: `{col_concept}`")
    if time_grain := col.get("time_grain"):
        lines.append(f"  - *Time grain*: {time_grain}")
    if col.get("is_time_dimension"):
        lines.append("  - *Secondary time dimension*")
    if sample_values := col.get("sample_values", []):
        lines.append(f"  - *Examples*: {', '.join(map(str, sample_values))}")
    if col_synonyms := col.get("synonyms", []):
        lines.append(f"  - *Synonyms*: {', '.join(col_synonyms)}")
    if application_rules := col.get("application_rules", []):
        for rule in application_rules:
            lines.append(f"  - *Rule*: {rule}")

    return lines


def render_table(
    table: dict,
    concept_refs: list[str] | None = None,
    enriched: bool = True,
) -> list[str]:
    """Renders a single table block as Markdown lines.

    Args:
        table: The table's ``to_dict()`` entry.
        concept_refs: Concept ids realized by this table's columns
            (excluding the table's own ``concept``, which has its own
            line). When provided, a one-line backlink is rendered so a
            reader landing on the table block can jump to the concept
            blocks — the table-side mirror of a concept's
            ``Realized by`` line. Only the bundle render passes this;
            a tables-only export has no concept blocks to link to.
        enriched: If False (the *schema* tier), only structural facts
            are rendered: name, keys, columns with types and FK targets.
            If True (the *enriched* tier), semantic annotations are
            added — description, concept, synonyms, contexts, time
            dimension, default filters.
    """
    lines = []
    table_name = table.get("name", "Unknown")
    schema = table.get("schema", "")
    full_name = f"{schema}.{table_name}" if schema else table_name

    # Each field is a list item: single plain-text newlines are soft
    # breaks in Markdown and render as one run-together paragraph.
    lines.append(f"### {table_name}")
    lines.append(f"- **Full Name**: {full_name}")

    if primary_key := table.get("primary_key"):
        lines.append(f"- **Primary Key**: {', '.join(primary_key)}")
    if unique_keys := table.get("unique_keys"):
        rendered = "; ".join(", ".join(key) for key in unique_keys)
        lines.append(f"- **Unique Keys**: {rendered}")

    if enriched:
        lines.append(
            f"- **Description**: {table.get('description', 'No description available')}"
        )

        if table_concept := table.get("concept"):
            lines.append(f"- **Concept**: `{table_concept}`")
        if synonyms := table.get("synonyms", []):
            lines.append(f"- **Synonyms**: {', '.join(synonyms)}")
        if app_context := table.get("application_context"):
            lines.append(f"- **Application Context**: {app_context}")
        if business_context := table.get("business_context"):
            lines.append(f"- **Business Context**: {business_context.strip()}")
        if time_dimension := table.get("time_dimension"):
            lines.append(
                f"- **Time Dimension**: {time_dimension} — primary time "
                "axis; use for any per-day/month/quarter aggregation"
            )
        if sql_filters := table.get("sql_filters", []):
            lines.append(f"- **Default Filters**: {' AND '.join(sql_filters)}")
        if concept_refs:
            rendered_refs = ", ".join(f"`{ref}`" for ref in concept_refs)
            lines.append(f"- **Realizes concepts**: {rendered_refs}")

    lines.append("")

    if columns := table.get("columns", []):
        lines.append("#### Columns")
        for col in columns:
            lines.extend(render_column(col, enriched=enriched))
        lines.append("")

    lines.append("---\n")
    return lines


def render_relationship(rel: dict) -> list[str]:
    """Renders a single relationship block as Markdown lines."""
    lines = []
    from_table = rel.get("from_table", "unknown")
    to_table = rel.get("to_table", "unknown")

    lines.append(f"### {from_table} → {to_table}")
    lines.append(f"- **Type**: {rel.get('relationship_type', 'unknown')}")
    lines.append(f"- **Join**: {rel.get('join_condition', '')}")
    if rel_desc := rel.get("description"):
        lines.append(f"- **Description**: {rel_desc}")
    lines.append("")
    return lines


#: Human-readable phrasing for concept-to-concept relation edges. An edge
#: ``(BROADER, target)`` reads "target is the broader concept" — matching
#: the ``broader=`` authoring kwarg on ``ConceptRegistry.concept()``.
_RELATION_PHRASES = {
    "same_as": "same as",
    "broader": "broader",
    "narrower": "narrower",
    "related": "related to",
    "distinct_from": "distinct from",
}

#: Human-readable phrasing for concept-to-external mapping relations,
#: read concept-first: "narrower than → <target>" states the concept is
#: narrower than the external target.
_MAPPING_PHRASES = {
    "exact_match": "exact match",
    "close_match": "close match",
    "broader": "broader than",
    "narrower": "narrower than",
    "related": "related to",
}


def render_concept(
    concept_id: str, concept: dict, sources: dict, realized_by: list[str]
) -> list[str]:
    """Renders a single concept block as Markdown lines.

    Args:
        concept_id: The registered concept id.
        concept: The concept's ``to_dict()`` entry.
        sources: The registry's serialized sources, for version pins.
        realized_by: Table / table.column names bound to this concept.

    Returns:
        list: Markdown lines for the concept block.
    """
    lines = [f"### `{concept_id}` — {concept.get('label', '')}"]
    lines.append(f"- **Definition**: {concept.get('definition', '')}")
    if synonyms := concept.get("synonyms"):
        lines.append(f"- **Synonyms**: {', '.join(synonyms)}")
    if realized_by:
        lines.append(f"- **Realized by**: {', '.join(realized_by)}")
    else:
        lines.append("- **Realized by**: — (context only, not bound in this schema)")
    for mapping in concept.get("mappings", []):
        source = sources.get(mapping.get("source", ""), {})
        pin = f"{mapping.get('source', '')}@{source.get('version', '?')}"
        relation_value = mapping.get("relation", "")
        entry = (
            f"- **External**: "
            f"{_MAPPING_PHRASES.get(relation_value, relation_value)} → "
            f"`{mapping.get('target', '')}` [{pin}]"
        )
        if justification := mapping.get("justification"):
            entry += f" — {justification}"
        lines.append(entry)
    for relation in concept.get("relations", []):
        phrase = _RELATION_PHRASES.get(
            relation.get("relation", ""), relation.get("relation", "")
        )
        lines.append(f"- **Relation**: {phrase} → `{relation.get('concept', '')}`")
    lines.append("")
    return lines


def render_disambiguation(
    homonyms: dict, concepts: dict, realized_by: dict
) -> list[str]:
    """Renders the Disambiguation section for colliding surface forms.

    This section is the direct countermeasure to silent lexical
    collisions: identical labels bound to distinct registered meanings
    are surfaced as explicit, cheap-to-attend-to context instead of
    being left for the reader (or the model) to conflate.

    Args:
        homonyms: ``find_homonyms()`` output — surface form -> concept ids.
        concepts: The registry's serialized concepts, for definitions.
        realized_by: concept id -> table / table.column names.

    Returns:
        list: Markdown lines for the Disambiguation section.
    """
    lines = [
        "## Disambiguation\n",
        "The surface forms below are claimed by more than one distinct "
        "concept. Always resolve by concept id, never by label.\n",
    ]
    for form, concept_ids in homonyms.items():
        lines.append(f'### "{form}" — {len(concept_ids)} distinct concepts')
        for concept_id in concept_ids:
            concept = concepts.get(concept_id, {})
            bound = ", ".join(realized_by.get(concept_id, [])) or "not bound here"
            lines.append(f"- `{concept_id}` ({bound}): {concept.get('definition', '')}")
        lines.append(
            "\nDo not treat these as equivalent; do not join or compare "
            "their columns as if they carried the same meaning.\n"
        )
    return lines
