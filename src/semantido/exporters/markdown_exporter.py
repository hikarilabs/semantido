"""Exports a SemanticLayer to Markdown format."""

from semantido.generators.semantic_layer import SemanticLayer
from semantido.exporters.utils.markdown import (
    render_table,
    render_relationship,
)


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
