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

"""Tests for the Markdown exporter's concept tier and Disambiguation
section — the countermeasure that turns silent lexical collisions
(the EMIR/MiFIR counterparty homonym) into explicit rendered context."""

from semantido.concepts import (
    ConceptRegistry,
    OntologySource,
    exact_match,
    narrow_match,
)
from semantido.exporters import to_markdown
from semantido.exporters.markdown_exporter import to_markdown_table
from semantido.generators.semantic_layer import Column, SemanticLayer, Table


def _registry() -> ConceptRegistry:
    """The counterparty homonym plus one unrelated, unreferenced concept."""
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
        external=exact_match("fibo", "FND/DatesAndTimes/SettlementDate"),
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


def test_no_registry_renders_no_concept_sections():
    md = to_markdown(_layer(None))
    assert "## Concepts" not in md
    assert "## Disambiguation" not in md


def test_column_binding_rendered_inline():
    md = to_markdown(_layer(_registry()))
    assert "*Concept*: `counterparty.emir`" in md


def test_concepts_section_embeds_subset_closure_only():
    """Referenced closure only: the distinct_from partner travels with
    the export; the unreferenced concept does not."""
    md = to_markdown(_layer(_registry()))
    assert "## Concepts (2 in scope)" in md
    assert "`counterparty.emir`" in md
    # unrealized homonym partner reached via the distinct_from edge
    assert "`counterparty.mifir`" in md
    assert "not bound in this schema" in md
    # unreferenced, unrelated concept must not bloat the export
    assert "settlement_date" not in md


def test_mapping_rendered_with_pin_and_justification():
    md = to_markdown(_layer(_registry()))
    assert "[fibo@2025Q3]" in md
    assert "EMIR sense is jurisdiction-scoped" in md


def test_disambiguation_section_surfaces_the_homonym():
    md = to_markdown(_layer(_registry()))
    assert "## Disambiguation" in md
    assert '"counterparty" — 2 distinct concepts' in md
    assert "Do not treat these as equivalent" in md
    assert "Always resolve by concept id" in md


def test_realized_by_lists_binding_sites():
    md = to_markdown(_layer(_registry()))
    assert "**Realized by**: trades.cpty_lei" in md


def test_table_variant_carries_concept_sections():
    md = to_markdown_table(_layer(_registry()))
    assert "## Concepts (2 in scope)" in md
    assert "## Disambiguation" in md


def test_table_level_concept_rendered():
    registry = _registry()
    layer = _layer(registry)
    layer.tables["trades"].concept = "counterparty.emir"
    md = to_markdown(layer)
    assert "- **Concept**: `counterparty.emir`" in md
    assert "**Realized by**: trades, trades.cpty_lei" in md
