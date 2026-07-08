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

"""Semnatido specific utility functions for handling slqalchemy metadata exports
andß time-aware columns."""

from semantido.generators.utils.time_grain import (
    normalize_time_grain,
    check_grain_supported_by_type,
)
from semantido.generators.utils.sqlalchemy_mapping import (
    map_sqlalchemy_type,
    build_join_condition,
)

__all__ = [
    "normalize_time_grain",
    "check_grain_supported_by_type",
    "map_sqlalchemy_type",
    "build_join_condition",
]
