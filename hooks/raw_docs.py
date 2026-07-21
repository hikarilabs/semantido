"""Serve every docs page as raw markdown under /raw-docs/, Wren-style.

Lets an LLM (or a curious human) fetch e.g.
  https://semantido.ai/raw-docs/concepts/correctness.md
instead of parsing rendered HTML. Pairs with the 'Ask Claude about this
page' pattern: link to the raw-docs URL in a chat prompt.
"""

import shutil
from pathlib import Path


def on_post_build(config, **kwargs):
    src = Path(config["docs_dir"])
    dst = Path(config["site_dir"]) / "raw-docs"
    for md in src.rglob("*.md"):
        target = dst / md.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(md, target)
