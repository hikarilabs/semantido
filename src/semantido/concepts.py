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

"""Authoring façade for the concept tier.

Everything concept-related in one import:

    from semantido.concepts import (
        ConceptRegistry, OntologySource,
        exact_match, close_match, broad_match, narrow_match, related_match,
    )
"""

from semantido.generators.concept_registry import (
    Concept,
    ConceptRegistry,
    ConceptRelation,
    ExternalMapping,
    MappingRelation,
    OntologySource,
    broad_match,
    close_match,
    exact_match,
    narrow_match,
    related_match,
)

__all__ = [
    "Concept",
    "ConceptRegistry",
    "ConceptRelation",
    "ExternalMapping",
    "MappingRelation",
    "OntologySource",
    "broad_match",
    "close_match",
    "exact_match",
    "narrow_match",
    "related_match",
]
