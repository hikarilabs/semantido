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

"""Semantic layer JSON exporter"""

import json

from semantido import SemanticLayer


def to_json(semantic_layer: SemanticLayer, include_empty: bool = False) -> str:
    """
    Export the semantic layer as a formatted JSON string.

    Args:
        semantic_layer: SemanticLayer built from SQLAlchemy models
        include_empty: Whether to include empty values in the JSON output,
        as some semantic layer values are optional and may not be present.

    Returns:
            str: Indented JSON string representing the semantic layer.
    """
    return json.dumps(semantic_layer.to_dict(include_empty=include_empty), indent=4)


def to_json_file(
    layer: SemanticLayer, file_path: str, include_empty: bool = False
) -> None:
    """
    Serializes and saves the semantic layer to a JSON file.

    Args:
        layer: The SemanticLayer instance to export.
        file_path: The filesystem path where the JSON file will be created.
        include_empty: If False (default), removes null and empty collection values.
    """
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(layer.to_dict(include_empty=include_empty), f, indent=4)
