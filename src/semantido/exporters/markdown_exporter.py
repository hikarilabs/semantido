"""Exports a SemanticLayer to Markdown format."""

from semantido.generators.semantic_layer import SemanticLayer
from semantido.exporters.utils.markdown import (
    render_concept,
    render_disambiguation,
    render_relationship,
    render_table,
)


def _concept_sections(layer: SemanticLayer) -> list[str]:
    """Builds the Concepts and Disambiguation sections, if applicable.

    Mirrors the OSI exporter's embedding rule: only the ``subset()``
    closure of concepts actually referenced by tables or columns is
    rendered, so an organization-wide registry does not bloat every
    schema export. The closure follows concept relations, which is what
    carries a bound concept's ``distinct_from`` homonym partner into the
    export even when that partner is unrealized in this schema.

    Args:
        layer: The SemanticLayer instance being exported.

    Returns:
        list: Markdown lines, empty when no registry or no bindings.
    """
    registry = layer.concept_registry
    if registry is None:
        return []
    referenced = {table.concept for table in layer.tables.values() if table.concept} | {
        column.concept
        for table in layer.tables.values()
        for column in table.columns
        if column.concept
    }
    if not referenced:
        return []

    scoped_registry = registry.subset(referenced)
    scoped = scoped_registry.to_dict()
    concepts = scoped.get("concepts", {})
    sources = scoped.get("sources", {})

    realized_by: dict[str, list[str]] = {}
    for table in layer.tables.values():
        if table.concept:
            realized_by.setdefault(table.concept, []).append(table.name)
        for column in table.columns:
            if column.concept:
                realized_by.setdefault(column.concept, []).append(
                    f"{table.name}.{column.name}"
                )

    lines = [
        f"## Concepts ({len(concepts)} in scope)\n",
        "Business concepts realized by this schema. The concept id is the "
        "authoritative reference; labels may collide (see Disambiguation).\n",
    ]
    for concept_id, concept in concepts.items():
        lines.extend(
            render_concept(
                concept_id, concept, sources, realized_by.get(concept_id, [])
            )
        )

    if homonyms := scoped_registry.find_homonyms():
        lines.extend(render_disambiguation(homonyms, concepts, realized_by))
    return lines


def to_markdown(layer: SemanticLayer, include_empty: bool = False):
    """
    Converts the semantic layer into a structured Markdown document.
    Optimized for LLM understanding and natural language to SQL generation.

    Args:
        layer: The SemanticLayer instance to export.
        include_empty: If False (default), omits null and empty collection values.

    Returns:
        str: A Markdown string representing the semantic layer.
    """
    data = layer.to_dict(include_empty=include_empty)
    tables = list(data.get("tables", {}).values())
    relationships = data.get("relationships", [])

    lines: list[str] = [
        "# Semantic Layer\n",
        "Machine-readable database schema for natural language queries\n",
        f"## Database Entities ({len(tables)} tables)\n",
    ]

    for table in tables:
        lines.extend(render_table(table))

    if relationships:
        lines.append(f"## Relationships ({len(relationships)} connections)\n")
        for rel in relationships:
            lines.extend(render_relationship(rel))

    lines.extend(_concept_sections(layer))

    total_columns = sum(len(t.get("columns", [])) for t in tables)
    lines += [
        "## Summary",
        f"- **Total Tables**: {len(tables)}",
        f"- **Total Columns**: {total_columns}",
        f"- **Total Relationships**: {len(relationships)}",
    ]

    return "\n".join(lines)


def to_markdown_table(layer: SemanticLayer, include_empty: bool = False) -> str:
    """
    Exports the semantic layer as a Markdown document.

    Args:
        layer: The SemanticLayer instance to export.
        include_empty: If False (default), omits null and empty collection values.

    Returns:
        str: A Markdown string representing the semantic layer.
    """
    data = layer.to_dict(include_empty=include_empty)
    lines: list[str] = ["# Semantic Layer\n"]

    for table_name, table in data.get("tables", {}).items():
        lines.append(f"## {table_name}\n")
        if desc := table.get("description"):
            lines.append(f"{desc}\n")

        columns = table.get("columns", [])
        if columns:
            lines.append("| Column | Type | Description | Privacy |")
            lines.append("| ------ | ---- | ----------- | ------- |")
            for col in columns:
                lines.append(
                    f"| {col.get('name', '')} "
                    f"| {col.get('data_type', '')} "
                    f"| {col.get('description', '')} "
                    f"| {col.get('privacy_level', '')} |"
                )
        lines.append("")

    relationships = data.get("relationships", [])
    if relationships:
        lines.append("## Relationships\n")
        lines.append("| From | To | Type | Join Condition |")
        lines.append("| ---- | -- | ---- | -------------- |")
        for rel in relationships:
            lines.append(
                f"| {rel.get('from_table', '')} "
                f"| {rel.get('to_table', '')} "
                f"| {rel.get('relationship_type', '')} "
                f"| `{rel.get('join_condition', '')}` |"
            )

    if concept_lines := _concept_sections(layer):
        lines.append("")
        lines.extend(concept_lines)

    return "\n".join(lines)


def to_markdown_file(
    layer: SemanticLayer, file_path: str, include_empty: bool = False, table=False
) -> None:
    """
    Writes the semantic layer to a Markdown file.

    Args:
        layer: The SemanticLayer instance to export.
        file_path: Destination path for the Markdown file.
        include_empty: If False (default), omits null and empty collection values.
        table: if True exports the semantic layer in a table Markdown format
    """
    with open(file_path, "w", encoding="utf-8") as f:
        if table:
            f.write(to_markdown_table(layer, include_empty=include_empty))
        else:
            f.write(to_markdown(layer, include_empty=include_empty))
