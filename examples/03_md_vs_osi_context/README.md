# Markdown vs. OSI YAML as text-to-SQL context — an experiment

One semantido semantic layer, three serializations, six probe questions,
deterministic scoring. This example measures which serialization of the same
semantic layer makes a better *prompt context* for text-to-SQL.

## Design

Comparing the Markdown and OSI exports raw would be confounded: they differ
in **format** and in **information content** (the Markdown exporter does not
yet emit the structured time metadata, default filters, or glossary; the OSI
export carries no data types). So the experiment runs three conditions:

- **md** — the Markdown export as shipped.
- **osi** — the OSI YAML export as shipped.
- **md_enriched** — the Markdown export plus a plain-text block of exactly
  the signals it lacks. This is the control: *md vs md_enriched* isolates
  the content effect at constant format; *md_enriched vs osi* isolates the
  format effect at near-constant content.

Structurally (see `exports/structural_comparison.txt`), `md_enriched` is the
only condition carrying every signal — including the data types OSI lacks —
at roughly 1,040 tokens against OSI's 1,719 and plain Markdown's 780.

**Pre-registered hypothesis:** `md_enriched ≥ osi > md`, with the first gap
near zero and the second concentrated on the axis and default-filter
questions.

Six probe questions each target one metadata signal: axis choice, the audit
trap, the default ACTIVE filter, value-date routing, the sign convention,
and a join with glossary vocabulary. Scoring is deterministic regex checks
on the generated SQL (all `requires` match, no `forbids` match).

## Run it

Python harness (writes `exports/results.csv` and a summary):

```bash
pip install semantido pyyaml
cd examples/03_md_vs_osi_context
ANTHROPIC_API_KEY=sk-... python experiment_md_vs_osi.py --trials 5
```

Without a key, the harness still regenerates the three context files and the
structural comparison.

Interactive runner: open `runner.html` in a browser, paste an Anthropic API
key (sent only to `api.anthropic.com`, never stored), and click *Run
experiment* — a test-runner dot matrix fills in per trial, and clicking any
dot shows the generated SQL and the check that decided it. Inside a Claude
 artifact, the key field can be left empty.

## Files

- `experiment_md_vs_osi.py` — builds the three contexts from the models in
  `../02_osi_time_dimension` (single source of truth, no duplicated models),
  writes the structural report, and runs the live grid when a key is set.
- `runner.html` — the same experiment as an interactive page.
- `exports/` — generated contexts, `structural_comparison.txt`, and
  `results.csv` after a live run.
