# 01 — Getting started

A synthetic EMIR/MiFIR regulatory reporting schema, annotated end to end.
Six tables, nine concepts, five grains, exported to four formats and gated
on the linter.

```bash
pip install 'semantido[lint,ossie]>=0.5.3'
python semantic.py      # build, lint, export
python lint_demo.py     # what the declared concepts now reject
```

## The order this example is built in

Article 02 of the series argues that semantics must come before ontology:
first say what a thing *is* in the context it is used, then build the graph.
The file layout follows that argument.

`models/concepts.py` comes first. Every entry is a definition a domain expert
would recognise — what a UTI identifies, why a notional is not an exposure —
and only then a node with edges and a grain.

`models/trade_reporting.py` comes second. It is the physical schema, and it
*references* concepts rather than defining them. A column says
`uti_concept = "uti"`; it does not restate what a UTI means. Meaning lives in
one place.

`semantic.py` builds the layer, lints it, and exports. The lint step is the
one that changed in v0.5: before it existed, every annotation in this example
was documentation — true when written, unverifiable afterwards.

## The three failure modes

The schema deliberately encodes three classic text-to-SQL traps. Run
`lint_demo.py` to see which are now enforced:

| Trap | The join | Verdict |
|---|---|---|
| Amount ambiguity | `notional_amount = valuation_amount` | SL008 + SL009 |
| Identifier grain | `uti = transaction_reference` | SL008 + SL009 |
| Party homonym | `counterparty_id = buyer_id` | SL009 |
| Bridge fan-out | `trade_reports` → `trade_parties`, then `SUM` | **not caught** |

The first three were prose warnings in a docstring until the concepts were
declared. Declaring them turned a comment into a build failure.

The fourth is not caught and this example says so. Both sides of the fan-out
join carry the same concept at the same grain, so no shipped check sees it.
Cardinality is a separate axis from grain and needs the column tuple that
makes a row unique — see
[`examples/07_security_master`](../07_security_master) for the same limit in
reference data, measured.

## What gets exported

| File | For |
|---|---|
| `trade_reporting.semantic.md` | Agent prompt context |
| `trade_reporting.semantic.json` | Programmatic consumers |
| `trade_reporting.ossie.yaml` | Ossie interchange |
| `groundings.yaml` | Concept-to-column bindings, with definition checksums |

The groundings file is derived, not authored. You already wrote it, every
time a `_concept` attribute appeared on a column. Regenerating it is the
workflow; hand-editing it is a smell.

## Using the gate in CI

`semantic.py` exits non-zero on any lint error. That is the whole integration:

```python
findings = lint_layer(layer)
errors = [f for f in findings if f.severity.value == "error"]
if errors:
    sys.exit(1)
```

Errors gate the build. Warnings don't.
