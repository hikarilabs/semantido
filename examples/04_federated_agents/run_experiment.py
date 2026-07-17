"""Federated-agent experiment: two institutions, three resolution regimes.

Bank B's agent asks Bank A's agent questions in Bank B's vocabulary.
Ground truth per message is defined by hand from the registries: which
grounding is correct, and which messages MUST be refused because the
concepts are legally distinct despite identical surface terms.

Scoring per (message, condition):
  CORRECT        grounded to the right columns, or refused when refusal
                 is the right answer
  SILENT_ERROR   answered confidently with the wrong grounding — the
                 dangerous outcome
  FALSE_REFUSAL  refused although a correct grounding existed

Run:  python run_experiment.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "models"))


class _Tee:
    """Duplicates stdout to a report file next to the script."""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, text):
        for stream in self.streams:
            stream.write(text)

    def flush(self):
        for stream in self.streams:
            stream.flush()


_REPORT = open(
    Path(__file__).parent / "results" / "experiment_output.txt", "w", encoding="utf-8"
)
sys.stdout = _Tee(sys.__stdout__, _REPORT)


import bank_a
import bank_b
from agents import (
    Agent,
    ConceptResolver,
    Institution,
    LexicalResolver,
    Request,
    SemanticResolver,
)
from alignment import align

# ------------------------------------------------------------------ #
# Setup                                                              #
# ------------------------------------------------------------------ #
inst_a = Institution(
    bank_a.BaseA, bank_a.build_registry(), bank_a.SEED_ROWS, bank_a.EmirTradeState
)
inst_b = Institution(
    bank_b.BaseB, bank_b.build_registry(), bank_b.SEED_ROWS, bank_b.MifirTransaction
)

alignments = align(inst_a.registry, inst_b.registry)

print("=" * 72)
print("ALIGNMENT TABLE (bank_a.glossary <-> bank_b.vocab)")
print("=" * 72)
for (id_a, id_b), item in sorted(alignments.items()):
    print(f"  {id_a:22s} <-> {id_b:22s}  {item.verdict.name}")
    for reason in item.reasons:
        print(f"      - {reason}")

# ------------------------------------------------------------------ #
# Message set: Bank B asks Bank A                                    #
# ------------------------------------------------------------------ #
# Correct grounding in Bank A's schema, per message; None = must refuse.
MESSAGES = [
    (
        Request(
            asking_namespace="bank_b.vocab",
            intent="Total exposure per party (LEI) in your book",
            terms={"group_by": "party", "measure": "amount"},
            concepts={"group_by": "party", "measure": "transaction_amount"},
        ),
        # Positive control. party ==ALIGNED_EXACT(gleif)== legal_entity,
        # which is unrealized in Bank A's schema, but counterparty.emir
        # is a realized narrower proxy (every counterparty is a legal
        # entity), so {cpty_lei, notional} is the correct grounding.
        {"accept": [{"group_by": "cpty_lei", "measure": "notional"}]},
    ),
    (
        Request(
            asking_namespace="bank_b.vocab",
            intent="Sum by counterparty — MiFIR sense (RTS 22 buyer/seller)",
            terms={"group_by": "counterparty", "measure": "amount"},
            concepts={
                "group_by": "counterparty.mifir",
                "measure": "transaction_amount",
            },
        ),
        # The homonym trap: Bank A's "counterparty" is the EMIR sense.
        # Substituting it silently is the canonical cross-ontology error.
        {"accept": [None]},
    ),
    (
        Request(
            asking_namespace="bank_b.vocab",
            intent="Sum amount by asset class (our instrument classification)",
            terms={"group_by": "asset class", "measure": "amount"},
            concepts={
                "group_by": "instrument_class",
                "measure": "transaction_amount",
            },
        ),
        # Only obstacle is the fibo pin mismatch: semantically the same
        # concept, so answering {asset_class, notional} is defensible AND
        # a conservative refusal (re-verify against re-pinned fibo) is
        # defensible. Both accepted; what differs is auditability.
        {"accept": [{"group_by": "asset_class", "measure": "notional"}, None]},
    ),
    (
        Request(
            asking_namespace="bank_b.vocab",
            intent="Your execution reports filed last quarter",
            terms={"group_by": "execution report", "measure": "amount"},
            concepts={
                "group_by": "execution_report",
                "measure": "transaction_amount",
            },
        ),
        # Bank A has no MiFIR execution reports at all: NO_BRIDGE,
        # refusal is the only correct answer.
        {"accept": [None]},
    ),
]

CONDITIONS = [
    (LexicalResolver(), "condition 1: raw schema, lexical match"),
    (SemanticResolver(), "condition 2: semantic layer, no concepts"),
    (ConceptResolver(), "condition 3: concept protocol + alignment"),
]


def score(response, accept):
    if response.ok:
        return (
            "CORRECT"
            if response.grounding in [a for a in accept if a]
            else "SILENT_ERROR"
        )
    return "CORRECT" if None in accept else "FALSE_REFUSAL"


print()
print("=" * 72)
print("EXPERIMENT: Bank B's agent queries Bank A's agent")
print("=" * 72)

tally = {label: {"CORRECT": 0, "SILENT_ERROR": 0, "FALSE_REFUSAL": 0} for _, label in CONDITIONS}

for request, truth in MESSAGES:
    print(f"\nREQUEST: {request.intent}")
    print(f"  asker terms: {request.terms} | asker concepts: {request.concepts}")
    for resolver, label in CONDITIONS:
        agent_a = Agent(inst_a, resolver, alignments)
        response = agent_a.answer(request)
        outcome = score(response, truth["accept"])
        tally[label][outcome] += 1
        print(f"  [{label}] -> {outcome}")
        if response.ok:
            print(f"      grounding: {response.grounding}")
            print(f"      rows: {response.rows}")
        else:
            print(f"      refusal: {response.refusal}")

print()
print("=" * 72)
print(f"{'SCOREBOARD':40s} correct  silent-error  false-refusal")
print("=" * 72)
for label, counts in tally.items():
    print(
        f"{label:40s} {counts['CORRECT']:^7d} {counts['SILENT_ERROR']:^13d} "
        f"{counts['FALSE_REFUSAL']:^13d}"
    )
print()
print(
    "The metric that matters in a regulated context is the middle column:\n"
    "silent errors are confident answers grounded in the wrong legal\n"
    "concept. The concept protocol converts them into inspectable\n"
    "refusals carrying the reason (sibling-narrower, pin mismatch, or\n"
    "no bridge) — the heterogeneous-ontology problem made visible\n"
    "instead of silently absorbed."
)