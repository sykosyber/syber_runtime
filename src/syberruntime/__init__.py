"""SyberRuntime operation-primary kernel.

The package root exports the stable kernel surface: the runtime facade, the
operation grammar types, the storage primitives, the model-adapter boundary,
and the typed errors. Evidence tooling (harness, dogfood, acceptance,
scale analysis) and research-phase utilities (merge, confidence, merkle
internals) are imported from their submodules directly.
"""

from syberruntime.adapter_config import AdapterBundle, load_adapter_bundle
from syberruntime.adapters import MCPStdioToolAdapter, ModelAdapter, ScriptedModelAdapter
from syberruntime.ai_contracts import (
    GeneratorOutput,
    ModelRequest,
    ModelResponse,
    ModelSpec,
    PlannerOutput,
    VerifierOutput,
)
from syberruntime.blob_store import BlobStore
from syberruntime.errors import (
    AdapterError,
    BudgetExceededError,
    ModelContractError,
    RoutingError,
    StabilizationBlockedError,
    SyberRuntimeError,
    VerificationError,
)
from syberruntime.intent import IntentMetadata
from syberruntime.models import ArtifactRef, Evaluation, EvaluationStatus, Operation, Provenance, Verb
from syberruntime.operation_log import LogEntry, LogIntegrityError, OperationLog
from syberruntime.policy import FixedPolicy
from syberruntime.projections import RuntimeState, fold_operations
from syberruntime.runtime import Runtime

__all__ = [
    "AdapterBundle",
    "AdapterError",
    "ArtifactRef",
    "BlobStore",
    "BudgetExceededError",
    "Evaluation",
    "EvaluationStatus",
    "FixedPolicy",
    "GeneratorOutput",
    "IntentMetadata",
    "LogEntry",
    "LogIntegrityError",
    "MCPStdioToolAdapter",
    "ModelAdapter",
    "ModelContractError",
    "ModelRequest",
    "ModelResponse",
    "ModelSpec",
    "Operation",
    "OperationLog",
    "PlannerOutput",
    "Provenance",
    "RoutingError",
    "Runtime",
    "RuntimeState",
    "ScriptedModelAdapter",
    "StabilizationBlockedError",
    "SyberRuntimeError",
    "Verb",
    "VerificationError",
    "VerifierOutput",
    "fold_operations",
    "load_adapter_bundle",
]
