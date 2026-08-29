"""Version-adaptive probe: one fixed schema, every semantido release.

Run under each installed release. Detects capabilities at runtime rather than
assuming an API, so it degrades cleanly on versions that predate a feature
instead of crashing. Emits a single JSON line on stdout.

Measures, per release:
  - what the authoring surface can express (grain, concepts, distinctions)
  - how large the exported agent context is
  - which static checks exist
  - which of three fixed joins each release actually catches

No LLM calls. Everything here is deterministic and reproducible offline.
"""

from __future__ import annotations

import inspect
import json
import sys

from sqlalchemy import Column, Date, Numeric, String
from sqlalchemy.orm import DeclarativeBase

import semantido
from semantido import ConceptRegistry, OntologySource, SemanticBase, semantic_table


def approx_tokens(text: str) -> int:
    """Deterministic proxy: 4 chars per token. Comparable across versions."""
    return round(len(text) / 4)


def capabilities() -> dict:
    cap = {}
    sig = inspect.signature(ConceptRegistry.concept)
    cap["grain"] = "grain" in sig.parameters
    cap["distinct_from"] = "distinct_from" in sig.parameters
    cap["external"] = "external" in sig.parameters
    cap["concept_on_table"] = "concept" in inspect.signature(semantic_table).parameters

    import semantido.exporters as ex

    cap["groundings"] = hasattr(ex, "to_groundings_dict")
    cap["skos"] = hasattr(ex, "to_skos_turtle")
    cap["ossie_name"] = (
        "to_ossie_yaml"
        if hasattr(ex, "to_ossie_yaml")
        else ("to_osi_yaml" if hasattr(ex, "to_osi_yaml") else None)
    )
    try:
        import semantido.lint  # noqa: F401

        cap["lint"] = True
    except Exception:
        cap["lint"] = False
    return cap


def available_checks() -> list[str]:
    try:
        import re
        from pathlib import Path

        import semantido.lint as lint

        src = Path(lint.__file__).read_text()
        return sorted(set(re.findall(r"SL0\d{2}", src)))
    except Exception:
        return []


def build(cap: dict):
    class Base(SemanticBase, DeclarativeBase):
        pass

    registry = ConceptRegistry(namespace="secmaster")
    registry.add_source(
        OntologySource(
            name="secmaster", namespace="urn:hikarilabs:secmaster", version="1.0.0"
        )
    )

    def concept(cid, definition, *, grain=None, distinct=None, **kw):
        kwargs = dict(kw)
        if grain and cap["grain"]:
            kwargs["grain"] = grain
        if distinct is not None and cap["distinct_from"]:
            kwargs["distinct_from"] = distinct
        return registry.concept(cid, definition, **kwargs)

    isin = concept(
        "isin",
        "ISO 6166 identifier. Identifies an issue — one security as issued, "
        "irrespective of where it trades.",
        grain="issue",
        synonyms=["ISIN"],
    )
    concept(
        "figi",
        "OpenFIGI identifier. Identifies a listing — one instrument on one "
        "venue. A single issue carries many FIGIs.",
        grain="listing",
        distinct=isin,
        synonyms=["FIGI"],
    )
    concept(
        "ric",
        "Refinitiv Instrument Code. Identifies a listing on one venue, "
        "carrying vendor quote conventions.",
        grain="listing",
        distinct=isin,
        synonyms=["RIC"],
    )

    tbl = (lambda **kw: semantic_table(**kw)) if cap["concept_on_table"] else None

    def deco(description, concept_id, **kw):
        if cap["concept_on_table"]:
            return semantic_table(description=description, concept=concept_id, **kw)
        return semantic_table(description=description, **kw)

    @deco("Bloomberg vendor feed, one row per listing per business date.", "figi")
    class BloombergFeed(Base):
        __tablename__ = "bloomberg_feed"
        figi = Column(String(12), primary_key=True)
        figi_concept = "figi"
        isin = Column(String(12))
        isin_concept = "isin"
        venue = Column(String(4))
        px_last = Column(Numeric(18, 6))
        extract_date = Column(Date, primary_key=True)

    @deco("Refinitiv vendor feed, one row per listing per business date.", "ric")
    class RefinitivFeed(Base):
        __tablename__ = "refinitiv_feed"
        ric = Column(String(20), primary_key=True)
        ric_concept = "ric"
        isin = Column(String(12))
        isin_concept = "isin"
        venue = Column(String(4))
        px_last = Column(Numeric(18, 6))
        extract_date = Column(Date, primary_key=True)

    @deco("ANNA register, the issue-grain golden source.", "isin")
    class AnnaRegister(Base):
        __tablename__ = "anna_register"
        isin = Column(String(12), primary_key=True)
        isin_concept = "isin"
        issuer_name = Column(String(140))
        currency = Column(String(3))
        registered_date = Column(Date)

    _ = (BloombergFeed, RefinitivFeed, AnnaRegister, tbl)
    registry.validate()
    bridge = Base.get_semantic_bridge()
    try:
        layer = bridge.sync_from_models(concept_registry=registry)
    except TypeError:
        layer = bridge.sync_from_models()
    return layer


JOINS = [
    ("figi = ric", "bloomberg_feed.figi = refinitiv_feed.ric"),
    ("isin = ric", "bloomberg_feed.isin = refinitiv_feed.ric"),
    ("isin = isin", "bloomberg_feed.isin = refinitiv_feed.isin"),
]


def probe_joins(layer, cap: dict) -> dict:
    if not cap["lint"]:
        return {name: None for name, _ in JOINS}
    from semantido.generators.semantic_layer import Relationship
    from semantido.lint import lint_layer

    caught = {}
    for name, condition in JOINS:
        base = len(layer.relationships)
        layer.add_relationship(
            Relationship(
                from_table="bloomberg_feed",
                to_table="refinitiv_feed",
                join_condition=condition,
                relationship_type="many_to_many",
                description=name,
            )
        )
        codes = sorted(
            {
                f.code
                for f in lint_layer(layer)
                if f.code in {"SL008", "SL009"} and f.location.endswith(f"[{base}]")
            }
        )
        caught[name] = codes
        del layer.relationships[base:]
    return caught


def concept_dicts(layer) -> list[dict]:
    reg = getattr(layer, "concept_registry", None)
    if reg is None:
        return []
    try:
        concepts = reg.to_dict().get("concepts", {})
    except Exception:
        return []
    if isinstance(concepts, dict):
        return list(concepts.values())
    return list(concepts)


def main() -> None:
    cap = capabilities()
    layer = build(cap)

    from semantido.exporters import to_markdown

    md = to_markdown(layer)
    concepts = concept_dicts(layer)
    result = {
        "version": semantido.__version__,
        "capabilities": {k: v for k, v in cap.items() if k != "ossie_name"},
        "ossie_exporter": cap["ossie_name"],
        "checks": available_checks(),
        "concepts": len(concepts),
        "markdown_tokens": approx_tokens(md),
        "markdown_chars": len(md),
        "grain_declared": sum(1 for c in concepts if c.get("grain")),
        "joins": probe_joins(layer, cap),
    }
    print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"version": "ERROR", "error": f"{type(exc).__name__}: {exc}"}))
        sys.exit(0)
