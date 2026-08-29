"""The to_osi_* names were renamed to to_ossie_* in 0.5.1.

Code written against 0.5.0 called the old names. These tests pin the
compatibility shim so the rename cannot silently break a reader's script
again, and so removal in 0.7 is a deliberate act rather than an accident.
"""

import warnings

import pytest

from semantido import exporters


def test_deprecated_aliases_are_exported():
    assert "to_osi_yaml" in exporters.__all__
    assert "to_osi_dict" in exporters.__all__


@pytest.mark.parametrize(
    "old, new",
    [("to_osi_yaml", "to_ossie_yaml"), ("to_osi_dict", "to_ossie_dict")],
)
def test_alias_warns_and_names_replacement(old, new):
    alias = getattr(exporters, old)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(Exception):
            alias(None, model_name="irrelevant")
    assert caught, f"{old}() did not warn"
    assert caught[0].category is DeprecationWarning
    message = str(caught[0].message)
    assert new in message, f"warning should name {new}"
    assert "0.7" in message, "warning should state the removal version"
