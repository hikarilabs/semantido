# Changelog

All notable changes to semantido are documented here. The project adheres to
[Semantic Versioning](https://semver.org) within the limits of its alpha status:
the authoring surface is stable in practice; exporter output may move with the
specs it targets.

## [0.4.0] — 2026-07-18

### Added

**Concept registry** (`semantido.concepts`) — a concept tier above the physical
schema, motivated by the EMIR/MiFIR *Counterparty* homonym: same label, different
legal concepts, and nothing at the schema tier able to say so. This is an experimental vibe-coded
feature to verify that you do not need a full OWL representation in an agent-2-agent interaction.
Highly likely to break in a future release.

- `ConceptRegistry.concept()` — single authoring path. Relation kwargs
  (`broader`, `narrower`, `same_as`, `related`, `distinct_from`) accept only
  `Concept` handles from the same registry, so unresolved references are
  impossible to author: a misspelling is a `NameError`, a string a `TypeError`,
  a foreign handle a `ValueError`.
- `distinct_from` — the explicit homonym edge (OWL-style non-equivalence; SKOS
  has no such assertion). Symmetric relations reciprocate automatically:
  declaring either side records both.
- **External mappings** to pinned ontology releases via SKOS-aligned helpers
  (`exact_match`, `close_match`, `narrow_match`, `broad_match`,
  `related_match`) against `OntologySource(name, namespace, version)` —
  `version` required, untyped mappings unrepresentable.
- `find_homonyms()` — surface forms (labels and synonyms) claimed by more than
  one concept.
- `subset()` — self-contained sub-registry closed over a set of ids via
  relations; the unit of exchange between teams. Handles do not transfer
  between registries; exchange is by serialized document.
- `validate()` — referential checks (targets resolve, no self-relations,
  mapping sources pinned, broader/narrower acyclic), collecting every
  violation into one raise.
- `Concept.definition_checksum` — stable fingerprint of the definition text,
  so diffs distinguish rewording from meaning change.
- Sidecar serialization: `to_yaml()` emits a standalone `concepts.yaml` with
  sources, both directions of every symmetric relation, and checksums.

**Schema binding**

- `@semantic_table(concept="...")` and the `<column>_concept` attribute bind
  tables and columns to registered concept ids
  (dunder: `__semantic_concept__`, with the same same-class-body conflict
  `ValueError` as `time_dimension`).
- `sync_semantic_layer(concept_registry=...)` validates every binding at sync
  time and raises one `ValueError` listing all unresolved references — concept
  bindings cannot silently-exist.

**Exporters**

- Markdown: new `## Concepts (N in scope)` section rendering the subset
  closure of bound concepts — closure follows relations, so a bound concept's
  `distinct_from` partner appears even when unbound — and a
  `## Disambiguation` section surfacing `find_homonyms()` output with explicit
  do-not-conflate instructions.
- OSI: the same closure embeds in model-level `custom_extensions` under the
  `SEMANTIDO` vendor, including relations and definition checksums.
- JSON: registry carried under a top-level `concepts` key via `to_dict()`.

### Notes

- **Cross-registry alignment is deliberately not a library feature.** A
  reference alignment protocol — SKOS relation composition with weakest-link
  semantics, a sibling rule for co-narrow matches under a shared anchor, and a
  pin-mismatch cap — is demonstrated in `examples/04_federated_agents`, where
  it reduces silent cross-institution errors from 2 to 0 across a two-bank
  EMIR/MiFIR experiment. Alignment policy (how much composition to trust,
  where to cap confidence) belongs to your governance, not to `pip install`.
  A companion experiment, `examples/05_toolchain_drift`, reuses the same
  alignment verbatim to reconcile an authored registry against a
  tool-generated one, showing `definition_checksum` disagreement, relation
  inflation, and `distinct_from` collisions detecting every injected fault.
- `semantido.concepts` is the canonical import path; the implementation lives
  at `semantido.generators.concept_registry` and both work.
- Test suite grows 81 → 90; `concept_registry.py` at 99% line coverage.

## [0.3.1] — 2026

OSI exporter conformance patch (three schema defects in the native exporter
against Ossie `0.2.0.dev0`); dependency refresh; examples re-run against the
current Ossie schema.

## [0.3.0] — 2026

Time-dimension model (primary axis per table via `time_dimension=` /
`__semantic_time_dimension__`, secondary axes via `<col>_is_time_dimension`,
`TimeGrain` with sync-time validation); complete exporter overhaul producing
OSI YAML, Markdown, and JSON from one `SemanticLayer`; audit-column demotion
in the OSI exporter.
