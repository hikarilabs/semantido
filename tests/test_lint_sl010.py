"""Tests for SL010 — DISTINCT_FROM concepts claiming the same exactMatch."""

from sqlalchemy import Column, String
from sqlalchemy.orm import DeclarativeBase

from semantido import ConceptRegistry, OntologySource, SemanticBase, semantic_table
from semantido.generators.concept_registry import close_match, exact_match
from semantido.lint import Severity, lint_layer

FIBO = "https://spec.edmcouncil.org/fibo/ontology/FND/Parties/Parties/Counterparty"
FIBO_OTHER = "https://spec.edmcouncil.org/fibo/ontology/FND/Parties/Parties/Party"


def _layer(*, distinct: bool = True, relation=exact_match, target=FIBO):
    class Base(SemanticBase, DeclarativeBase):
        pass

    registry = ConceptRegistry(namespace="reg")
    registry.add_source(
        OntologySource(
            name="fibo",
            namespace="https://spec.edmcouncil.org/fibo/ontology/",
            version="2024Q3",
        )
    )
    emir = registry.concept(
        "counterparty.emir",
        "Either entity party to a derivative contract (EMIR Article 9).",
        label="Counterparty",
        grain="legal_entity",
        external=exact_match("fibo", FIBO, because="EMIR Art.9 sense"),
    )
    registry.concept(
        "counterparty.mifir",
        "The market-side entity faced in a transaction (MiFIR RTS 22).",
        label="Counterparty",
        grain="legal_entity",
        distinct_from=emir if distinct else None,
        external=relation("fibo", target, because="MiFIR RTS 22 sense"),
    )

    @semantic_table(description="Reports.", concept="counterparty.emir")
    class Report(Base):
        __tablename__ = "report"
        row_id = Column(String(20), primary_key=True)
        emir_lei = Column(String(20))
        emir_lei_concept = "counterparty.emir"
        mifir_lei = Column(String(20))
        mifir_lei_concept = "counterparty.mifir"

    registry.validate()
    return Base.get_semantic_bridge().sync_from_models(concept_registry=registry)


def _sl010(layer):
    return [f for f in lint_layer(layer) if f.code == "SL010"]


def test_sl010_fires_on_shared_exact_match():
    findings = _sl010(_layer())
    assert len(findings) == 1
    assert findings[0].severity is Severity.ERROR
    assert FIBO in findings[0].message
    assert "transitive" in findings[0].message


def test_sl010_silent_for_close_match():
    """closeMatch is not transitive, so a shared target is legitimate."""
    assert not _sl010(_layer(relation=close_match))


def test_sl010_silent_without_distinct_from():
    assert not _sl010(_layer(distinct=False))


def test_sl010_silent_on_different_targets():
    assert not _sl010(_layer(target=FIBO_OTHER))


def test_sl010_reports_each_pair_once():
    findings = _sl010(_layer())
    locations = [f.location for f in findings]
    assert len(locations) == len(set(locations))


def test_sl010_needs_a_registry():
    layer = _layer()
    layer.concept_registry = None
    assert not _sl010(layer)
