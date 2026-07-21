---
title: Why is the output deterministic?
description: semantido exports are a pure function of your model files — byte-identical, committable, diffable, cacheable.
---

# Why is the output deterministic?

Given the same models, semantido always produces byte-identical exports.

This sounds like an implementation detail. It is the reason the artifacts are useful.

## What it buys you

**You can commit the export.** A generated `model.osi.yaml` in the repo is only meaningful if regenerating it on an unchanged schema produces no diff. Otherwise the file churns on every CI run and everyone learns to ignore it.

**You can diff the export.** This is the one that matters in regulated environments. When the definition of `notional` changes, the diff shows exactly that — a semantic change, isolated, reviewable, attributable to a commit and an author. "The AI decided" is not an audit response. "Here is the versioned definition, here is the PR, here is the reviewer" is.

**You can test the export.** A snapshot test on the generated Markdown is a real regression test. It fails when someone drops an annotation, which is exactly the failure you cannot otherwise see.

**You can cache the export.** The layer is a pure function of the model files. Build it once at import, not per request.

**You can gate on the export.** See [Versioning and CI](../guides/versioning-and-ci.md) for the check that fails a PR when a new column arrives with no description.

## Where the determinism comes from

Two properties, both structural:

- **No I/O.** `sync_semantic_layer()` reads the SQLAlchemy registry. It does not connect to a database, does not call an LLM, does not read the network. There is nothing in the path that can vary.
- **Stable ordering.** Tables, columns, and relationships are emitted in the order the mapper reports them, which is the order they are declared in your files.

The corollary is that the export is only as stable as your model files. If your models are generated at runtime, or you conditionally register mappers based on environment, you have introduced the non-determinism yourself.

## What semantido deliberately does not do

Some semantic layer systems get smarter over time: they store confirmed question–SQL pairs, index them, and retrieve them as few-shot examples for similar future questions. It is a genuinely good idea and it makes those systems better with use.

semantido has no such loop, on purpose.

A memory system makes the layer's output a function of its usage history. That is the right trade for a hosted product with a feedback UI. It is the wrong trade for an artifact that has to be reproducible from the repo alone — you can no longer regenerate last quarter's semantic model from last quarter's commit, because the memory has moved on.

**Keep the substrate deterministic and put the learning above it.** If you want query recall, build it in your pipeline: store the confirmed pairs, retrieve them, and concatenate them with the semantido export. The context layer stays reproducible; the example layer gets to be adaptive.

## In short

- Same models in, byte-identical document out.
- That is what makes it committable, diffable, testable, and auditable.
- Learning is a feature of the pipeline, not the substrate.
