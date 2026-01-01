
# How to contribute
Contributions are welcome and encouraged! This project aims to provide a solid foundations for production text-to-SQL systems while staying out of your way.

Guidelines for making `semantido` the coolest semantic wrapper for SQLAlchemy:

1. Fork the repo, develop and test your code changes, add docs.
2. Make sure that your commit messages clearly describe the changes.
3. Send a pull request.
4. Report bugs or suggest features via GitHub Issues.
5. Submit PRs for bug fixes or enhancements (tests appreciated).
6. Improve documentation or add examples.
7. Share your use cases, they help shape the roadmap.

To install the project along with the dev optional dependencies run:

```bash
$ pip install ".[dev]"
```

Making changes
-----
Some notes on making changes to ``semantido``.
- If you've added a new feature or modified an existing feature, make sure to  add or update any applicable documentation in docstrings and in the
documentation (in ``docs/``). The reference documentation can be re-generated with:
```bash
nox -s docgen
```

- The codebase *aims* for greater than 90% test coverage after each commit. This is a guideline, not a *must*.
  You can test coverage with:

```bash
$ pytest --cov=semantido tests/
```

Testing changes
-----
This project uses hatch as the "all-in-one" project manager. To test your changes, run unit tests with ``hatch``.
```bash
$ hatch test
```

Coding Style
-----
This library is PEP8 & Pylint compliant. Pylint config is defined at
``.pylintrc`` for package code. Use default pylint command to check for non-compliant code 

```bash
$ pylint src/*
```

Documentation Coverage and Markdown Documentation
-----
If you fix a bug, all documentation which references the change must be updated to reflect the fix, ideally in the same commit.
To build and review docs use  ``nox``::
   $ nox -s docs
The Markdown version of the docs will be built in ``docs/``

Versioning
-----
This library follows `Semantic Versioning`: http://semver.org/
It is currently in minor alpha version 1 (``x.1.z``), which means that anything
may change at any time and the semantic wrapper should not be considered stable.
