---
title: The concept registry
description: Declare what your schema means at the concept tier — including which same-named things must never be conflated.
---

# The concept registry

*New in v0.4.0.*

Everything else in semantido describes **physical objects** — tables, columns, joins. The concept registry describes the **business concepts** those objects realize, and the relations between the concepts themselves.

The motivating case is a homonym that costs real money. Under EMIR, a *Counterparty* is a party to a derivative contract, including CCPs. Under MiFIR, a *Counterparty* is the execution counterparty on a reportable transaction. Same word, same industry, same bank, different legal concepts, and different reports. Nothing at the schema tier can say that `emir_trades.cpty` and `mifir_tx.party` are **not the same thing** — the concept registry exists so something can.

## Authoring

One public path — `registry.concept()` constructs, registers, and returns in one step:

```python
from semantido.concepts import ConceptRegistry, OntologySource, exact_match

reg = ConceptRegistry()

reg.add_source(OntologySource(
    name="fibo",
    namespace="https://spec.edmcouncil.org/fibo/ontology/",
    version="2025Q3",              # required — unpinned mappings can't be validated
))

party = reg.concept(
    "party",
    "A legal person able to enter contracts.",
)

emir = reg.concept(
    "counterparty.emir",
    "EMIR Art. 2(8): a party to a derivative contract, including CCPs.",
    label="Counterparty",
    broader=party,
    external=exact_match("fibo", "fibo-fnd-pty-pty:PartyInRole"),
)

mifir = reg.concept(
    "counterparty.mifir",
    "MiFIR RTS 22: the execution counterparty on a reportable transaction.",
    label="Counterparty",
    broader=party,
    distinct_from=emir,            # the explicit homonym declaration
)

reg.validate()
```

The design rules, each of which prevents a class of silent error:

- **Relation kwargs take `Concept` handles, not strings.** A misspelled handle is a `NameError` at author time; a string is a `TypeError`; a handle from another registry is a `ValueError`. There is no unresolved-reference state to discover later.
- **Symmetric relations reciprocate automatically.** Declaring `distinct_from=emir` on `mifir` also records the mirror edge on `emir` — exports show the assertion from both sides, and you cannot forget half of it.
- **External mappings must state their relation.** There is no way to write an untyped pointer at FIBO: you build the mapping with `exact_match()`, `close_match()`, `narrow_match()`, `broad_match()`, or `related_match()` (SKOS-aligned), against a *pinned* source version.
- **Dotted ids are namespacing convention only.** `counterparty.emir` derives no relation from its prefix; every edge is explicit.
- **`validate()` collects everything.** Unresolvable targets, self-relations, unpinned mapping sources, and cycles in the broader/narrower graph are reported in one raise, not one at a time.

## Binding concepts to the schema

Tables bind via the decorator; columns via the `<column>_concept` convention — both take the concept **id** as a string:

```python
@semantic_table(
    description="EMIR trade state reports — one row per report.",
    concept="counterparty.emir",
)
class EmirTrade(SemanticDeclarativeBase):
    __tablename__ = "emir_trades"

    id = Column(Integer, primary_key=True)
    cpty = Column(String(20))
    notional = Column(Numeric(18, 2))

    cpty_concept = "counterparty.emir"
```

The registry joins at sync:

```python
layer = SemanticDeclarativeBase.sync_semantic_layer(concept_registry=reg)
```

**Binding is validated at sync time.** Every `concept=` / `<column>_concept` reference must resolve to a registered id; a typo fails your test suite with a listing of every unresolved reference:

```
ValueError: Unresolved concept references (not in registry):
  - table 'emir_trades' -> 'counterparty.emri'
```

This closes the silent-typo gap that column annotations have — a concept binding cannot quietly not-exist.

## What the agent sees

The Markdown exporter renders the **subset closure**: only concepts actually referenced by the schema, plus everything reachable through their relations. That closure rule is what makes homonym protection work — binding only the EMIR concept still pulls its `distinct_from` partner into the export, because a warning about MiFIR is useless if MiFIR isn't on the page. Real output from the model above, unedited:

```markdown
## Concepts (3 in scope)

Business concepts realized by this schema. The concept id is the authoritative
reference; labels may collide (see Disambiguation).

### `counterparty.emir` — Counterparty
- **Definition**: EMIR Art. 2(8): a party to a derivative contract, including CCPs.
- **Realized by**: emir_trades, emir_trades.cpty
- **External**: exact match → `fibo-fnd-pty-pty:PartyInRole` [fibo@2025Q3]
- **Relation**: broader → `party`
- **Relation**: distinct from → `counterparty.mifir`

### `counterparty.mifir` — Counterparty
- **Definition**: MiFIR RTS 22: the execution counterparty on a reportable transaction.
- **Realized by**: — (context only, not bound in this schema)
- **Relation**: broader → `party`
- **Relation**: distinct from → `counterparty.emir`

### `party` — party
- **Definition**: A legal person able to enter contracts.
- **Realized by**: — (context only, not bound in this schema)

## Disambiguation

The surface forms below are claimed by more than one distinct concept. Always
resolve by concept id, never by label.

### "counterparty" — 2 distinct concepts
- `counterparty.emir` (emir_trades, emir_trades.cpty): EMIR Art. 2(8): a party
  to a derivative contract, including CCPs.
- `counterparty.mifir` (not bound here): MiFIR RTS 22: the execution
  counterparty on a reportable transaction.

Do not treat these as equivalent; do not join or compare their columns as if
they carried the same meaning.
```

The `## Disambiguation` section is `find_homonyms()` surfaced: every label or synonym claimed by more than one concept, with the instruction an agent needs. You can also call `reg.find_homonyms()` yourself — it returns `dict[str, list[str]]`, surface form to concept ids — for CI checks or your own rendering.

In the **OSI export**, the same closure rides in the model-level `custom_extensions` under the `SEMANTIDO` vendor, including relations and per-concept `definition_checksum`s. The **JSON export** carries it as a top-level `concepts` key. And independent of any schema, the registry serializes to a sidecar document:

```python
reg.to_yaml("concepts.yaml")
```

which includes the pinned sources, every relation from both sides, and a `definition_checksum` per concept — a stable fingerprint of the definition text, so a diff on the file distinguishes "the wording changed" from "the meaning moved." What checksums and relation structure buy in practice is demonstrated in [`examples/05_toolchain_drift`](https://github.com/hikarilabs/semantido/tree/main/examples/05_toolchain_drift): reconciling an authored registry against a tool-generated one, checksum disagreement, relation inflation, and collisions against `distinct_from` catch every injected fault that name-matching and anchor alignment each miss.

## Sharing concepts across teams and registries

`subset()` builds a self-contained sub-registry closed over a set of ids — the piece you hand to another team, another agent, or another schema's export without shipping your whole ontology:

```python
shared = reg.subset({"counterparty.emir"})
# contains counterparty.emir + party + counterparty.mifir (closure via relations)
shared.to_yaml("emir_concepts.yaml")
```

Handles deliberately do **not** transfer between registries — a `Concept` from one registry used in another's `concept()` call raises. Exchange happens through serialized documents, not shared Python objects, which is what keeps a registry auditable as a unit.

What semantido ships is the registry, the closure, and the exports. **Cross-registry alignment — computing which of *your* concepts corresponds to which of *theirs* — is deliberately not a library feature.** A reference alignment protocol (SKOS relation composition with weakest-link semantics) is demonstrated in [`examples/04_federated_agents`](https://github.com/hikarilabs/semantido/tree/main/examples/04_federated_agents), where it takes silent cross-institution errors from 2 to 0 in a two-bank EMIR/MiFIR experiment. It lives in examples because alignment policy — how much composition you trust, where you cap confidence — is a decision your governance should own, not one a library should freeze.

## What to register (and what not to)

The registry earns its keep on concepts that are **contested, regulated, or collide** — not on everything.

Register: concepts with a legal definition (EMIR/MiFIR/SFTR terms), homonyms across regimes or departments, concepts you map to an external ontology, and concepts two schemas must agree on.

Skip: concepts that exist in one table with one uncontested meaning. `orders` does not need a concept; its table description already says everything. A registry of four hundred trivially-true concepts buries the six that matter.

## In short

- The schema tier says what a column **is**; the concept tier says what it **means** — and, critically, what it must never be conflated with.
- `distinct_from` is the explicit homonym edge; the subset closure and `## Disambiguation` section carry it to the agent even when only one side is bound.
- Binding is validated at sync; authoring errors fail at author time; `validate()` reports everything at once.
- Alignment across organizations is a protocol you run (see `examples/04`), not a feature you import.
