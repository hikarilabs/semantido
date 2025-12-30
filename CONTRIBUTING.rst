
How to contribute
============
Contributions are welcome and encouraged! This project aims to provide solid foundations for production text-to-SQL systems
while staying out of your way.

Guidelines for making ``semantido`` the coolest sematic wrapper for SQLAlchemy.

#. Fork the repo, develop and test your code changes, add docs.
#. Make sure that your commit messages clearly describe the changes.
#. Send a pull request.
#. Report bugs or suggest features via GitHub Issues
#. Submit PRs for bug fixes or enhancements (tests appreciated)
#. Improve documentation or add examples
#. Share your use cases, they help shape the roadmap


Making changes
--------------
Some notes on making changes to ``semantido``.
- If you've added a new feature or modified an existing feature, make sure to
  add or update any applicable documentation in docstrings and in the
  documentation (in ``docs/``). The reference documentation can be re-generated
  using ``nox -s docgen``.

- The codebase *aims* for 100% test coverage after each commit. This is a guideline, not a *must*.
  You can test coverage with ``nox -e cover``.

Testing changes
---------------
To test your changes, run unit tests with ``nox``::
    $ nox -s unit


Coding Style
------------
This library is PEP8 & Pylint compliant. Our Pylint config is defined at
``pylintrc`` for package code and ``pylintrc.tests`` for test code. Use
``nox`` to check for non-compliant code::
   $ nox -s lint

Documentation Coverage and Building HTML Documentation
------------------------------------------------------
If you fix a bug, and the bug requires an API or behavior modification, all
documentation in this package which references that API or behavior must be
changed to reflect the bug fix, ideally in the same commit that fixes the bug
or adds the feature.
To build and review docs use  ``nox``::
   $ nox -s docs
The HTML version of the docs will be built in ``docs/_build/html``

Versioning
----------
This library follows `Semantic Versioning`_.
.. _Semantic Versioning: http://semver.org/
It is currently in minor version zero (``0.y.z``), which means that anything
may change at any time and the public API should not be considered
stable.
