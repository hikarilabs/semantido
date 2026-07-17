"""Tests for the Markdown exporter's rendering behavior."""

from semantido.exporters import to_markdown
from semantido.generators.semantic_layer import Column, SemanticLayer, Table


def _layer() -> SemanticLayer:
    layer = SemanticLayer()
    layer.tables["accounts"] = Table(
        name="accounts",
        description="Customer accounts.",
        synonyms=["accounts"],
        business_context="Balances are end-of-day.",
        application_context="Core banking.",
        primary_key=["account_id"],
        columns=[
            Column(
                name="account_id",
                data_type="INTEGER",
                description=None,
                privacy_level=None,
            )
        ],
    )
    return layer


def test_table_header_fields_are_list_items():
    """Every header field must be its own Markdown list item.

    Plain consecutive lines are soft breaks in Markdown and render as a
    single run-together paragraph; list items always break.
    """
    md = to_markdown(_layer())
    for field in (
        "- **Full Name**: accounts",
        "- **Primary Key**: account_id",
        "- **Description**: Customer accounts.",
        "- **Synonyms**: accounts",
        "- **Application Context**: Core banking.",
        "- **Business Context**: Balances are end-of-day.",
    ):
        assert f"\n{field}\n" in md


def test_no_bare_header_field_lines():
    """No header field may appear as a bare (non-list-item) line."""
    md = to_markdown(_layer())
    for line in md.splitlines():
        stripped = line.strip()
        if stripped.startswith("**") and stripped.rstrip(":").endswith("**") is False:
            raise AssertionError(f"bare header field line would soft-wrap: {line!r}")
