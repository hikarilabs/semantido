"""Path B: a simulated AtScale-SML-to-semantido bridge, with fault injection.

HONEST LABEL: this does not run AtScale. It simulates the *characteristic
behaviors* of a generation pipeline deriving a concept registry from SML
models built on the same glossary — and serves as the behavioral test
double for the real bridge tool in semantido-mcp.

Baseline (all mutations off) is a faithful generator: dimension-style ids
(``dim_``/``m_`` prefixes — id drift is inherent to generators and must be
survivable), glossary definitions carried verbatim, glossary relations
honored, per-source pins copied.

Five injectable mutations, each a documented real-world generator failure:

  id_rename              gratuitous rename beyond prefix convention
  definition_paraphrase  definitions rephrased/truncated by the pipeline
  stale_pin              tool-level config pins fibo one release behind
  equivalence_inflation  every mapping emitted as exact_match — generated
                         pipelines default to equivalence; nobody writes a
                         code generator that outputs epistemic humility
  granularity_merge      name-normalization merges the two counterparty
                         senses into one generated concept
"""

from dataclasses import dataclass

from authored_stack import GLOSSARY
from semantido.concepts import (
    ConceptRegistry,
    ExternalMapping,
    MappingRelation,
    OntologySource,
)


@dataclass
class Mutations:
    id_rename: bool = False
    definition_paraphrase: bool = False
    stale_pin: bool = False
    equivalence_inflation: bool = False
    granularity_merge: bool = False

    def label(self) -> str:
        active = [k for k, v in self.__dict__.items() if v]
        return "+".join(active) if active else "baseline"


PARAPHRASES = {
    "legal_entity": "Legal person identified by an LEI code.",
    "counterparty_emir": "The counterparty of the trade (EMIR).",
    "counterparty_mifir": "Counterparty per MiFIR reporting.",
    "notional": "Notional of the contract in EUR.",
    "asset_class": "Asset class (IR/FX/CR/EQ/CO).",
    "trade_report": "EMIR submission to the TR.",
}

RENAMES = {"counterparty_emir": "trading_party", "notional": "contract_value"}

#: Generated realized_by mapping table (generators emit mapping tables,
#: not decorators): physical column -> generated concept id.
def realized_map(mutations: Mutations) -> dict[str, str]:
    ids = {t: _gen_id(t, mutations) for t in GLOSSARY["terms"]}
    mapping = {
        "emir_trade_state.cpty_lei": ids["counterparty_emir"],
        "emir_trade_state.notional": ids["notional"],
        "emir_trade_state.asset_class": ids["asset_class"],
        "mifir_transaction.buyer_lei": ids["counterparty_mifir"],
        "mifir_transaction.amount": ids["notional"],
    }
    return mapping


def _gen_id(term_id: str, mutations: Mutations) -> str:
    if mutations.granularity_merge and term_id.startswith("counterparty"):
        return "dim_counterparty"
    base = RENAMES.get(term_id, term_id) if mutations.id_rename else term_id
    prefix = "m_" if term_id in ("notional",) else "dim_"
    return f"{prefix}{base}"


def build_generated_registry(mutations: Mutations) -> ConceptRegistry:
    registry = ConceptRegistry("hikari.golden.sml_generated")

    for name, src in GLOSSARY["sources"].items():
        version = src["version"]
        if mutations.stale_pin and name == "fibo":
            version = "2025Q1"  # tool config lags the glossary
        registry.add_source(
            OntologySource(
                name=name,
                namespace=src["namespace"],
                version=version,
                profile=src.get("profile"),
            )
        )

    emitted: set[str] = set()
    for term_id, term in GLOSSARY["terms"].items():
        gen_id = _gen_id(term_id, mutations)
        if gen_id in emitted:  # granularity merge collapses ids
            continue
        emitted.add(gen_id)

        definition = (
            PARAPHRASES[term_id]
            if mutations.definition_paraphrase
            else term["definition"]
        )
        mappings = []
        for anchor in term.get("anchors", []):
            relation = MappingRelation(
                anchor["relation"]
                .replace("narrow_match", "narrower")
                .replace("broad_match", "broader")
                .replace("related_match", "related")
            )
            if mutations.equivalence_inflation:
                relation = MappingRelation.EXACT_MATCH
            mappings.append(
                ExternalMapping(
                    target=anchor["target"],
                    relation=relation,
                    source=anchor["source"],
                    # generators do not emit justifications
                )
            )
        registry.concept(
            gen_id,
            definition=definition,
            label=term.get("label", term_id.replace("_", " ")),
            external=mappings,
            # generators emit no concept-to-concept relations
        )
    registry.validate()
    return registry
