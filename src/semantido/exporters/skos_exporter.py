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

"""Exports a ConceptRegistry as a SKOS concept scheme in Turtle.

The registry's model is SKOS-aligned by construction — mapping relations
carry their ``skos:*Match`` predicate, concept relations mirror
``skos:broader`` / ``narrower`` / ``related`` / ``exactMatch`` — so this
exporter is mostly a faithful transcription. One deliberate extension:
SKOS has no disjointness relation between concepts, so ``distinct_from``
(the homonym declaration, semantido's most load-bearing edge) is emitted
as ``smtdo:distinctFrom`` under the semantido vocabulary namespace, with
the pair additionally surfaced in a ``skos:editorialNote`` so consumers
that ignore unknown predicates still see the warning as text.

Zero dependencies: the Turtle is built by hand. Literals are escaped for
quotes, backslashes and newlines; ids are used as URI local names (the
registry already restricts ids to dotted snake_case, which is URI-safe).
"""

from typing import Optional, Union

from semantido.generators.concept_registry import ConceptRegistry
from semantido.generators.semantic_layer import SemanticLayer

#: Vocabulary namespace for semantido-specific extension predicates.
SEMANTIDO_VOCAB = "https://semantido.ai/vocab#"

#: Concept-to-concept relations with a native SKOS predicate.
_RELATION_PREDICATES = {
    "broader": "skos:broader",
    "narrower": "skos:narrower",
    "related": "skos:related",
    "same_as": "skos:exactMatch",
}


def _literal(text: str) -> str:
    """Escapes a string for use as a single-line Turtle literal."""
    escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def _registry_of(source: Union[SemanticLayer, ConceptRegistry]) -> ConceptRegistry:
    if isinstance(source, ConceptRegistry):
        return source
    if source.concept_registry is None:
        raise ValueError("The layer has no concept registry attached")
    return source.concept_registry


def to_skos_turtle(
    source: Union[SemanticLayer, ConceptRegistry],
    base_uri: Optional[str] = None,
) -> str:
    """Serializes the concept registry as a SKOS concept scheme (Turtle).

    Args:
        source: A ``ConceptRegistry``, or a ``SemanticLayer`` carrying one.
        base_uri: Base URI under which concept URIs are minted
            (``{base_uri}{concept_id}``). Defaults to a URN derived from
            the registry namespace (``urn:semantido:{namespace}:``), so
            the export is valid without the caller owning a domain;
            organizations with a concept-URI policy pass their own.

    Returns:
        str: A Turtle document: one ``skos:ConceptScheme`` plus one
        ``skos:Concept`` per registered concept, with labels,
        definitions, synonyms as ``altLabel``, hierarchy/association
        edges, external ``skos:*Match`` mappings resolved against each
        source's namespace, and ``distinct_from`` as
        ``smtdo:distinctFrom`` plus an editorial note.
    """
    registry = _registry_of(source)
    data = registry.to_dict()
    namespace = data.get("namespace", "registry")
    base = base_uri if base_uri is not None else f"urn:semantido:{namespace}:"
    sources = data.get("sources", {})
    concepts = data.get("concepts", {})

    lines = [
        "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
        f"@prefix smtdo: <{SEMANTIDO_VOCAB}> .",
        f"@prefix : <{base}> .",
        "",
        ":scheme a skos:ConceptScheme ;",
        f"    skos:prefLabel {_literal(namespace)} .",
        "",
    ]

    for concept_id, concept in concepts.items():
        triples = [
            f":{concept_id} a skos:Concept",
            "    skos:inScheme :scheme",
            f"    skos:prefLabel {_literal(concept.get('label', concept_id))}",
            f"    skos:definition {_literal(concept.get('definition', ''))}",
        ]
        for synonym in concept.get("synonyms", []) or []:
            triples.append(f"    skos:altLabel {_literal(synonym)}")

        distinct_partners = []
        for relation in concept.get("relations", []) or []:
            kind = relation.get("relation", "")
            target = relation.get("concept", "")
            if kind == "distinct_from":
                triples.append(f"    smtdo:distinctFrom :{target}")
                distinct_partners.append(target)
            elif predicate := _RELATION_PREDICATES.get(kind):
                triples.append(f"    {predicate} :{target}")

        if distinct_partners:
            partners = ", ".join(distinct_partners)
            triples.append(
                "    skos:editorialNote "
                + _literal(
                    "Deliberate homonym: shares a surface form with "
                    f"{partners} but must never be conflated with it."
                )
            )

        for mapping in concept.get("mappings", []) or []:
            source_ns = sources.get(mapping.get("source", ""), {}).get("namespace", "")
            target_uri = f"{source_ns}{mapping.get('target', '')}"
            predicate = mapping.get("skos", "skos:closeMatch")
            triples.append(f"    {predicate} <{target_uri}>")
            if justification := mapping.get("justification"):
                triples.append(
                    f"    smtdo:mappingJustification {_literal(justification)}"
                )

        lines.append(" ;\n".join(triples) + " .")
        lines.append("")

    return "\n".join(lines)


def to_skos_file(
    source: Union[SemanticLayer, ConceptRegistry],
    file_path: str,
    base_uri: Optional[str] = None,
) -> None:
    """Writes the SKOS Turtle serialization to a file.

    Args:
        source: A ``ConceptRegistry``, or a ``SemanticLayer`` carrying one.
        file_path: Destination path for the Turtle file.
        base_uri: See ``to_skos_turtle``.
    """
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(to_skos_turtle(source, base_uri=base_uri))
