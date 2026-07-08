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


def render_column(col: dict) -> list[str]:
    """Renders a single column as Markdown lines."""
    lines = []
    col_name = col.get("name", "unknown")
    col_type = col.get("data_type", "unknown")
    privacy = col.get("privacy_level", "")
    is_fk = col.get("is_foreign_key", False)
    references = col.get("references", "")

    type_info = f"{col_type}, {privacy}" if privacy else col_type
    line_parts = [f"- **{col_name}** ({type_info})"]
    if is_fk and references:
        line_parts.append(f"ForeignKey → {references}")
    lines.append(" ".join(line_parts))

    if col_desc := col.get("description"):
        lines.append(f"  - {col_desc}")
    if sample_values := col.get("sample_values", []):
        lines.append(f"  - *Examples*: {', '.join(map(str, sample_values))}")
    if col_synonyms := col.get("synonyms", []):
        lines.append(f"  - *Synonyms*: {', '.join(col_synonyms)}")

    return lines


def render_table(table: dict) -> list[str]:
    """Renders a single table block as Markdown lines."""
    lines = []
    table_name = table.get("name", "Unknown")
    schema = table.get("schema", "")
    full_name = f"{schema}.{table_name}" if schema else table_name

    lines.append(f"### {table_name}")
    lines.append(f"**Full Name**: {full_name}")

    if primary_key := table.get("primary_key"):
        lines.append(f"**Primary Key**: {primary_key}")

    lines.append(
        f"**Description**: {table.get('description', 'No description available')}"
    )

    if synonyms := table.get("synonyms", []):
        lines.append(f"**Synonyms**: {', '.join(synonyms)}")
    if app_context := table.get("application_context"):
        lines.append(f"**Application Context**: {app_context}")
    if business_context := table.get("business_context"):
        lines.append(f"**Business Context**: {business_context.strip()}")

    lines.append("\n")

    if columns := table.get("columns", []):
        lines.append("#### Columns")
        for col in columns:
            lines.extend(render_column(col))
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
