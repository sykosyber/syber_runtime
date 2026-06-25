# SyberRuntime v1 — Implementation Roadmap
## From specification to a working, measured kernel

**Status:** Implementation plan, derived from the v0.6 spec + the Verification Playbook + the Deep-Theory Foundations.
**Premise:** the theory is complete enough. v1 exists to (a) pass the first-validation gate, (b) run the full generate→debt→verify→stabilize loop with real AI, (c) *measure* discharge efficiency rather than assume it, and (d) produce the RQ0/RQ6 empirical results that convert the spec into an institutional ask. v1 is the **kernel** — nothing more.

---

## 0. What v1 is — and is not

**v1 IS the kernel:** an event-sourced operation runtime; a Merkle-linked, content-addressed Archive; the verification-debt engine with the generative grammar under fixed rigor profiles; one MCP adapter; a deterministic-first, cross-model Tribunal-lite; a minimal Code Forge; and an inspectable provenance/debt surface.

**v1 is NOT:** Diagrammer, Simulator, Studio, the full Lab; VS Code / Browser / GitHub / CLI adapters beyond MCP; multi-user/CRDT sync; the endogenous self-calibrating controller; typed debt; formal-methods verification; ZK proof-carrying artifacts; the RQ1 environment study. All of these are post-v1, and the kernel must *earn* them with results.

**The discipline that governs every decision below:** scope creep has been the dominant risk since v0.1. The antidote is the **walking skeleton** — build the thinnest end-to-end loop first, get to a testable claim fast, and resist breadth until the core loop is real and measured.

---

## 1. The one open decision: the runtime stack

This has been deferred since v0.2; a roadmap cannot defer it further. The tension is real: the *runtime core* (event-sourced, concurrent, durable, local-first daemon, Merkle log) favors **Go**; the *AI and measurement periphery* (MCP, model clients, conformal calibration, mutation testing, RQ0/RQ6 statistics) favors **Python**.

**Recommendation: Python for v1**, with the event-sourced core written as a pure `fold(log) → state` so a Go (or Rust) reimplementation of the runtime is a tractable v2+ option if performance or distribution ever demands it. Reasoning:

- v1 is **single-user, single-machine, local-first**. Concurrency is modest (handfuls of threads/operations, not millions), and the hardest event-sourcing problems — distributed ordering, eventual consistency, event collisions — are *absent* at this scale. Python's `asyncio` is more than sufficient.
- The dominant v1 costs are **iteration velocity** (solo founder) and **AI + measurement integration** (the entire verification, rigor-metabolism, and RQ machinery is model-calling and statistical analysis). Python wins both decisively, and it is your native tongue from the ML work.
- Event sourcing is **inherently portable**: because state is a pure fold over an append-only log, the core logic is a pure function; a later Go port is unusually tractable *because* the design is event-sourced.
- Hot-path escape hatch: if the Merkle log or projection rebuild becomes a measured bottleneck, drop that one path to a Rust/Go extension via FFI — don't rewrite the kernel.

**The one call you might override:** if your priority is the systems-craftsmanship signal (a single-binary Go daemon reads as serious infrastructure to an Anthropic reviewer) or you intend the runtime to be production-grade from day one, choose Go and keep the measurement tooling in Python around it. That is a defensible inversion of the same tradeoff; it costs velocity to buy polish. The rest of this roadmap is stack-agnostic.

**Concrete v1 stack (Python path):** Python 3.12+, `asyncio` for the operation scheduler; SQLite (or a single append-only file + index) for the operation log; content-addressed blob store on the filesystem (`blake3`/`sha256` keys); the MCP SDK for inference; `pytest` + `hypothesis` (property-based) for tests; a thin local web UI (FastAPI + a single HTML/SVG page) for the inspection surface.

---

## 2. The v1 data model

The data model is the spine, and operation identity is its keystone (the answer to the long-open data-model question). Everything is a projection of one append-only, Merkle-linked log of operations.

### 2.1 The Operation (the atomic, append-only record)

```
Operation {
  id:        content_hash(type, inputs, params, parents, nonce)   # stable, content-addressed identity
  prev_hash: hash            # hash-chain link to the previous log entry (tamper-evidence)
  type:      Feature | Test | Refactor | Research | Verify | Compress | Simulate | Stabilize
  thread_id: id              # which operation-graph
  center_id: id              # scope of the rigor regime
  parents:   [op_id]         # DAG edges: fork = parent with >1 child; merge = op with >1 parent
  inputs:    [artifact_ref]  # content-hash references (never inline payloads — keep events lean)
  params:    { intent, adapter_bindings, budget_alloc, model_assignment }
  outputs:   [artifact_ref]  # produced artifacts, content-addressed
  evaluation: {
     question:    str                         # the operation's own success question
     obligations: [obligation_id]             # paired evaluation obligations (the grammar)
     status:      unverified | partial | full
     confidence:  { conformal_set, regime }   # calibrated from history — NOT verbalized
  }
  provenance: {                               # how-provenance (the most general; cheaper views project from it)
     actor:      human | model_id
     retrievals: [...]
     decisions:  [...]
     assumptions:[ {claim, depends_on, confidence, alternatives} ]   # the metacognitive ledger
     ts:         timestamp
  }
}
```

### 2.2 The stores
- **Operation log:** append-only, hash-chained, with a **Merkle history tree** over entries → O(log n) inclusion proofs ("this artifact derives from this history") and consistency proofs ("the log was only appended to, never rewritten"). v1.0 can ship the hash-chain and add the full Merkle tree in Phase 4.
- **Content-addressed blob store:** artifact payloads keyed by hash; operations reference blobs, never inline them (the event-sourcing lean-state discipline).

### 2.3 The projections (folds over the log; materialized on demand, snapshotted for rebuild)
- **Artifact state** — current materialized artifacts (`artifact = fold(log)`).
- **Operation-graph view** — the typed DAG (this is the provenance the human reads).
- **Verification-debt ledger** — per artifact: `residual_unverified_mass · blast_radius · criticality`, with the center's rigor regime setting accrual/discharge.
- **Controller/policy state** — in v1 a *fixed* read-only policy projection (budgets, rigor profiles, model-routing rules); the self-calibrating version is deferred.
- **Provenance views** — how/why/where as semiring projections of the log (v1 ships how-provenance + a why-provenance view; PROV/RO-Crate export in Phase 4).

### 2.4 Centers and rigor regimes
v1 centers are explicit groupings of operations (tag or folder-like), each carrying a **rigor profile** — `exploratory | production | research-grade | safety-critical` — with a project-level default and per-center override. Each profile fixes `accrual_rate`, the verifier set, and `floor` rigor (the irreversible/expensive error classes that can't be declared away).

---

## 3. The build plan — five phases

Each phase has a single goal, a concrete deliverable, hard acceptance criteria, and an explicit "deferred" list. Do not start a phase until the prior phase's acceptance criteria pass.

### Phase 0 — Walking skeleton (the first-validation gate) · *no AI yet*
**Goal:** prove the substrate — create/fork/produce/track/stabilize — with zero intelligence in the loop.
**Build:** the operation log (append-only, content-addressed, hash-chained); thread create + fork (operation-graph DAG); a hand-invoked `Feature` op that writes an artifact to the blob store; provenance recorded; a `Stabilize` op; the artifact and operation-graph projections.
**Acceptance (the spec's first-validation gate):** a user can (1) create a thread → first Feature; (2) fork the thread → fork the graph; (3) produce an artifact; (4) inspect its full provenance (the operation graph); (5) Stabilize it. Replaying the log reproduces identical state (fold determinism).
**Deferred:** all verification, all AI, budgets, centers.

### Phase 1 — The grammar + debt + deterministic verification · *the RQ6 core, still no LLM*
**Goal:** make the central mechanism real and testable without AI confounds.
**Build:** the grammar (a `Feature` auto-creates an open `Test` obligation = visible debt); the verification-debt ledger projection; budget enforcement (when debt would exceed budget: halt or flag for the human — never silently accumulate); fixed rigor profiles per center; the first **verifier = deterministic** (execute the artifact, run supplied tests/diffs); `Stabilize` clears discharged debt; `floor` rigor enforced.
**Acceptance:** a Feature with no Test accrues debt; debt over budget halts/flags; a passing deterministic Test discharges the obligation and lowers debt; Stabilize is blocked while floor-rigor debt is open. Property-based tests confirm fork/merge **commutation** (independent operations merge order-independently) and **conflict-tolerant** merge (conflicts surface, never silently resolve, don't recur).
**Deferred:** LLM operations, conformal confidence, mutation testing.

### Phase 2 — AI operations via MCP · *the generative loop comes alive*
**Goal:** a real human–AI generative environment under the grammar. This is where §4 (prompt engineering) is implemented.
**Build:** the MCP adapter (inference stays external); the `Feature`/implementation operation driven by a generator model that also emits the structured **assumption ledger**; the `Verify`/`Test` operation driven by a **cross-family** verifier (deterministic-first, LLM-judge as last resort); **conformal confidence** calibrated from accumulating operation history per regime; **model routing** (planning/verification → strong reasoner; implementation → capable implementer, cross-family) under the fixed policy; the regime-scaled metacognitive **tracking budget**.
**Acceptance:** end-to-end loop runs from a human intent: plan → generate (with assumptions) → verify (cross-model) → stabilize, with debt tracked throughout. Confidence sets show empirically valid coverage on a held-out set (conformal guarantee holds). A deliberately wrong implementation is caught by the verifier and *not* stabilized (no false discharge on a known-bad case).
**Deferred:** mutation-test calibration, the full inspection UI, PROV export.

### Phase 3 — Measurement · *the actual point of v1*
**Goal:** produce the empirical results that justify the program.
**Build:** the **mutation-testing harness** (inject synthetic faults into generated artifacts; measure kill rate = **measured `discharge_efficiency`**; surviving mutants flag false-discharge-prone verifiers); metrics instrumentation (generative return = validated artifacts / action cost; structural rigor = provenance completeness + debt level + downstream defect rate + re-comprehension proxy; false-discharge rate); the **autobiographical-design study** — build a real artifact *with* SyberRuntime (a SyberLabs deliverable, or a v1.x component of SyberRuntime itself).
**Acceptance:** the kernel reports a measured discharge-efficiency curve per rigor profile; a **pre-registered RQ0 comparison** (operation-primary vs. a snapshot/commit baseline on the §6 metrics) and **RQ6 comparison** (grammar-enforced vs. unbounded generation) yield reportable results, framed honestly as n=1 existence/feasibility, not population effects.
**Deferred:** small-n studies (that's P1 of the *research* roadmap, post-v1).

### Phase 4 — Hardening + the demonstrator
**Goal:** make v1 legible to others — and the "preserve understanding" thesis *visible*.
**Build:** full Merkle history tree (inclusion + consistency proofs); W3C-PROV / RO-Crate provenance export; the **inspection surface** — a minimal UI/CLI that renders the operation graph, the debt ledger, the assumption ledgers, and the provenance for any artifact (the thesis must be *seeable*); event-schema versioning + upcasting + snapshots; the deletion-rights path (sensitive payloads outside the log, referenceable for crypto-shredding); packaging as a runnable portfolio demonstrator with a written walkthrough.
**Acceptance:** a fresh reader can open the demonstrator, pick any stabilized artifact, and trace exactly how it was made, what was assumed, what was verified, and at what confidence — in minutes. The tamper-evidence and consistency proofs verify.

---

## 4. Prompt engineering — the AI-facing design

This is where every research finding becomes an instruction. The kernel's operations are partly model-driven, and the verification grammar is partly model-mediated, so the prompts *are* part of the architecture. Each design choice below is annotated with the finding that forces it.

### 4.0 The runtime constitution (shared system framing)
Every model call carries a compact system frame establishing the operation ontology: that work proceeds as typed operations; that every generative operation incurs a paired evaluation obligation; that nothing is "done" until its obligation is discharged; that assumptions must be surfaced, not hidden; and that the human's understanding is the thing being protected. This keeps model behavior consistent with the operation/grammar model rather than defaulting to chat-style help.

### 4.1 The generator (Feature / implementation operation)
**Design:**
```
SYSTEM: You are performing a Feature operation in SyberRuntime. Produce the artifact AND a
structured ledger of the assumptions and decisions that DRIVE it.

CRITICAL ORDERING: State your assumptions and the decisions you are about to make BEFORE you
produce the artifact. Then produce the artifact consistent with them. Do not write the artifact
first and rationalize afterward.

INTENT: {intent}
CONSTRAINTS / CONTEXT: {inputs, center rigor profile}

OUTPUT (strict JSON):
{
  "assumptions": [ {"claim": "...", "depends_on": "...", "confidence_rationale": "...",
                    "alternatives_considered": "..."} ],
  "plan": "the decision sequence you will follow",
  "artifact": "...",
  "self_identified_risks": [ "where this is most likely wrong, and why" ]
}
```
**Rationale:** assumptions-*before*-artifact is the central faithfulness guard — reconstructing reasoning after the fact is an **ill-posed inverse problem** and chain-of-thought is **systematically unfaithful** (worse on hard problems). Forward-commitment makes the ledger *causal*, not decorative. Structured/parseable output is what enables **process verification**, which the **Data Processing Inequality** shows raises the ceiling on what verification can achieve (a verifier seeing only the artifact is information-bounded by it). `self_identified_risks` seeds the verifier's search. The tracking detail scales with the center's rigor profile (the regime-scaled metacognitive budget).

### 4.2 The verifier (Verify / Test operation)
**Design:**
```
SYSTEM: You are performing a Verify operation. Your job is to FIND THE ERROR, not to approve.
Assume an error exists until you have checked. Do not be agreeable.

STEP 1 — Prefer a deterministic check. If a test, property, type check, metamorphic relation, or
executable check could decide this, specify it precisely so the runtime can RUN it. Only proceed
to judgment if no checkable oracle exists.

STEP 2 — If judging, evaluate the artifact AND its assumption ledger: are the stated assumptions
true, do they actually support the conclusion, and does the artifact follow from them? Locate any
specific failure (quote it).

ARTIFACT + ASSUMPTION LEDGER: {...}

OUTPUT (strict JSON):
{ "checkable_oracle": "test/property to run, or null",
  "verdict": "pass | fail | uncertain",
  "located_errors": [ {"where": "...", "why": "..."} ],
  "obligation_discharged": true|false }
```
**Constraints enforced by the runtime, not the prompt:** the verifier model is a **different family** than the generator (decorrelation — same-model verification is information-bounded and biased by self-preference); it runs in **fresh context** (no exposure to the generator's reasoning beyond the artifact + ledger, to keep errors independent); and an LLM verdict is recorded as **partial discharge** (sampled, re-checkable), never full.
**Rationale:** deterministic-first because **LLM-as-judge is systematically unreliable** (position/verbosity/self-preference bias; >50% error on hard bias benchmarks) — it is the lowest-efficiency verifier and a **false-discharge** risk. Adversarial "find the error" framing counters sycophancy and **widens the generation-verification gap** (the interactive-proof intuition: make errors easier to catch than to produce). Step 1 implements **metamorphic/property/oracle-free testing** for the domains where direct verification collapses.

### 4.3 The planner (decomposing intent into an operation graph) — strong model
**Design:** given an intent and the center's rigor profile, emit a typed operation graph (e.g., `Research → Feature → Test → Refactor → Verify → Stabilize`), with each node's success question and a budget allocation, plus the recommended model tier per node.
**Rationale:** planning is high-stakes reasoning, so it routes to the strongest reasoner (**model routing**; capability is multi-dimensional, so route by *operation type*). The plan *is* the thread structure; making it explicit gives the human a comprehensible map up front.

### 4.4 Confidence — never "how confident are you?"
The runtime does **not** ask models for confidence numbers (**verbalized confidence is systematically overconfident** — nominal 99% intervals cover ~65% — and does not improve with scale). Instead it derives confidence from **conformal calibration** over accumulating operation history per rigor regime: it observes realized outcomes and constructs prediction sets with empirical coverage guarantees. Confidence is a *triage and abstention* signal (where to spend more verification, when to escalate to the human), and its calibration is the same loop that will later calibrate rigor (RQ7).

### 4.5 Routing policy (fixed in v1)
Plan / Verify → strongest reasoner; Implement → capable implementer of a *different family* than the verifier; escalation driven by conformal confidence (not verbalized); cheap implementers permitted only in low-rigor / high-discharge-efficiency centers — never where the rigor profile sets a high floor (the **weak-to-strong oversight limit**: the verifier must not be much weaker than what it checks).

---

## 5. Testing & validation

- **First-validation gate** (Phase 0 acceptance) — the non-negotiable substrate proof.
- **Property-based tests for merge** (`hypothesis`): commutation and conflict-tolerance of the operation-graph merge (the patch-theory guarantees).
- **Mutation testing as discharge measurement** (Phase 3): the kernel's verification layer is itself measured by fault injection — this both calibrates `discharge_efficiency` and dogfoods the rigor tool on itself.
- **Eat your own dogfood:** build the kernel rigorously, and once v1.0 works, build v1.x features *with* SyberRuntime — the compounding that makes solo scope tractable.
- **Pre-registered RQ0 and RQ6 comparisons** (Phase 3): commit the metrics and protocol before running, and report n=1 results as feasibility/existence, not generalization. This honesty is what makes the results credible to a lab.
- **Known-bad cases:** maintain a suite of deliberately-wrong artifacts the verifier must catch (false-discharge regression tests).

---

## 6. Risk register (implementation-specific)

- **Scope creep — still dominant.** *Mitigation:* v1 = kernel; phase gates; walking skeleton first; the "deferred" lists are binding.
- **Over-building substrate before validating the claim.** *Mitigation:* Phases 0–1 reach a testable debt loop with *no AI*; get to RQ6 signal fast.
- **False discharge from bad verifier prompts.** *Mitigation:* deterministic-first; cross-family; LLM verdicts are partial; mutation-test the verifier; known-bad regression suite.
- **AI-integration moving target** (MCP/models evolve monthly). *Mitigation:* the adapter boundary; model-agnostic routing; no model-specific logic in the core.
- **Solo bandwidth.** *Mitigation:* phasing; dogfooding compounds; each phase is independently demonstrable (no big-bang).
- **n=1 unconvincing.** *Mitigation:* pre-registration; honest framing; the *working measured kernel* itself is the artifact, with results as supporting evidence.
- **Event-sourcing operational debt** (projection rebuild cost, schema evolution). *Mitigation:* snapshots + versioned events + upcasting from Phase 4; single-user scale keeps it small.

---

## 7. What "v1 done" means — and the path onward

**v1 is done when** the kernel: passes the first-validation gate; runs the full plan→generate→verify→stabilize loop with real AI via MCP under the grammar; measures discharge efficiency via mutation testing; produces pre-registered RQ0 and RQ6 results from dogfooding; and renders an inspectable provenance/debt/assumption surface where a fresh reader can trace any artifact's making in minutes.

**That artifact is the institutional ask.** It converts "here is a deeply-reasoned spec" into "here is a working substrate and the evidence that process-primary generation + bounded, measured verification preserves understanding at generative scale — fund the rest." The post-v1 sequence is already mapped (the spec's P1–P3 / the research roadmap): small-n studies, the controlled RQ6/RQ0 comparison, then the extended platforms and the endogenous controller.

---

## 8. The first two weeks (concrete starting moves)

1. Stand up the repo, the operation dataclass, and the append-only hash-chained log with content-addressed blobs.
2. Implement `create_thread`, `fork`, a hand-invoked `Feature`, and `Stabilize`; write the fold that materializes artifact + operation-graph state.
3. Write the first property-based test (fork/merge commutation) and the log-replay determinism test.
4. Hit the **first-validation gate** (Phase 0 acceptance). Demo it to yourself end-to-end.
5. Only then: add the grammar + debt ledger + a deterministic verifier (Phase 1).

Resist every urge to add AI, UI, or breadth before the gate passes. The skeleton has to walk before it can think.
