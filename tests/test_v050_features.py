"""Tests for the v0.5.0 features: grain, groundings, lint, and fixes.

Covers:
* ``Concept.grain`` — authoring, serialization (omit-if-unset), markdown
  and SKOS emission.
* ``subset()`` aliasing fix — mutating a subset must not corrupt the
  parent registry.
* SKOS mapping URI construction — no more raw namespace+target
  concatenation.
* Groundings exporter — extraction, round-trip, format guard.
* ``semantido.lint`` — every check SL001-SL008 firing and staying quiet.
"""

import pytest
from sqlalchemy import Column, Date, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase

from semantido import SemanticBase, semantic_table
from semantido.exporters import (
    load_groundings,
    to_groundings_dict,
    to_groundings_file,
    to_markdown_concepts,
    to_skos_turtle,
)
from semantido.generators.concept_registry import ConceptRegistry, exact_match
from semantido.generators.semantic_layer import Relationship, RelationshipType
from semantido.lint import Finding, Severity, lint_layer


# --------------------------------------------------------------------- #
# Fixture: a miniature vendor cross-reference domain                     #
# --------------------------------------------------------------------- #


def build_domain(
    *,
    bad_filter: bool = False,
    bad_join_column: bool = False,
    grain_mismatch_join: bool = False,
    bad_sample: bool = False,
    colliding_synonyms: bool = False,
    undeclared_homonym: bool = False,
):
    """Builds a registry + layer, optionally seeded with lintable defects."""
    registry = ConceptRegistry(namespace="xref_test")
    from semantido.generators.concept_registry import OntologySource

    registry.add_source(
        OntologySource(
            name="iso6166",
            namespace="urn:iso:std:iso:6166",
            version="2021",
        )
    )

    isin = registry.concept(
        "isin",
        "Issue-level instrument identifier.",
        grain="issue",
        external=exact_match("iso6166", "iso6166:isin"),
    )
    registry.concept(
        "figi",
        "Venue-level instrument identifier.",
        grain="listing",
        distinct_from=isin,
    )
    if undeclared_homonym:
        registry.concept(
            "trade_ticker",
            "Exchange trading symbol.",
            synonyms=["ticker"],
        )
        registry.concept(
            "vendor_ticker",
            "Vendor display symbol.",
            synonyms=["ticker"],
        )

    class Base(SemanticBase, DeclarativeBase):
        """Isolated registry for this test."""

    @semantic_table(
        description="Golden records.",
        synonyms=["master", "golden copy"] if colliding_synonyms else ["master"],
        sql_filters=[
            "status = 'ACTIVE' unless asked" if bad_filter else "status = 'ACTIVE'"
        ],
    )
    class Master(Base):
        __tablename__ = "master"
        id = Column(Integer, primary_key=True)
        isin = Column(String(12))
        isin_concept = "isin"
        status = Column(String(10))
        status_sample_values = ["ACTIVE"]
        confidence = Column(Numeric(4, 3))
        confidence_sample_values = ["high"] if bad_sample else ["0.97"]

    @semantic_table(
        description="Vendor feed.",
        synonyms=["feed", "golden copy"] if colliding_synonyms else ["feed"],
    )
    class Feed(Base):
        __tablename__ = "feed"
        figi = Column(String(12), primary_key=True)
        figi_concept = "figi"
        isin = Column(String(12))
        isin_concept = "isin"
        load_date = Column(Date)
        load_date_is_time_dimension = True
        load_date_time_grain = "day"

    layer = Base.get_semantic_bridge().sync_from_models(concept_registry=registry)

    if grain_mismatch_join:
        join = "feed.figi = master.isin"
    elif bad_join_column:
        join = "feed.isin = master.primary_isin"
    else:
        join = "feed.isin = master.isin"
    layer.add_relationship(
        Relationship(
            from_table="feed",
            to_table="master",
            join_condition=join,
            relationship_type=RelationshipType.MANY_TO_ONE,
            description="Feed rows resolve to golden records.",
        )
    )
    return registry, layer


def codes(findings: list[Finding]) -> set[str]:
    return {finding.code for finding in findings}


# --------------------------------------------------------------------- #
# Grain                                                                  #
# --------------------------------------------------------------------- #


class TestGrain:
    def test_grain_authoring_and_serialization(self):
        registry, _ = build_domain()
        assert registry.concepts["isin"].grain == "issue"
        serialized = registry.to_dict()["concepts"]
        assert serialized["isin"]["grain"] == "issue"

    def test_grain_omitted_when_unset(self):
        registry = ConceptRegistry()
        registry.concept("thing", "A thing.")
        assert "grain" not in registry.to_dict()["concepts"]["thing"]

    def test_grain_in_markdown(self):
        _, layer = build_domain()
        markdown = to_markdown_concepts(layer, scope="bound")
        assert "- **Grain**: issue" in markdown
        assert "- **Grain**: listing" in markdown

    def test_grain_in_skos(self):
        registry, _ = build_domain()
        turtle = to_skos_turtle(registry)
        assert 'smtdo:grain "issue"' in turtle
        assert 'smtdo:grain "listing"' in turtle


# --------------------------------------------------------------------- #
# subset() aliasing fix                                                  #
# --------------------------------------------------------------------- #


class TestSubsetIsolation:
    def test_subset_mutation_does_not_leak_to_parent(self):
        registry, _ = build_domain()
        subset = registry.subset({"isin"})
        subset.concepts["isin"].synonyms = ["mutated"]
        subset.concepts["isin"].mappings.append(exact_match("iso6166", "iso6166:other"))
        subset.concepts["isin"].relations.append(
            next(iter(subset.concepts["isin"].relations), None)
            or (list(registry.concepts["figi"].relations)[0])
        )
        assert registry.concepts["isin"].synonyms != ["mutated"]
        assert len(registry.concepts["isin"].mappings) == 1

    def test_subset_still_closes_over_relations(self):
        registry, _ = build_domain()
        subset = registry.subset({"figi"})
        # figi is DISTINCT_FROM isin, so isin must be pulled in
        assert set(subset.concepts) == {"figi", "isin"}


# --------------------------------------------------------------------- #
# SKOS mapping URI construction                                          #
# --------------------------------------------------------------------- #


class TestSkosMappingUri:
    def test_prefix_form_target_is_stripped_and_joined(self):
        registry, _ = build_domain()
        turtle = to_skos_turtle(registry)
        assert "<urn:iso:std:iso:6166/isin>" in turtle
        # the pre-fix malformed concatenation must be gone
        assert "urn:iso:std:iso:6166iso6166" not in turtle

    def test_absolute_target_passes_through(self):
        registry = ConceptRegistry()
        from semantido.generators.concept_registry import OntologySource

        registry.add_source(
            OntologySource(
                name="fibo",
                namespace="https://spec.edmcouncil.org/fibo/ontology/",
                version="1",
            )
        )
        registry.concept(
            "x",
            "X.",
            external=exact_match("fibo", "https://spec.edmcouncil.org/fibo/ontology/X"),
        )
        turtle = to_skos_turtle(registry)
        assert "<https://spec.edmcouncil.org/fibo/ontology/X>" in turtle

    def test_slash_terminated_namespace_gets_no_double_separator(self):
        registry = ConceptRegistry()
        from semantido.generators.concept_registry import OntologySource

        registry.add_source(
            OntologySource(
                name="fibo",
                namespace="https://spec.edmcouncil.org/fibo/ontology/",
                version="1",
            )
        )
        registry.concept("y", "Y.", external=exact_match("fibo", "FBC/Y"))
        turtle = to_skos_turtle(registry)
        assert "<https://spec.edmcouncil.org/fibo/ontology/FBC/Y>" in turtle


# --------------------------------------------------------------------- #
# Groundings exporter                                                    #
# --------------------------------------------------------------------- #


class TestGroundings:
    def test_extraction_shape(self):
        _, layer = build_domain()
        document = to_groundings_dict(layer)
        assert document["format"] == "semantido/groundings"
        assert document["namespace"] == "xref_test"
        isin = document["groundings"]["isin"]
        assert isin["columns"] == ["feed.isin", "master.isin"]
        assert "definition_checksum" in isin

    def test_registry_yaml_stays_meaning_only(self):
        registry, _ = build_domain()
        serialized = registry.to_dict()
        text = str(serialized)
        # No physical anchor should ever appear in the meaning artifact
        assert "master.isin" not in text
        assert "feed.figi" not in text

    def test_file_round_trip(self, tmp_path):
        _, layer = build_domain()
        path = tmp_path / "groundings.yaml"
        to_groundings_file(layer, str(path))
        document = load_groundings(str(path))
        assert document["groundings"]["figi"]["columns"] == ["feed.figi"]

    def test_load_rejects_foreign_documents(self):
        with pytest.raises(ValueError, match="Not a semantido groundings"):
            load_groundings({"format": "something/else"})


# --------------------------------------------------------------------- #
# Lint                                                                   #
# --------------------------------------------------------------------- #


class TestLint:
    def test_clean_layer_produces_no_findings(self):
        _, layer = build_domain()
        assert lint_layer(layer) == []

    def test_sl001_prose_in_filter(self):
        _, layer = build_domain(bad_filter=True)
        findings = lint_layer(layer)
        assert "SL001" in codes(findings)
        assert any("master.sql_filters[0]" == f.location for f in findings)

    def test_sl002_unknown_column_in_filter(self):
        registry, layer = build_domain()
        layer.tables["master"].sql_filters = ["state = 'ACTIVE'"]
        findings = lint_layer(layer)
        assert "SL002" in codes(findings)

    def test_sl003_unknown_join_column(self):
        _, layer = build_domain(bad_join_column=True)
        findings = lint_layer(layer)
        assert "SL003" in codes(findings)

    def test_sl004_sample_value_type_mismatch(self):
        _, layer = build_domain(bad_sample=True)
        findings = lint_layer(layer)
        sl004 = [f for f in findings if f.code == "SL004"]
        assert sl004 and sl004[0].severity is Severity.WARNING
        assert "master.confidence.sample_values" == sl004[0].location

    def test_sl005_table_synonym_collision(self):
        _, layer = build_domain(colliding_synonyms=True)
        findings = lint_layer(layer)
        assert "SL005" in codes(findings)

    def test_sl006_undeclared_homonym(self):
        _, layer = build_domain(undeclared_homonym=True)
        findings = lint_layer(layer)
        sl006 = [f for f in findings if f.code == "SL006"]
        assert sl006 and "ticker" in sl006[0].message

    def test_sl006_quiet_when_distinct_from_declared(self):
        # isin/figi share no surface forms here, but the base domain has
        # figi DISTINCT_FROM isin declared — no SL006 either way.
        _, layer = build_domain()
        assert "SL006" not in codes(lint_layer(layer))

    def test_sl007_stale_grounding_anchor(self, tmp_path):
        _, layer = build_domain()
        path = tmp_path / "groundings.yaml"
        to_groundings_file(layer, str(path))
        # simulate schema drift: drop a grounded column
        layer.tables["feed"].columns = [
            c for c in layer.tables["feed"].columns if c.name != "figi"
        ]
        findings = lint_layer(layer, groundings=str(path))
        sl007 = [f for f in findings if f.code == "SL007"]
        assert sl007 and "feed.figi" in sl007[0].message

    def test_sl007_checksum_drift(self, tmp_path):
        registry, layer = build_domain()
        path = tmp_path / "groundings.yaml"
        to_groundings_file(layer, str(path))
        # simulate meaning drift: the definition changes post-recording
        registry.concepts["isin"].definition = "Something else entirely."
        findings = lint_layer(layer, groundings=str(path))
        assert any(
            f.code == "SL007" and "checksum drift" in f.message for f in findings
        )

    def test_sl008_grain_mismatched_join(self):
        _, layer = build_domain(grain_mismatch_join=True)
        findings = lint_layer(layer)
        sl008 = [f for f in findings if f.code == "SL008"]
        assert len(sl008) == 1
        assert sl008[0].severity is Severity.ERROR
        assert "'issue'" in sl008[0].message and "'listing'" in sl008[0].message

    def test_sl008_quiet_on_same_grain(self):
        _, layer = build_domain()  # joins isin (issue) to isin (issue)
        assert "SL008" not in codes(lint_layer(layer))

    def test_sl008_quiet_when_grain_undeclared(self):
        registry, layer = build_domain(grain_mismatch_join=True)
        registry.concepts["figi"].grain = None
        assert "SL008" not in codes(lint_layer(layer))

    def test_findings_are_deterministically_ordered(self):
        _, layer = build_domain(
            bad_filter=True, bad_sample=True, colliding_synonyms=True
        )
        first = lint_layer(layer)
        second = lint_layer(layer)
        assert first == second
        assert [f.severity for f in first] == sorted(
            (f.severity for f in first), key=lambda s: s.value
        )
