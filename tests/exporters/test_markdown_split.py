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

"""Tests for the split-source / combinable-render exporter design:
tables and concepts as separate source-of-truth artifacts, merged only
in the prompt-facing bundle with cross-references resolved."""

import pytest

from semantido.concepts import ConceptRegistry, OntologySource, narrow_match
from semantido.exporters import (
    to_markdown,
    to_markdown_concepts,
    to_markdown_tables,
)
from semantido.generators.semantic_layer import Column, SemanticLayer, Table


def _registry() -> ConceptRegistry:
    registry = ConceptRegistry("hikari.regreport")
    registry.add_source(
        OntologySource(
            name="fibo",
            namespace="https://spec.edmcouncil.org/fibo/ontology/",
            version="2025Q3",
        )
    )
    emir = registry.concept(
        "counterparty.emir",
        label="counterparty",
        definition="Counterparty within the meaning of EMIR Art. 2(8)-(9).",
        external=narrow_match(
            "fibo",
            "FND/Parties/Parties/Counterparty",
            because="EMIR sense is jurisdiction-scoped",
        ),
    )
    registry.concept(
        "counterparty.mifir",
        label="counterparty",
        definition="Entity identified in MiFIR transaction reports (RTS 22).",
        distinct_from=emir,
    )
    registry.concept(
        "settlement_date",
        definition="Date on which the transaction settles.",
    )
    return registry


def _layer(registry: ConceptRegistry | None) -> SemanticLayer:
    layer = SemanticLayer()
    layer.tables["trades"] = Table(
        name="trades",
        description="EMIR trade-state rows.",
        primary_key=["trade_id"],
        concept=None,
        columns=[
            Column(
                name="cpty_lei",
                data_type="VARCHAR",
                description="LEI of the counterparty.",
                privacy_level=None,
                concept="counterparty.emir",
            )
        ],
    )
    layer.concept_registry = registry
    return layer


# ---------------------------------------------------------------- tables-only


def test_tables_only_excludes_concept_sections():
    md = to_markdown_tables(_layer(_registry()))
    assert "## Database Entities" in md
    assert "## Concepts" not in md
    assert "## Disambiguation" not in md


def test_tables_only_keeps_column_bindings_but_no_backlink():
    """Column-level concept ids are physical-layer metadata and stay;
    the aggregated backlink line links to concept blocks, which do not
    exist in a tables-only artifact."""
    md = to_markdown_tables(_layer(_registry()))
    assert "*Concept*: `counterparty.emir`" in md
    assert "**Realizes concepts**" not in md


def test_tables_only_equals_include_tables():
    layer = _layer(_registry())
    assert to_markdown_tables(layer) == to_markdown(layer, include=("tables",))


# -------------------------------------------------------------- concepts-only


def test_concepts_only_is_standalone_document_with_anchors():
    md = to_markdown_concepts(_layer(_registry()))
    assert md.startswith("# Concept Registry")
    assert "## Database Entities" not in md
    # cross-reference into the physical layer without embedding it
    assert "**Realized by**: trades.cpty_lei" in md
    assert "## Disambiguation" in md


def test_concepts_only_bound_scope_uses_subset_closure():
    md = to_markdown_concepts(_layer(_registry()))
    assert "`counterparty.emir`" in md
    assert "`counterparty.mifir`" in md  # travels via distinct_from
    assert "settlement_date" not in md


def test_concepts_only_all_scope_renders_whole_registry():
    md = to_markdown_concepts(_layer(_registry()), scope="all")
    assert "`settlement_date`" in md
    assert "context only, not bound in this schema" in md


def test_concepts_only_without_registry_degrades_gracefully():
    md = to_markdown_concepts(_layer(None))
    assert "No concept registry is attached" in md


def test_invalid_scope_raises():
    with pytest.raises(ValueError):
        to_markdown_concepts(_layer(_registry()), scope="everything")


# -------------------------------------------------------------------- bundle


def test_bundle_carries_backlink_line():
    md = to_markdown(_layer(_registry()))
    assert "- **Realizes concepts**: `counterparty.emir`" in md


def test_backlink_excludes_table_own_concept():
    registry = _registry()
    layer = _layer(registry)
    layer.tables["trades"].concept = "counterparty.emir"
    md = to_markdown(layer)
    # the table's own concept has its dedicated line ...
    assert "- **Concept**: `counterparty.emir`" in md
    # ... and is not repeated in the backlink (no other column concepts
    # remain, so the backlink line is absent entirely)
    assert "**Realizes concepts**" not in md


def test_bundle_is_tables_plus_concepts():
    """The bundle contains every content line of both single-artifact
    renders (headers differ; the backlink line is bundle-only)."""
    layer = _layer(_registry())

    def content(md: str) -> list[str]:
        """Lines from the first '## ' section on — skips each document's
        own title and preamble, which legitimately differ."""
        lines = md.splitlines()
        first = next(i for i, line in enumerate(lines) if line.startswith("## "))
        return lines[first:]

    bundle = to_markdown(layer)
    for line in content(to_markdown_tables(layer)):
        assert line in bundle
    for line in content(to_markdown_concepts(layer)):
        assert line in bundle


def test_include_validation():
    layer = _layer(_registry())
    with pytest.raises(ValueError):
        to_markdown(layer, include=())
    with pytest.raises(ValueError):
        to_markdown(layer, include=("tables", "vibes"))


def test_include_order_is_canonical():
    layer = _layer(_registry())
    assert to_markdown(layer, include=("concepts", "tables")) == to_markdown(layer)


# ---------------------------------------------------------------- tier system


def _timed_layer() -> SemanticLayer:
    """A layer exercising every enrichment signal from example 03."""
    layer = _layer(_registry())
    table = layer.tables["trades"]
    table.time_dimension = "trade_date"
    table.sql_filters = ["status = 'LIVE'"]
    table.columns.append(
        Column(
            name="trade_date",
            data_type="DATE",
            description="Business date of the trade.",
            privacy_level=None,
            is_time_dimension=True,
        )
    )
    table.columns.append(
        Column(
            name="created_at",
            data_type="TIMESTAMP",
            description="Audit timestamp.",
            privacy_level=None,
            is_time_dimension=True,
            application_rules=["do not use as a time axis"],
        )
    )
    layer.application_glossary["UTI"] = "Unique Trade Identifier."
    return layer


def test_schema_tier_is_structure_only():
    md = to_markdown(_timed_layer(), include=("schema",))
    assert "- **trade_date** (DATE)" in md
    assert "- **Primary Key**: trade_id" in md
    assert "**Description**" not in md
    assert "*Concept*" not in md
    assert "**Time Dimension**" not in md
    assert "## Glossary" not in md


def test_enriched_tier_emits_example03_signals():
    """The five signals the 03 experiment appended by hand are now
    first-class exporter output."""
    md = to_markdown(_timed_layer(), include=("schema", "enriched"))
    assert "- **Time Dimension**: trade_date — primary time axis" in md
    assert "- **Default Filters**: status = 'LIVE'" in md
    assert "*Secondary time dimension*" in md
    assert "*Rule*: do not use as a time axis" in md
    assert "## Glossary (1 terms)" in md and "**UTI**" in md


def test_enriched_requires_schema():
    with pytest.raises(ValueError):
        to_markdown(_timed_layer(), include=("enriched",))
    with pytest.raises(ValueError):
        to_markdown(_timed_layer(), include=("enriched", "concepts"))


def test_tables_alias_expands_to_schema_plus_enriched():
    layer = _timed_layer()
    assert to_markdown(layer, include=("tables",)) == to_markdown(
        layer, include=("schema", "enriched")
    )
    assert to_markdown_tables(layer) == to_markdown(layer, include=("tables",))


def test_schema_helper_matches_include():
    from semantido.exporters import to_markdown_schema

    layer = _timed_layer()
    assert to_markdown_schema(layer) == to_markdown(layer, include=("schema",))


def test_schema_plus_concepts_skips_backlinks():
    """Backlinks are enriched-tier annotations; a schema+concepts render
    has no annotation layer to carry them."""
    md = to_markdown(_timed_layer(), include=("schema", "concepts"))
    assert "## Concepts" in md
    assert "**Realizes concepts**" not in md


def test_full_bundle_unchanged_by_default():
    layer = _timed_layer()
    assert to_markdown(layer) == to_markdown(
        layer, include=("schema", "enriched", "concepts")
    )


# --------------------------------------------- registry-alone catalog exports


def test_concepts_export_from_bare_registry():
    """Catalog-upload path: no layer required, whole registry by default."""
    md = to_markdown_concepts(_registry())
    assert md.startswith("# Concept Registry")
    assert "`counterparty.emir`" in md
    assert "`settlement_date`" in md  # scope defaults to "all" for a bare registry
    assert "context only, not bound in this schema" in md
    assert "## Disambiguation" in md


def test_skos_turtle_from_bare_registry():
    from semantido.exporters import to_skos_turtle

    ttl = to_skos_turtle(_registry())
    assert "@prefix skos:" in ttl
    assert ":scheme a skos:ConceptScheme" in ttl
    assert ":counterparty.emir a skos:Concept" in ttl
    assert 'skos:prefLabel "counterparty"' in ttl
    # SKOS-aligned external mapping resolved against the source namespace
    assert (
        "skos:broadMatch <https://spec.edmcouncil.org/fibo/ontology/"
        "FND/Parties/Parties/Counterparty>"
    ) in ttl
    # distinct_from: custom predicate plus a plain-text warning
    assert "smtdo:distinctFrom :counterparty.mifir" in ttl
    assert "skos:editorialNote" in ttl and "Deliberate homonym" in ttl


def test_skos_turtle_base_uri_override_and_layer_input():
    from semantido.exporters import to_skos_turtle

    layer = _layer(_registry())
    ttl = to_skos_turtle(layer, base_uri="https://hikarilabs.ai/concepts/")
    assert "@prefix : <https://hikarilabs.ai/concepts/> ." in ttl


def test_skos_turtle_requires_a_registry():
    from semantido.exporters import to_skos_turtle

    with pytest.raises(ValueError):
        to_skos_turtle(_layer(None))
