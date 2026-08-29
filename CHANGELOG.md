# Changelog

All notable changes to semantido are documented here. The project adheres to
[Semantic Versioning](https://semver.org) within the limits of its alpha status:
the authoring surface is stable in practice; exporter output may move with the
specs it targets.

## [Unreleased]

### Added

- **Deprecated aliases `to_osi_dict` / `to_osi_yaml`.** These were renamed to
  `to_ossie_*` in 0.5.1 with no shim and no changelog entry, so code written
  against 0.5.0 broke on upgrade. The old names now work again and emit a
  `DeprecationWarning` naming the replacement. They will be removed in 0.7.

- **`examples/06_groundings_and_lint`** — groundings lifecycle and the four
  checks that guard it (SL007 in both directions, SL009, SL010), on the
  EMIR/MiFIR counterparty homonym. Every finding in the output is real
  linter output.

- **`examples/07_security_master`** — grain, the fan-out, and the limits of
  static checking. The twelve-row matrix is computed from the fixture rather
  than asserted.

- **`examples/08_release_timeline`** — one fixed schema probed under every
  published release, showing what each could express and enforce.
  Deterministic and offline.

- **`examples/README.md`** — an index, with a reading order.

### Changed

- **`examples/01_getting_started` updated to v0.5.** The walkthrough now
  declares a concept registry (`models/concepts.py`) with nine concepts
  across five grains, binds them to columns, exports a groundings document,
  and gates the build on the linter. A new `lint_demo.py` shows which of the
  schema's documented failure modes are now rejected statically — amount
  ambiguity, identifier grain and the counterparty homonym — and which is
  not: the bridge fan-out, where both sides carry the same concept at the
  same grain.

  The example previously taught a v0.3-era model while being the only one
  linked from the README.

- **README now indexes all eight examples** rather than only the first.
  `docs/get-started/quickstart.md` and `docs/concepts/correctness.md`
  updated to match.

### Changed

- **SL008 message wording corrected.** It claimed a grain-mismatched join
  "fans out or drops rows". It does neither: identifiers at different grains
  occupy different value spaces, so the equality matches nothing and the join
  returns an empty set. The fan-out comes from the *same* concept keying both
  sides at the same grain, which SL008 does not catch. `docs/guides/lint.md`
  carried the same overclaim and has been corrected alongside.

### Removed

- **`examples/04_federated_agents/bank_a.py` and `bank_b.py`** (root copies).
  `run_experiment.py` prepends `models/` to `sys.path`, so the `models/`
  copies were the live ones and these never loaded. They had already drifted
  from their live counterparts.

## [0.5.3]

### Added

- **SL009 — join equates concepts asserted `DISTINCT_FROM`.** A gap in the
  v0.5.0 check set: SL006 warns that a homonym exists without a
  `DISTINCT_FROM` edge, and SL008 rejects joins across differing grain, but
  nothing rejected a join that equates two concepts the registry explicitly
  says are *not* the same thing. Where those concepts share a grain — the
  EMIR/MiFIR "Counterparty" case, both denoting a legal entity — SL008 has
  nothing to compare and the join passed silently. SL009 is grain-independent
  and reported as an error. Where both SL008 and SL009 apply to one join,
  both are reported: each names a distinct reason the join is wrong.

  SL009 is the more consequential of the two. A grain mismatch usually
  implies two different identifier schemes and therefore two disjoint value
  spaces, so an SL008 join tends to return nothing — wrong, but visibly so.
  Two concepts that share a grain share a value space (both LEIs, both NPIs),
  so an SL009 join *matches rows* and returns a plausible number. In the
  EMIR/MiFIR fixture it doubles a counterparty exposure, reporting 50m
  against a true 25m, with no error anywhere in the stack.

- **SL010 — `DISTINCT_FROM` concepts claiming the same `exactMatch`.**
  `skos:exactMatch` is symmetric and transitive, so two concepts that both
  exactMatch the same external IRI are entailed to be interchangeable. Where
  a `DISTINCT_FROM` edge also exists, the registry asserts both that they are
  distinct and that they are the same, and the exported Turtle is
  inconsistent under any SKOS reasoner. Reported as an error. `closeMatch`,
  `broadMatch`, `narrowMatch` and `relatedMatch` are unaffected — closeMatch
  is deliberately non-transitive, so a shared target there is legitimate and
  is the correct way to map two regime-specific readings onto one external
  concept.

### Changed

- The reciprocated `DISTINCT_FROM` lookup used by SL006 is extracted into
  `_asserted_distinct()` and shared with SL009; behaviour is unchanged.

## [0.5.2] — 2026-08-01

- **SL010 — `DISTINCT_FROM` concepts claiming the same `exactMatch`.**
  `skos:exactMatch` is symmetric and transitive, so two concepts that both
  exactMatch the same external IRI are entailed to be interchangeable. Where
  a `DISTINCT_FROM` edge also exists, the registry asserts both that they are
  distinct and that they are the same, and the exported Turtle is
  inconsistent under any SKOS reasoner. Reported as an error. `closeMatch`,
  `broadMatch`, `narrowMatch` and `relatedMatch` are unaffected — closeMatch
  is deliberately non-transitive, so a shared target there is legitimate and
  is the correct way to map two regime-specific readings onto one external
  concept.

### Changed

- **OSI → Apache Ossie** naming convention adopted across the source, tests,
  examples, and docs, tracking the project's rename: `osi_exporter.py` →
  `ossie_exporter.py`, `to_osi_dict`/`to_osi_yaml` → `to_ossie_dict` /
  `to_ossie_yaml`, the `osi` extra → `ossie`, and spec constants renamed
  accordingly (`APACHE_OSSIE_SPEC_VERSION`). No behavioral change to
  exporter output beyond the vendor/spec identifiers.

## [0.5.1] — 2026-08-01

### Fixed

- **SL007 groundings anchors with dotted table names.** Anchor strings were
  split on the *first* dot, so tables whose names themselves contain dots —
  Kafka topic names like `etd.executions` modelled as `__tablename__` —
  mis-resolved and produced false missing-anchor findings. Anchors now split
  on the *last* dot: only the final segment is the column.

## [0.5.0] — 2026-07-31

### Added

**`semantido.lint`** — static checks for the seams between claim systems.
Every subsystem validates itself (SQLAlchemy the schema, the registry its
graph, exporters their formats); nothing validated the cross-references
between them, which rot silently. The linter owns the seams. Tier-2 static:
no database connection, no model calls. SQL parsed with sqlglot
(`pip install semantido[lint]`).

- `lint_layer(layer, groundings=None) -> list[Finding]` — deterministic,
  sorted findings; errors gate CI, warnings do not.
- SL001/SL002 — `sql_filters` must be parseable SQL and reference only
  columns that exist (prose leakage and renamed-column rot).
- SL003 — relationship join conditions must parse and fully resolve, with
  every column qualified.
- SL004 — `sample_values` consistent with the declared column type.
- SL005 — synonym collisions across tables, or across columns bound to
  different concepts.
- SL006 — registry homonyms (shared surface forms) without a declared
  `DISTINCT_FROM` edge between the claimants.
- SL007 — groundings staleness, both directions: physical anchors that no
  longer exist in the layer (schema drift) and recorded
  `definition_checksum` values that no longer match the registry (meaning
  drift).
- SL008 — grain-mismatched joins: see *Concept grain* below.

**Concept grain** — `Concept.grain`, a first-class declaration of the level
at which a concept identifies or measures its subject (free-form by design;
`"issue"` / `"listing"` / `"product"` for instrument identifiers is the
motivating idiom from security-master vendor cross-referencing, where
ISIN/FIGI/RIC/UPI all read as "the identifier" but sit at different grains).
Authored via `registry.concept(..., grain=...)`, serialized only when set
(no output churn for existing registries), rendered in the Markdown concept
tier (`- **Grain**:`) and in SKOS Turtle as `smtdo:grain`. `semantido.lint`
compares declared grains verbatim: a join equality between columns bound to
concepts of different grain is an SL008 error — the static form of the
classic issue-level-to-listing-level fan-out join.

**Groundings exporter** (`semantido.exporters.groundings_exporter`) — the
deployment half of the meaning/deployment split. The registry serializes
meaning only (`to_yaml()`, verified and now locked by test); groundings
capture where each concept is physically realized in one deployment:

- `to_groundings_dict/yaml/file(layer)` — concept id → anchor tables and
  `table.column` anchors, each entry carrying the concept's
  `definition_checksum` at recording time.
- `load_groundings(path_or_dict)` — format-guarded loading
  (`format: semantido/groundings`).
- Design rule: **meaning travels, groundings don't.** Exchange the concepts
  file across organizational boundaries; keep the groundings file with the
  deployment it describes, checked for staleness by SL007.

### Fixed

- `ConceptRegistry.subset()` no longer aliases the parent registry's
  `Concept` objects: subsets deep-copy concept state, so mutating a subset
  (synonyms, mappings, relations) cannot silently corrupt the parent.
- SKOS exporter: external mapping target URIs are now constructed correctly.
  Absolute targets pass through verbatim, `source:`-prefixed targets are
  stripped before joining, and a separator is inserted unless the namespace
  ends in `/`, `#` or `:`. Previously namespace and target were concatenated
  raw, producing malformed URIs such as `<urn:iso:std:iso:10962iso10962:cfi>`.
- Committed example exports regenerated: they had drifted from the code that
  generates them (missing `unique_keys`, unnormalized relationship
  directions).

### Compatibility

API-compatible: all existing calls work unchanged (`grain` and the lint /
groundings modules are additive). Output-compatible for grain-less
registries (grain is omit-if-unset). SKOS Turtle output changes for any
registry whose external mapping targets previously produced malformed URIs —
that is the bug fix; regenerate committed `.ttl` artifacts.

### Deferred

- `align()` remains in `examples/04_federated_agents`, per the
  feature-freeze rule of keeping the 0.5.0 API surface small. The security
  master vendor cross-reference use case (one registry per vendor
  vocabulary, crosswalk computed by alignment) is the strongest candidate
  consumer if promoted in 0.6.

Test suite: 141 passing (114 at 0.4.1 + 27 new).

## [0.4.1] — 2026-07-22

*Backfilled at 0.5.0: this entry was drafted during the 0.4.1 cycle but never
committed — the release gate now requires the changelog to land with the code.*

### Added

- **Tiered Markdown export**: `to_markdown(include=("schema", "enriched",
  "concepts"))` separates the pure table schema, the enriched semantic
  fields, and the concept-registry tier, so agent context can be budgeted
  per tier.
- Standalone export functions: `to_markdown_schema`, `to_markdown_tables`,
  `to_markdown_concepts`.
- SKOS Turtle exporter (`to_skos_turtle`, `to_skos_file`) with the
  `smtdo:distinctFrom` extension predicate for the OWL-style homonym edge
  SKOS cannot express.

### Compatibility

API-compatible: `include` is a new optional parameter. Default
`to_markdown()` output is not byte-identical to 0.4.0 — the enriched tier
emits fields previously silently dropped. Snapshot tests, token-budgeted
contexts, and export checksums are affected; `to_markdown(include=("schema",))`
restores the prior minimal footprint.

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
