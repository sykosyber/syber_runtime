"""Command line surface for SyberRuntime kernel operations and release gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import uuid4

from syberruntime.acceptance import run_v1_acceptance_audit
from syberruntime.adapter_config import load_adapter_bundle
from syberruntime.dogfood import create_dogfood_report, write_dogfood_report
from syberruntime.harness import (
    default_live_scale_tasks,
    run_live_agent_harness,
    run_scripted_agent_harness,
    write_harness_report,
)
from syberruntime.hashing import canonical_json
from syberruntime.runtime import Runtime


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="syber")
    parser.add_argument("--root", default=".syberruntime", help="Runtime storage root.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create-thread")
    create_parser.add_argument("--intent", required=True)

    fork_parser = subparsers.add_parser("fork-thread")
    fork_parser.add_argument("source_thread_id")
    fork_parser.add_argument("--intent", required=True)

    feature_parser = subparsers.add_parser("feature")
    feature_parser.add_argument("thread_id")
    feature_parser.add_argument("--artifact-name", required=True)
    feature_parser.add_argument("--intent", required=True)
    feature_parser.add_argument("--generative-mass", type=float, default=1.0)
    feature_parser.add_argument("--blast-radius", type=float, default=1.0)
    feature_parser.add_argument("--criticality", type=float, default=1.0)
    content_group = feature_parser.add_mutually_exclusive_group(required=True)
    content_group.add_argument("--text")
    content_group.add_argument("--file", type=Path)

    test_parser = subparsers.add_parser("test")
    test_parser.add_argument("thread_id")
    test_parser.add_argument("artifact_digest")
    test_parser.add_argument("--intent", default="Run deterministic verification against the artifact.")
    check_group = test_parser.add_mutually_exclusive_group(required=True)
    check_group.add_argument("--text-contains")
    check_group.add_argument("--text-equals")
    check_group.add_argument("--sha256-equals")

    stabilize_parser = subparsers.add_parser("stabilize")
    stabilize_parser.add_argument("thread_id")
    stabilize_parser.add_argument("--artifact-digest")
    stabilize_parser.add_argument("--intent", default="Stabilize the current artifact projection.")

    mutation_parser = subparsers.add_parser("mutation-campaign")
    mutation_parser.add_argument("thread_id")
    mutation_parser.add_argument("artifact_digest")
    mutation_check_group = mutation_parser.add_mutually_exclusive_group(required=True)
    mutation_check_group.add_argument("--text-contains")
    mutation_check_group.add_argument("--text-equals")
    mutation_check_group.add_argument("--sha256-equals")

    ai_loop_parser = subparsers.add_parser("ai-loop")
    ai_loop_parser.add_argument("--config", required=True, type=Path)
    ai_loop_parser.add_argument("--intent", required=True)
    ai_loop_parser.add_argument("--artifact-name", required=True)
    ai_loop_parser.add_argument("--thread-id")
    ai_loop_parser.add_argument("--center-id", default="root")

    subparsers.add_parser("inspect")
    inspect_artifact_parser = subparsers.add_parser("inspect-artifact")
    inspect_artifact_parser.add_argument("artifact_digest")

    subparsers.add_parser("metrics")
    subparsers.add_parser("merkle-root")

    inclusion_parser = subparsers.add_parser("inclusion-proof")
    inclusion_parser.add_argument("index", type=int)

    consistency_parser = subparsers.add_parser("consistency-proof")
    consistency_parser.add_argument("old_size", type=int)
    consistency_parser.add_argument("--new-size", type=int)

    subparsers.add_parser("snapshot")
    subparsers.add_parser("export-prov")
    subparsers.add_parser("export-ro-crate")

    shred_parser = subparsers.add_parser("shred-blob")
    shred_parser.add_argument("artifact_digest")
    shred_parser.add_argument("--reason", default="deletion-rights request")

    dogfood_parser = subparsers.add_parser("dogfood-report")
    dogfood_parser.add_argument("--protocol", default="docs/rq0_rq6_preregistration.md")
    dogfood_parser.add_argument("--output", required=True, type=Path)
    dogfood_parser.add_argument("--notes", required=True)
    dogfood_parser.add_argument("--artifact-digest", action="append", default=[])

    harness_parser = subparsers.add_parser("agent-harness")
    harness_parser.add_argument("action", choices=("run",))
    harness_parser.add_argument("--mode", choices=("scripted", "live"), default="scripted")
    harness_parser.add_argument("--config", type=Path)
    harness_parser.add_argument("--protocol", default="docs/agentic_intent_harness.md")
    harness_parser.add_argument("--output", type=Path)
    harness_parser.add_argument("--run-id")
    harness_parser.add_argument("--principal", default="agent-harness-v0")
    harness_parser.add_argument("--benchmark-id", default="agentic-intent-harness-v0")
    harness_parser.add_argument("--acceptance-authority", default="deterministic-oracle")
    harness_parser.add_argument("--task-set", choices=("smoke", "scale3"), default="smoke")

    acceptance_parser = subparsers.add_parser("acceptance-check")
    acceptance_parser.add_argument("--mcp-config", type=Path)
    acceptance_parser.add_argument("--dogfood-report-dir", type=Path)
    acceptance_parser.add_argument("--agent-harness-report-dir", type=Path)

    subparsers.add_parser("replay-check")

    args = parser.parse_args(argv)
    runtime = Runtime(args.root)

    if args.command == "create-thread":
        entry = runtime.create_thread(intent=args.intent)
        _print_json({"entry": entry.to_dict()})
    elif args.command == "fork-thread":
        entry = runtime.fork_thread(args.source_thread_id, intent=args.intent)
        _print_json({"entry": entry.to_dict()})
    elif args.command == "feature":
        content = args.file.read_bytes() if args.file else args.text
        entry = runtime.record_feature(
            args.thread_id,
            artifact_name=args.artifact_name,
            content=content,
            intent=args.intent,
            generative_mass=args.generative_mass,
            blast_radius=args.blast_radius,
            criticality=args.criticality,
        )
        _print_json({"entry": entry.to_dict()})
    elif args.command == "test":
        check = _check_from_args(args)
        entry = runtime.record_test(
            args.thread_id,
            artifact_digest=args.artifact_digest,
            check=check,
            intent=args.intent,
        )
        _print_json({"entry": entry.to_dict()})
    elif args.command == "stabilize":
        entry = runtime.stabilize(
            args.thread_id,
            artifact_digest=args.artifact_digest,
            intent=args.intent,
        )
        _print_json({"entry": entry.to_dict()})
    elif args.command == "mutation-campaign":
        check = _check_from_args(args)
        entry, report = runtime.run_mutation_campaign(
            args.thread_id,
            artifact_digest=args.artifact_digest,
            check=check,
        )
        _print_json({"entry": entry.to_dict(), "report": report.to_dict()})
    elif args.command == "ai-loop":
        bundle = load_adapter_bundle(args.config)
        result = runtime.run_ai_loop(
            intent=args.intent,
            artifact_name=args.artifact_name,
            planner=bundle.planner,
            generator=bundle.generator,
            verifier=bundle.verifier,
            thread_id=args.thread_id,
            center_id=args.center_id,
        )
        _print_json(result.to_dict())
    elif args.command == "inspect":
        _print_json(runtime.rebuild_state().to_dict())
    elif args.command == "inspect-artifact":
        _print_json(runtime.inspect_artifact(args.artifact_digest))
    elif args.command == "metrics":
        _print_json(runtime.metrics().to_dict())
    elif args.command == "merkle-root":
        _print_json({"root_hash": runtime.merkle_root_hash()})
    elif args.command == "inclusion-proof":
        proof = runtime.inclusion_proof(args.index)
        _print_json({"proof": proof.to_dict(), "verified": proof.verify()})
    elif args.command == "consistency-proof":
        proof = runtime.consistency_proof(args.old_size, args.new_size)
        _print_json({"proof": proof.to_dict(), "verified": proof.verify()})
    elif args.command == "snapshot":
        _print_json({"snapshot": runtime.create_snapshot().to_dict()})
    elif args.command == "export-prov":
        _print_json(runtime.export_prov())
    elif args.command == "export-ro-crate":
        _print_json(runtime.export_ro_crate())
    elif args.command == "shred-blob":
        _print_json(
            {
                "artifact_digest": args.artifact_digest,
                "shredded": runtime.shred_blob(args.artifact_digest, reason=args.reason),
            }
        )
    elif args.command == "dogfood-report":
        report = create_dogfood_report(
            runtime,
            protocol_path=args.protocol,
            notes=args.notes,
            artifact_digests=tuple(args.artifact_digest),
        )
        path = write_dogfood_report(report, args.output)
        _print_json({"path": str(path), "report": report.to_dict()})
    elif args.command == "agent-harness":
        run_id = args.run_id or f"agent-harness-{uuid4().hex}"
        output = args.output or Path("docs") / "agentic_harness_reports" / f"{run_id}.json"
        if args.mode == "live":
            if args.config is None:
                parser.error("agent-harness --mode live requires --config")
            principal = (
                "agent-harness-live-v1"
                if args.principal == "agent-harness-v0"
                else args.principal
            )
            benchmark_id = (
                "agentic-intent-harness-live-v1"
                if args.benchmark_id == "agentic-intent-harness-v0"
                else args.benchmark_id
            )
            acceptance_authority = (
                "provider-verifier-and-deterministic-oracle"
                if args.acceptance_authority == "deterministic-oracle"
                else args.acceptance_authority
            )
            report = run_live_agent_harness(
                runtime_root=args.root,
                protocol_path=args.protocol,
                run_id=run_id,
                config_path=args.config,
                principal=principal,
                benchmark_id=benchmark_id,
                acceptance_authority=acceptance_authority,
                tasks=default_live_scale_tasks() if args.task_set == "scale3" else None,
            )
        else:
            report = run_scripted_agent_harness(
                runtime_root=args.root,
                protocol_path=args.protocol,
                run_id=run_id,
                principal=args.principal,
                benchmark_id=args.benchmark_id,
                acceptance_authority=args.acceptance_authority,
            )
        path = write_harness_report(report, output)
        _print_json({"path": str(path), "report": report.to_dict()})
    elif args.command == "acceptance-check":
        _print_json(
            run_v1_acceptance_audit(
                mcp_config_path=args.mcp_config,
                dogfood_report_dir=args.dogfood_report_dir,
                agent_harness_report_dir=args.agent_harness_report_dir,
            ).to_dict()
        )
    elif args.command == "replay-check":
        _print_json({"deterministic": runtime.replay_is_deterministic()})
    else:
        parser.error(f"Unknown command: {args.command}")
    return 0


def _print_json(value: dict) -> None:
    print(json.dumps(json.loads(canonical_json(value)), indent=2, sort_keys=True))


def _check_from_args(args: argparse.Namespace) -> dict:
    if args.text_contains is not None:
        return {"kind": "text_contains", "expected": args.text_contains}
    if args.text_equals is not None:
        return {"kind": "text_equals", "expected": args.text_equals}
    if args.sha256_equals is not None:
        return {"kind": "sha256_equals", "expected": args.sha256_equals}
    raise ValueError("No deterministic check supplied")


if __name__ == "__main__":
    raise SystemExit(main())
