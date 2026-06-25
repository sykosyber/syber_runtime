"""SyberRuntime operation-primary kernel."""

from syberruntime.blob_store import BlobStore
from syberruntime.adapters import MCPJsonAdapter, MCPStdioToolAdapter, ModelAdapter, ScriptedModelAdapter
from syberruntime.ai_contracts import (
    Assumption,
    GeneratorOutput,
    LocatedError,
    ModelRequest,
    ModelResponse,
    ModelSpec,
    PlannedStep,
    PlannerOutput,
    VerifierOutput,
)
from syberruntime.acceptance import AcceptanceCriterion, AcceptanceReport, run_v1_acceptance_audit
from syberruntime.adapter_config import AdapterBundle, load_adapter_bundle
from syberruntime.confidence import ConformalCalibrator, ConformalSet
from syberruntime.debt import DebtLedger, DebtObligation, ObligationStatus
from syberruntime.dogfood import (
    DogfoodReport,
    create_dogfood_report,
    discover_dogfood_reports,
    load_dogfood_report,
    write_dogfood_report,
)
from syberruntime.errors import (
    AdapterError,
    BudgetExceededError,
    ModelContractError,
    RoutingError,
    StabilizationBlockedError,
    SyberRuntimeError,
    VerificationError,
)
from syberruntime.export import export_prov_document, export_ro_crate
from syberruntime.harness import (
    HarnessReport,
    HarnessTask,
    HarnessTaskResult,
    default_scripted_tasks,
    discover_harness_reports,
    load_harness_report,
    run_live_agent_harness,
    run_scripted_agent_harness,
    validate_harness_report,
    write_harness_report,
)
from syberruntime.inspector import inspect_artifact
from syberruntime.intent import IntentMetadata
from syberruntime.merge import MergeConflict, MergeError, MergeResult, merge_operation_sequences
from syberruntime.merkle import (
    ConsistencyProof,
    InclusionProof,
    MerkleHistoryTree,
    MerkleProofError,
    merkle_root,
    verify_consistency,
    verify_inclusion,
)
from syberruntime.metrics import RuntimeMetrics, compute_runtime_metrics
from syberruntime.models import ArtifactRef, Evaluation, EvaluationStatus, Operation, Provenance, Verb
from syberruntime.mutation import Mutant, MutantResult, MutationCampaignReport, TextMutationHarness
from syberruntime.operation_log import LogEntry, LogIntegrityError, OperationLog
from syberruntime.orchestration import AIOperationResult
from syberruntime.policy import CenterPolicy, FixedPolicy, RigorProfile
from syberruntime.projections import ArtifactState, ProjectionError, RuntimeState, ThreadState, fold_operations
from syberruntime.runtime import Runtime
from syberruntime.snapshots import Snapshot, SnapshotStore, make_snapshot
from syberruntime.verification import DeterministicVerifier, VerificationResult

__all__ = [
    "ArtifactRef",
    "ArtifactState",
    "AdapterError",
    "AIOperationResult",
    "AcceptanceCriterion",
    "AcceptanceReport",
    "AdapterBundle",
    "Assumption",
    "BlobStore",
    "BudgetExceededError",
    "CenterPolicy",
    "ConformalCalibrator",
    "ConformalSet",
    "ConsistencyProof",
    "DebtLedger",
    "DebtObligation",
    "DeterministicVerifier",
    "DogfoodReport",
    "Evaluation",
    "EvaluationStatus",
    "FixedPolicy",
    "GeneratorOutput",
    "HarnessReport",
    "HarnessTask",
    "HarnessTaskResult",
    "InclusionProof",
    "IntentMetadata",
    "LocatedError",
    "LogEntry",
    "LogIntegrityError",
    "MCPJsonAdapter",
    "MCPStdioToolAdapter",
    "MergeConflict",
    "MergeError",
    "MergeResult",
    "MerkleHistoryTree",
    "MerkleProofError",
    "ModelAdapter",
    "ModelContractError",
    "ModelRequest",
    "ModelResponse",
    "ModelSpec",
    "Mutant",
    "MutantResult",
    "MutationCampaignReport",
    "ObligationStatus",
    "Operation",
    "OperationLog",
    "PlannedStep",
    "PlannerOutput",
    "ProjectionError",
    "Provenance",
    "RigorProfile",
    "RoutingError",
    "Runtime",
    "RuntimeMetrics",
    "RuntimeState",
    "ScriptedModelAdapter",
    "Snapshot",
    "SnapshotStore",
    "StabilizationBlockedError",
    "SyberRuntimeError",
    "TextMutationHarness",
    "ThreadState",
    "VerificationError",
    "VerificationResult",
    "VerifierOutput",
    "Verb",
    "compute_runtime_metrics",
    "create_dogfood_report",
    "default_scripted_tasks",
    "discover_harness_reports",
    "discover_dogfood_reports",
    "export_prov_document",
    "export_ro_crate",
    "fold_operations",
    "inspect_artifact",
    "load_adapter_bundle",
    "load_dogfood_report",
    "load_harness_report",
    "make_snapshot",
    "merkle_root",
    "merge_operation_sequences",
    "verify_consistency",
    "verify_inclusion",
    "run_v1_acceptance_audit",
    "run_scripted_agent_harness",
    "run_live_agent_harness",
    "validate_harness_report",
    "write_dogfood_report",
    "write_harness_report",
]
