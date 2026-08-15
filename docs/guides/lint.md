# Linting the layer

`semantido.lint` is a static checker for the *seams* between claim systems.
Every subsystem in a semantic layer validates itself — SQLAlchemy checks the
schema, the concept registry checks its graph, exporters check their formats.
What nothing checks are the cross-references between them, and those rot
silently: a `sql_filter` naming a renamed column, a join condition pointing
at a dropped table, a groundings file recorded against a definition that has
since changed.

The linter is **Tier-2 static**: it never connects to a database and never
calls a model. SQL is parsed with [sqlglot](https://github.com/tobymao/sqlglot):

```bash
pip install semantido[lint]
```

## Usage

```python
from semantido.lint import lint_layer

findings = lint_layer(layer)                            # SL001–SL006, SL008–SL010
findings = lint_layer(layer, groundings="groundings.yaml")  # adds SL007

for finding in findings:
    print(finding)

errors = [f for f in findings if f.severity.value == "error"]
assert not errors, "semantic layer lint failed"
```

Findings are returned in deterministic order (errors first), so the output
diffs cleanly in CI. Errors should gate the build; warnings should not.

## Checks

| Code  | Severity | Meaning |
|-------|----------|---------|
| SL001 | error    | `sql_filter` is not parseable SQL (prose leakage). |
| SL002 | error    | `sql_filter` references a column that does not exist. |
| SL003 | error    | Join condition unparseable, unqualified, or unresolvable. |
| SL004 | warning  | `sample_values` inconsistent with the declared type. |
| SL005 | warning  | Synonym claimed by multiple tables, or by columns bound to different concepts. |
| SL006 | warning  | Registry homonym without a declared `DISTINCT_FROM` edge. |
| SL007 | error    | Groundings staleness: missing anchor or `definition_checksum` drift. |
| SL008 | error    | Grain-mismatched join (see below). |
| SL009 | error    | Join equates concepts asserted `DISTINCT_FROM` (see below). |
| SL010 | error    | `DISTINCT_FROM` concepts claiming the same `exactMatch` (see below). |

## Grain-mismatched joins (SL008)

Concepts can declare a **grain** — the level at which they identify or
measure their subject:

```python
isin = registry.concept(
    "isin", "Issue-level instrument identifier.", grain="issue")
figi = registry.concept(
    "figi", "Venue-level instrument identifier.",
    grain="listing", distinct_from=isin)
```

Grain is free-form: the registry imposes no vocabulary. But declared grains
are compared **verbatim** by the linter: any join equality between columns
bound to concepts of different grain is an SL008 error. This is the static
form of the classic reference-data trap — joining an issue-level identifier
(one ISIN) to a listing-level identifier (many FIGIs) fans out or drops rows,
and nothing at the schema tier can see it. The linter can, because the
grains are declared.

## Joins across a declared distinction (SL009)

`DISTINCT_FROM` asserts that two concepts are not the same thing. SL006
warns when a homonym exists without that edge; SL009 is the other half —
it fires when a join equates two concepts the registry says are distinct.

```python
cp_emir = registry.concept(
    "counterparty.emir",
    "Either entity party to a derivative contract (EMIR Article 9).",
    label="Counterparty", synonyms=["counterparty"], grain="legal_entity")
cp_mifir = registry.concept(
    "counterparty.mifir",
    "The market-side entity faced in a transaction (MiFIR RTS 22); a client "
    "dealt for is NOT a counterparty here.",
    label="Counterparty", synonyms=["counterparty"], grain="legal_entity",
    distinct_from=cp_emir)
```

Both concepts have the **same grain** — each denotes a legal entity — so
SL008 has nothing to compare and stays silent. The problem is denotation,
not cardinality: the two regimes mean different entities by the same word,
and a join equating them produces a query that runs, returns rows, and
answers a question nobody asked. SL009 is grain-independent for exactly this
reason.

Where both conditions hold — different grain *and* a `DISTINCT_FROM` edge —
both findings are reported, since each names a separate reason the join is
wrong.

## Contradictory external mappings (SL010)

`skos:exactMatch` is symmetric **and transitive** (SKOS Reference S44/S45).
So if two concepts both claim an exactMatch to the same external IRI, the
SKOS data model entails that they are interchangeable with each other:

```python
emir = registry.concept(
    "counterparty.emir", "...", label="Counterparty",
    external=exact_match("fibo", FIBO_COUNTERPARTY))
mifir = registry.concept(
    "counterparty.mifir", "...", label="Counterparty",
    distinct_from=emir,
    external=exact_match("fibo", FIBO_COUNTERPARTY))   # contradiction
```

The registry now asserts both that the two concepts are distinct and that
they are the same thing. An external reasoner over the exported Turtle would
reject this; SL010 catches it before export.

`skos:closeMatch` is deliberately **not** transitive, precisely to stop
similarity propagating across schemes. Two distinct concepts may legitimately
closeMatch the same external concept, and SL010 stays silent for closeMatch,
broadMatch, narrowMatch and relatedMatch. For a regime-specific reading of a
shared external concept — the EMIR and MiFIR senses of "counterparty" against
FIBO's general one — `close_match` or `broad_match` is both the correct
modelling and the non-contradictory one.

## What the linter deliberately does not do

Coherence of prose descriptions, intent-to-column matching, and definition
quality are advisory concerns for an LLM judge — never CI gates. The linter
checks only what is mechanically decidable.

There is also one join failure the current checks *cannot* reach. SL008 and
SL009 both require the two sides of an equality to differ — in grain or in
denotation. A join fans out when the same concept keys both sides but the
tables sit at a finer grain than the key: joining two listing-level feeds on
an issue-level ISIN yields the cross product of their venues. Both columns
are the same concept at the same grain, so both checks correctly stay silent.

Detecting that needs a **table-level** grain — "one row per (isin, venue)" —
which the layer does not currently declare. Until it does, a fan-out is
outside the linter's reach by construction rather than by oversight.
