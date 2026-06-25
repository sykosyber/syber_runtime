from __future__ import annotations

import json
import tempfile

from syberruntime.hashing import canonical_json
from syberruntime.policy import FixedPolicy
from syberruntime.runtime import Runtime


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        runtime = Runtime(tmp, policy=FixedPolicy(default_profile="production"))
        thread = runtime.create_thread(intent="Build a Phase 4 demonstrator artifact")
        feature = runtime.record_feature(
            thread.operation.thread_id,
            artifact_name="demo.txt",
            content="release-token\n",
            intent="Create a traced artifact",
            assumptions=(
                {
                    "claim": "A text artifact is enough for the demonstrator",
                    "depends_on": "The verifier checks a textual release token",
                    "confidence_rationale": "The deterministic oracle observes the token",
                    "alternatives_considered": "JSON artifact",
                },
            ),
        )
        digest = feature.operation.outputs[0].digest
        runtime.record_test(
            thread.operation.thread_id,
            artifact_digest=digest,
            check={"kind": "text_equals", "expected": "release-token\n"},
        )
        runtime.stabilize(thread.operation.thread_id, artifact_digest=digest)
        _entry, report = runtime.run_mutation_campaign(
            thread.operation.thread_id,
            artifact_digest=digest,
            check={"kind": "text_equals", "expected": "release-token\n"},
        )
        snapshot = runtime.create_snapshot()
        result = {
            "artifact_digest": digest,
            "mutation_report": report.to_dict(),
            "metrics": runtime.metrics().to_dict(),
            "merkle_root": runtime.merkle_root_hash(),
            "snapshot": snapshot.to_dict(),
            "inspection": runtime.inspect_artifact(digest),
        }
        print(json.dumps(json.loads(canonical_json(result)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
