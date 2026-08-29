# 08 — Release timeline

One fixed schema, every semantido release. What could you express, and what
would it have caught?

```bash
python run_timeline.py              # probes every tag
python run_timeline.py --report-only  # re-render saved results
```

Deterministic and offline. No LLM, no API key, no database. Re-running it on
the same tags reproduces the table exactly.

## Method

`probe.py` builds the same three-table security master under whichever release
is installed, detecting the API at runtime rather than assuming it. On releases
without `grain=`, it authors without grain instead of crashing — so the table
shows what each release *could express*, not what it errored on.

`run_timeline.py` creates a git worktree per tag, installs each in turn, runs
the probe, and tabulates.

Token counts are a deterministic proxy — 4 characters per token — chosen so
the number is comparable across releases and reproducible without a tokenizer.
It is not a billing figure.

## Result

```
release   concepts  grain  md tok  checks        figi = ric   isin = ric     isin = isin
0.4.0            3      0     629  —             n/a          n/a            n/a
0.4.1            3      0     645  —             n/a          n/a            n/a
0.5.0            3      3     660  SL001-SL008   silent       SL008          silent
0.5.1            3      3     660  SL001-SL008   silent       SL008          silent
0.5.2            3      3     660  SL001-SL008   silent       SL008          silent
0.5.3            3      3     660  SL001-SL010   silent       SL008+SL009    silent
```

## What it shows

**Expressiveness arrived in one release.** Grain, groundings and lint all
landed together in 0.5.0. Before that the registry could say two concepts were
distinct but not at what level either one identified its subject.

**Enforcement is cheap once meaning is declared.** Going from 8 checks to 10
in 0.5.3 cost nothing structurally — the declarations were already there. The
expensive release was 0.5.0.

**Context cost is flat.** 629 to 660 tokens across the whole history, a 5%
increase for grain, distinctions and checksums. Whatever the argument against
a semantic layer is, context budget is not it.

**And the column that matters never moves.** `isin = isin` is silent in every
release ever shipped. That is the join that returns twelve rows for one
instrument — 25% signal, decaying to 7% as vendor coverage grows. The join
that *is* caught, `isin = ric`, returns an empty set: loud, obvious, cheap.

Six releases of steadily better tooling, and the most expensive failure mode
in the domain has never once failed a build. Cardinality needs grain as a
column tuple rather than a single string, and that is a v0.6 question.

See [`07_security_master`](../07_security_master) for the fan-out computed
row by row.

## Caveat

This measures *expressiveness and enforcement*, not accuracy. It does not
re-run the text-to-SQL benchmark, which needs live model calls. The two
measure different things and the numbers are not comparable.

## Also surfaced

`to_osi_yaml` was renamed to `to_ossie_yaml` between 0.5.0 and 0.5.3 with no
deprecation shim. Any 0.5.0-era code calling the old name breaks on upgrade.
