# The time dimension in OSI exports: what actually drives agent accuracy

semantido and OSI solve different halves of the same problem, and the easiest
way to see the split is to ask where each one lives. semantido lives in the
inner loop: semantics are authored in Python, directly on the SQLAlchemy
models, in the same file and the same pull request as the schema itself. OSI
lives in the outer loop: it is a vendor-neutral YAML interchange format,
backed by Snowflake, Databricks, dbt Labs, Salesforce, and a long list of
others, whose job is to let one semantic model travel between tools that will
never share a runtime. semantido is where semantics are written and governed;
OSI is how they leave the building. They are complementary, and
`semantido.exporters.to_osi_yaml` is the seam between them.

Most of the translation is uneventful, which is itself a good sign. Tables
become datasets with a `source` and `primary_key`; table and column
descriptions carry across verbatim; synonyms land in `ai_context.synonyms`;
ORM relationships — including cardinality and composite joins — become OSI
relationships, deduplicated across SQLAlchemy's two directions; the
application glossary becomes model-level `ai_context` instructions. An OSI
consumer that knows nothing about semantido gets a complete, readable model.

The interesting parts are the asymmetries. semantido carries several concepts
OSI core simply has no field for: `PrivacyLevel` on columns, `sample_values`,
default `sql_filters`, the native `TimeGrain` of a column, and the notion of
a *primary* time axis. None of these are dropped. They travel in
`custom_extensions` blocks under `vendor_name: SEMANTIDO` — OSI's sanctioned
escape hatch — and, where they matter to an LLM consumer, they are mirrored
into `ai_context` as plain instructions, so a generic agent benefits without
understanding the extension. The asymmetry runs the other way too: OSI has
first-class, cross-dataset `metrics` and multi-dialect expressions, and
semantido currently has neither — a metric like `net_flow = SUM(amount)` has
no authoring home in the library yet, which is arguably the most useful
concept OSI could push back *into* semantido.

The time dimension is the sharpest illustration of why authoring and
interchange need each other, and it is what this example measures.
OSI's entire first-class time vocabulary is one boolean: `dimension.is_time`.
No grain, no hierarchies, no way to say which of several dates is *the* axis.
So the question is what an exporter should write into that one bit. Run the
comparison and the answer falls out of the report. With time metadata **off**,
zero columns are flagged, and an agent asked for monthly transaction volume
must guess between booking, value, and settlement dating — a coin toss with
regulatory consequences. With **naive** type inference, every `DATE` and
`TIMESTAMP` column is flagged: eight time dimensions across two tables,
including `created_at` and `updated_at`, giving a 1-in-5 signal-to-noise
ratio on the transaction table. Naive inference is arguably worse than
nothing, because it launders ETL plumbing into governed-looking metadata.
The **curated** strategy — semantido's default — flags only business dates,
marks `booking_date` as `PRIMARY` with `grain: day` (via `ai_context` and
the SEMANTIDO extension, since OSI core cannot express either), and demotes
the audit columns entirely, attaching an explicit "do not use as a time axis"
instruction. Same schema, same format, three very different models — and the
difference is precisely the curation that only lives next to the code.

### What actually drives the difference

It is worth being precise about which piece of metadata does the work here,
because the export carries three distinct time signals, and they are not
equally important. There is the `is_time` boolean itself; there is the
*primary-axis designation* (`__semantic_time_dimension__`, surfaced as the
`PRIMARY` instruction and the `is_primary_time_dimension` extension); and
there is `TimeGrain`. The strategy gap in the report is driven almost
entirely by the first two. The grain drives none of it.

Look at the numbers again with that lens. The move from **off** to **naive**
is the introduction of `is_time` as a signal at all — it takes the flagged
count from zero to eight. The move from **naive** to **curated** is not one
change but two, and they solve different problems. The first is *exclusion*:
the audit pattern removes `created_at` and `updated_at` from the candidate
set, eliminating false positives — columns that are temporal in type but not
time axes in meaning. The second is *designation*: among the columns that
survive as genuine time dimensions, exactly one per table is named the
default. Exclusion cuts the transaction table from five candidates to
three; designation cuts three to one. For the agent task in this example —
pick one `GROUP BY` column — designation is the single most decisive bit in
the entire export, and it is notable that it is exactly the bit OSI core
cannot express. Even a perfectly curated `is_time` leaves the agent facing
three legitimate axes on `transaction_info`; without the `PRIMARY` marker,
booking versus value versus settlement dating remains a one-in-three guess
on the hardest and most consequential part of the question.

`TimeGrain` sits on a different axis entirely — literally. `is_time` and the
primary designation answer a *horizontal* question: which column, among
several, is the time axis. Grain answers a *vertical* question: once the
axis is chosen, how far down may you aggregate it. In this example every
business date is day-grained, so the grain does no discriminating work at
all — deliberately, to keep the axis-selection problem clean. But it guards
against a failure mode the other signals cannot see. Add a month-end
balance-snapshot table to this model, and the danger inverts: the snapshot
date is unambiguous (one temporal column, trivially the primary axis), yet
an agent that groups it by day will happily return a series where each
month's balance appears once and twenty-nine days show nothing — or worse,
joins it to daily transactions and fans the snapshot out thirty-fold. No
amount of `is_time` curation prevents that; only the declaration that the
column's native resolution is `MONTH` does. Grain, in other words, is not
what makes the curated export better than the naive one in this report — it
is what keeps the curated export *correct* once the model grows tables whose
resolutions differ.

So the hierarchy, in descending order of impact on text-to-SQL accuracy for
this class of schema: first, exclusion of audit columns, because false
positives corrupt every downstream choice; second, primary-axis designation,
because it resolves the ambiguity that remains among true positives; third,
the `is_time` flag itself, the base signal both of the above refine; and
fourth, grain, which governs a different error class — aggregation below
native resolution — that only bites once the axis is already correctly
chosen. This ordering is also why the naive strategy is worse than it looks:
it maximizes the base signal while destroying the two refinements that give
the signal its value.

That curation is enforced, not hoped for. The declared axis is validated at
sync time: it must exist and must be a `Date`/`DateTime` column. Grains are
normalized from strings or enum members to a canonical `TimeGrain`, invalid
values fail fast with the legal values listed, and a grain finer than the
physical type can represent (say `hour` on a `DATE` column) raises a warning.
This is the library's core claim applied to time: semantics that drift from
the schema are bugs, and bugs should surface at sync, not in a consumer's
SQL three tools downstream.

Honest issues about the current state. The export is one-way: there is no
OSI-to-semantido importer yet, so semantido is a producer in the OSI
ecosystem, not a full round-trip participant. `Table.primary_key` holds a
single column, so composite primary keys are truncated in the export. The
primary axis is declared via the `__semantic_time_dimension__` class
attribute rather than a decorator keyword, and `TimeGrain` must be imported
from `semantido.generators.semantic_layer` — both small ergonomic seams. And
the SEMANTIDO extensions are, by definition, vendor extensions: a consumer
that ignores them still gets a correct model, but privacy levels and grains
are only *guaranteed* meaningful to SEMANTIDO-aware tooling until OSI
standardizes those concepts.

The takeaway is a division of labor. Author semantics where the schema
lives, because that is the only place drift is caught; interchange them
where the stack lives, because no single tool owns the semantic model
anymore. The one bit OSI gives you for time is worth exactly as much as the
curation behind it.

*The three-strategy comparison in this article is runnable from `examples/02_osi_time_dimension` in the [semantido repository](https://github.com/hikarilabs/semantido); the follow-on question — how the OSI export compares with semantido's Markdown export as LLM prompt context — is the subject of `examples/03_md_vs_osi_context`.*
