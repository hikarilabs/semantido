# Copyright 2025 Dragos Crintea - HikariLabs LTD
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""TimeGrain-specific utility functions for handling time-aware columns."""

import warnings
from typing import Type, Optional

from sqlalchemy import DateTime, Date

from semantido.generators.semantic_layer import TimeGrain


def normalize_time_grain(
    clazz: Type, column_name: str, raw_grain
) -> Optional[TimeGrain]:
    """
    Normalizes a `<col>_time_grain` attribute to a TimeGrain member.

    Accepts a `TimeGrain` member or a case-insensitive string, so model
    files may write `booking_date_time_grain = "day"` without importing
    the enum. Anything else fails at sync time.

    Args:
        clazz: The model class (for error messages).
        column_name: The column the grain is attached to.
        raw_grain: The raw attribute value, or None.

    Returns:
        Optional[TimeGrain]: The canonical grain, or None if not declared.

    Raises:
        ValueError: If the value is not a valid TimeGrain.
    """
    if raw_grain is None:
        return None
    if isinstance(raw_grain, TimeGrain):
        return raw_grain
    try:
        return TimeGrain(str(raw_grain).upper())
    except ValueError as exc:
        valid = ", ".join(grain.value for grain in TimeGrain)
        raise ValueError(
            f"{clazz.__name__}: {column_name}_time_grain={raw_grain!r} "
            f"is not a valid TimeGrain. Valid values: {valid}"
        ) from exc


def check_grain_supported_by_type(
    clazz: Type, column_name: str, time_grain: TimeGrain, sql_type
) -> None:
    """
    Warns when the declared grain is finer than the column type allows.

    A DATE column cannot carry sub-day information, so declaring e.g.
    `time_grain = "HOUR"` on it is authoring drift: the physical data
    cannot satisfy the semantic claim. This is a warning rather
    than an error because the schema may be mid-migration.

    Args:
        clazz: The model class (for the warning message).
        column_name: The column being checked.
        time_grain: The declared, already-normalized grain.
        sql_type: The SQLAlchemy type instance of the column.
    """
    is_date_only = isinstance(sql_type, Date) and not isinstance(sql_type, DateTime)
    if is_date_only and time_grain < TimeGrain.DAY:
        warnings.warn(
            f"{clazz.__name__}.{column_name}: time_grain="
            f"{time_grain.value} is finer than the DATE column type can "
            f"represent; the declared grain cannot be satisfied by the "
            f"data.",
            UserWarning,
            stacklevel=2,
        )
