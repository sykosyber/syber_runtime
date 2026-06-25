"""PROV and RO-Crate style exports."""

from __future__ import annotations

from typing import Any

from syberruntime.projections import RuntimeState


def export_prov_document(state: RuntimeState) -> dict[str, Any]:
    entities = {}
    activities = {}
    agents = {}
    was_generated_by = {}
    used = {}
    was_associated_with = {}
    was_derived_from = {}

    for operation_id, operation in state.operations.items():
        activity_id = f"operation:{operation_id}"
        agent_id = f"agent:{operation.provenance.actor}"
        activities[activity_id] = {
            "prov:type": operation.type,
            "syber:thread": operation.thread_id,
            "syber:center": operation.center_id,
            "prov:startTime": operation.provenance.ts,
            "syber:evaluation": operation.evaluation.to_dict(),
        }
        agents.setdefault(agent_id, {"prov:type": "syber:Actor", "syber:actor": operation.provenance.actor})
        was_associated_with[f"assoc:{operation_id}"] = {
            "prov:activity": activity_id,
            "prov:agent": agent_id,
        }
        for ref in operation.inputs:
            entity_id = f"artifact:{ref.digest}"
            entities.setdefault(entity_id, _artifact_entity(ref))
            used[f"used:{operation_id}:{ref.digest}"] = {
                "prov:activity": activity_id,
                "prov:entity": entity_id,
            }
        for ref in operation.outputs:
            entity_id = f"artifact:{ref.digest}"
            entities[entity_id] = _artifact_entity(ref)
            was_generated_by[f"gen:{ref.digest}:{operation_id}"] = {
                "prov:entity": entity_id,
                "prov:activity": activity_id,
            }
            for parent in operation.parents:
                was_derived_from[f"derive:{ref.digest}:{parent}"] = {
                    "prov:generatedEntity": entity_id,
                    "prov:usedEntity": f"operation:{parent}",
                }

    return {
        "prefix": {
            "prov": "http://www.w3.org/ns/prov#",
            "syber": "https://syberlabs.local/ns/syberruntime#",
        },
        "entity": entities,
        "activity": activities,
        "agent": agents,
        "wasGeneratedBy": was_generated_by,
        "used": used,
        "wasAssociatedWith": was_associated_with,
        "wasDerivedFrom": was_derived_from,
    }


def export_ro_crate(state: RuntimeState) -> dict[str, Any]:
    graph: list[dict[str, Any]] = [
        {
            "@id": "ro-crate-metadata.json",
            "@type": "CreativeWork",
            "about": {"@id": "./"},
        },
        {
            "@id": "./",
            "@type": "Dataset",
            "name": "SyberRuntime operation graph export",
            "hasPart": [{"@id": f"artifact:{digest}"} for digest in sorted(state.artifacts)],
        },
    ]

    for digest, artifact in sorted(state.artifacts.items()):
        graph.append(
            {
                "@id": f"artifact:{digest}",
                "@type": "File",
                "name": artifact.ref.name or digest,
                "encodingFormat": artifact.ref.media_type,
                "contentSize": artifact.ref.size,
                "sha256": digest,
                "syber:createdBy": {"@id": f"operation:{artifact.created_by}"},
                "syber:stabilizedBy": {"@id": f"operation:{artifact.stabilized_by}"}
                if artifact.stabilized_by
                else None,
            }
        )

    for operation_id, operation in sorted(state.operations.items()):
        graph.append(
            {
                "@id": f"operation:{operation_id}",
                "@type": "CreateAction" if operation.outputs else "Action",
                "name": operation.type,
                "agent": operation.provenance.actor,
                "startTime": operation.provenance.ts,
                "object": [{"@id": f"artifact:{ref.digest}"} for ref in operation.inputs],
                "result": [{"@id": f"artifact:{ref.digest}"} for ref in operation.outputs],
                "syber:evaluation": operation.evaluation.to_dict(),
                "syber:assumptions": list(operation.provenance.assumptions),
            }
        )

    return {
        "@context": [
            "https://w3id.org/ro/crate/1.1/context",
            {"syber": "https://syberlabs.local/ns/syberruntime#"},
        ],
        "@graph": graph,
    }


def _artifact_entity(ref: Any) -> dict[str, Any]:
    return {
        "prov:type": "syber:Artifact",
        "syber:digest": ref.digest,
        "syber:size": ref.size,
        "syber:mediaType": ref.media_type,
        "syber:name": ref.name,
    }
