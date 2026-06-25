# SyberRuntime
## A Research Program for Generative Engineering Environments
### Elevated Theoretical Specification — v0.6

**Status:** Research Program / System Specification
**Lineage:** SyberLabs · Consciousness-First Computing (CFC) applied to developer infrastructure
**Supersedes:** v0.5. This revision integrates the Technical Foundations Review (literature consultation across the Runtime's core technical concerns).

**Changes from v0.5:**
- **Corrected** the good-regulator claim: its strong form is contested, so the controller-as-projection is now presented as *motivating* and anchored on the **internal model principle** (Francis & Wonham, 1976) plus second-order cybernetics, not on "necessity." (§2, §3.6)
- **Re-grounded provenance (RQ3)** in the why/how/where hierarchy and **provenance semirings** (Green & Tannen, 2007): the operation graph is *how-provenance*; cheaper views (why / where / lineage) are *homomorphic projections* of it — unifying provenance with the projection ontology. (§2, §3.8, RQ3)
- **Adopted patch-theoretic merge + content-addressed operation identity** (Mimram & Di Giusto, 2013 / Pijul; CRDTs, Shapiro et al.): operations carry stable identity, commute where independent, and treat conflicts as first-class conflict-tolerant states. **Operation identity is the single data-model decision behind sound merge, intrinsic provenance, and future sync.** (§2, §3.1, §3.2, §4)
- **Hardened verification:** named **false discharge** (a biased verifier clearing debt that isn't truly cleared); a preference for deterministic/checkable verification; the generator/verifier split is now **cross-model/family with fresh context** — grounded in LLM-as-judge bias findings and the generation-verification gap. (§3.5, §3.6, RQ4, §8)
- **Grounded the grammar and rigor metabolism in the generation-verification gap:** separation adds information only when verifier errors *decorrelate*; `discharge_efficiency` *is* the exploitable gap (large with machine-checkable ground truth, collapsing without). (§2, §3.1, §3.5, RQ6)
- **Repositioned:** durable stateful threads are now commodity (LangGraph 1.0; Temporal + OpenAI Codex). The contribution is relocated to the **accounting + closure + rigor + re-comprehension-provenance** layer above the standard durable-thread substrate. (§0, §2, RQ2, §8)
- **Added** event-sourcing mitigations and a **deletion-rights** risk; positioned "verification debt" against the existing SE term "test debt." (§4, §8, §3.5)

---

## 0. The one-sentence thesis

> **As generation cost collapses, the scarce resource is no longer implementation but *understanding*. SyberRuntime is a local-first coordination and provenance substrate whose central function is to keep human comprehension load-bearing while generative freedom increases.**

Its **foundational move is ontological.** Software inherited from paper a metaphysics of the *file as completed object* — but creation is a *process*. The file preserves the corpse; the living thing is the trajectory of intent → attempt → failure → branch → test → revision → insight → compression. So SyberRuntime treats the **operation** as the primitive, **process** as primary, and **files as projections** — and it holds the freedom/rigor tension with one rule, **no unverified generation**, accounted for as bounded **verification debt**.

**What is and isn't the contribution.** As of 2026, durable stateful threads, fork/rewind, and human-in-the-loop are *commodity* — they ship in production agent frameworks (§2). SyberRuntime's contribution is **not** the durable-thread substrate. It is the **accounting layer** above it: the operation-with-evaluation primitive, the verification-debt *grammar*, organizational closure, the rigor metabolism, and provenance engineered for human *re-comprehension* rather than crash recovery. The thesis question — "easier to create without harder to understand" — is a *design commitment* about that layer.

### 0.1 SyberRuntime is CFC instantiated as infrastructure

The CFC criterion — *preserve the person's ability to perform conscious synthesis upon themselves and their world* — is not bolted on; it **is** the runtime's specification. Synthesis requires that the *process* remain inspectable, not merely the finished artifact, because the artifact alone discards the cognition, alternatives, and uncertainty that judgment needs.

It also fixes the system's teleology. SyberRuntime **regulates itself** from inside its own operation economy (organizational closure, §3.6), yet its **goal stays exogenous** — supplied by the human, not by the system's drive to persist. Closure of regulation, openness of intent: that is CFC as architecture.

---

## 1. Problem: three tensions, grounded

**1.1 Collapse of intention into creation.** When action cost approaches zero, users specify rather than construct, and the gap between *wanting* and *having* no longer forces the cognitive work that produced understanding as a side effect. (Interaction cost; cognitive load theory; Papert's constructionism — understanding is built *through* construction, which specification short-circuits.)

**1.2 Explosion of complexity; evaluation as the new bottleneck.** Generated artifacts scale faster than the human's capacity to evaluate them. The bottleneck migrates from *can I build it* to *can I trust what was built*. This is the keystone tension and the basis for **verification debt** (§3.5, RQ6).

**1.3 Fragmentation of cognition across tools.** Context spreads across IDE, chat, browser, repo, diagrams, notes, docs, with no shared runtime governing their interaction — a *distributed cognition* problem (Hutchins): when the coordinating substrate is absent, the cognitive system degrades.

The deeper diagnosis: **today's tools flatten process into snapshots.** A `.py` file looks static; the development that produced it was not. Git preserves commits, diffs, and snapshots — not active cognition, alternatives, rejected paths, uncertainty, or emergence. The most important thing in software is currently mostly invisible.

---

## 2. Position: where this sits in existing work

SyberRuntime is novel as a *synthesis and a stance*. Naming the neighbors precisely forces the reviewer's question: *why doesn't an existing framework already do this?*

**Process, operation & identity lineage (the foundation — proven engineering lifted up a layer).**
- **Event sourcing / CQRS** — current state is a *projection* (a materialized view) of an append-only event log; `artifact = projection(operation_graph)` is formally a fold/catamorphism over the log. This *is* `file = projection(process)` in production systems.
- **Datomic** (Hickey) — the database as immutable facts over time; "the present" is a view.
- **Patch theory** — Darcs treats *patches (operations)* as primary but suffered exponential-time merge in conflict cases; **Pijul** fixed this on Mimram & Di Giusto's *categorical theory of patches* (2013), where version control is **pushouts** and the **free cocompletion** of a category adds the missing ones. The operative properties — patch **commutation**, per-element **identity**, and **conflict-tolerant state** (conflicts are never silently wrong and, once resolved, don't recur) — are SyberRuntime's merge design (§3.2).
- **CRDTs & local-first** (Shapiro et al. 2011; Kleppmann et al., *Local-first software*, 2019; Automerge) — multi-user-from-the-ground-up data structures that merge concurrent edits by assigning **stable identity to each element/operation**. The same identity principle as Pijul; the basis for the extended program's multi-user sync.
- **Hazel** — typed structure editing with first-class edit *actions*. **Process philosophy** — Whitehead's "actual occasions," becoming over being.

**Systems science & cybernetics (the foundation for closure — claimed carefully).** A system that regulates its own generation, verification, and regulation costs from inside the same operation economy is **organizationally closed** — operationally closed yet structurally open (Maturana & Varela). The firm anchor for the controller-as-model is control theory's **internal model principle** (Francis & Wonham, 1976), reinforced by **second-order cybernetics** (von Foerster), in which the controller is part of the system it describes, dissolving the regulate-the-regulator regress without an infinite tower. *Honest caveat:* the often-cited **good-regulator theorem** (Conant & Ashby, 1970) is **contested** — its formal proof is widely held not to fully establish its title claim, its mapping is a lossy homomorphism, and many effective model-free regulators exist; so it is used here as *motivating intuition only*. Ashby's **requisite variety** and Beer's **Viable System Model** ground the bounded-recursive-regulation design. *Fence:* applying autopoiesis to software is a generalized analogy (Luhmann's extension is contested; Varela was cautious), so the claim is organizational closure in a *generalized cybernetic* sense, not literal autopoiesis.

**Agentic orchestration — the substrate has become commodity.** LangGraph (v1.0, Oct 2025) provides **durable execution** (agents persist through failure and resume from where they left off), organized around **threads** and state, with **human-in-the-loop** and **time-travel rewind**; LangChain's 2026 report finds >70% of production agents use a graph structure and >60% of incidents trace to state management. **Temporal** (durable execution) raised $300M at a $5B valuation and runs in production for **OpenAI's Codex**, with a March 2026 OpenAI Agents SDK integration. A sharp critique applies across frameworks: checkpointing only saves state and leaves failure detection, automatic resumption, and duplicate-execution prevention to the developer — *"checkpoints are not durable execution."* **Consequence for SyberRuntime:** the durable-thread substrate is no longer a differentiator (see §0); what these systems lack is the *accounting layer* — a LangGraph checkpoint is **recovery state, not interpretability provenance**. AutoGen / CrewAI (role-based — relevant to RQ4) round out the landscape.

**Verification, self-critique & technical debt (the theory under the grammar).**
- **Generation-verification gap** — the grammar assumes evaluation adds information beyond generation. Kambhampati et al. show LLMs are unreliable self-verifiers and that the classical "verification is easier than generation" argument may be irrelevant when the model is doing approximate retrieval. The mechanism is **correlated errors**: shared failure modes mean self-critique amplifies confidence without information. The prescribed fix — *separate generation from evaluation using fresh context, restoring the external feedback loop* — is **exactly** SyberRuntime's grammar (§3.1). The gap is **domain-bounded**: exploitable where machine-checkable ground truth exists (code+tests, formal tasks, proofs), collapsing where there is no formal correctness.
- **LLM-as-judge bias** — judges exhibit position, verbosity, self-preference, and family biases; a 2026 RAND study found no judge uniformly reliable across benchmarks, with frontier models exceeding 50% error on challenging bias benchmarks. This motivates *false discharge* (§3.5) and the cross-model verifier (RQ4).
- **Technical debt / SATD** (Cunningham; Maldonado & Shihab; Green-Tannen-adjacent quantification) — mature, with quantification by **density, diffusion, and interest**. Note: "**test debt**" already exists as an SATD category meaning shortcuts *in test code* — distinct from SyberRuntime's **verification debt** (the unverified-ness of artifacts as a budgeted quantity). A 2026 study finds debt dynamics differ sharply by paradigm (ML vs. LLM-infra vs. traditional) and that universal strategies fail — independent corroboration of the rigor metabolism.

**Provenance standards & theory (the rigorous frame for RQ3).** W3C PROV (entity / activity / agent → **artifact / operation / [human|AI]**), Research Objects / RO-Crate, and supply-chain provenance (SLSA, in-toto). Crucially, **database provenance theory** — the why / how / where hierarchy (Cheney, Chiticariu & Tan, 2009) and **provenance semirings** (Green & Tannen, 2007), in which different provenance models are different semirings connected by **homomorphisms**, with **how-provenance the most general** — gives RQ3 a principled lattice (§3.8).

**HCI of notation; the mathematics of the dual rule; Alexander & augmentation.** Cognitive Dimensions of Notations (Green & Petre, ~1996) and mixed-initiative interaction (Horvitz, 1999) for RQ1/RQ4; **adjoint functors** (`free ⊣ forgetful` ≈ `expand ⊣ compress`, and the free cocompletion above is itself a universal construction), lenses, and Noether for the dual rule, consistent with **Forma Fluens**; Alexander's centers/wholeness and the augmentation lineage (Engelbart 1962; Licklider 1960).

**Net position.** SyberRuntime is the *accounting and provenance substrate* sitting above a now-commodity durable-thread layer, whose differentiator is one defensible stance: **process, provenance, and bounded verification are properties of the medium, and the medium regulates itself from inside while leaving intent to the human.** The bet is that this matters more as AI does more of the work.

---

## 3. Conceptual architecture — the models, formalized

### 3.1 Operation (the atomic primitive)

The fundamental unit is not the file (state) but the **operation** (transformation):

```
Operation {
    id            // STABLE, content-addressed identity (the keystone data-model decision)
    type          // the verb (open, versioned set)
    inputs        // artifacts / knowledge in scope (referenced by id)
    outputs       // candidate artifacts produced (each element id-stamped)
    constraints   // budget, depth, allowed adapters
    evaluation    // the operation's own success question
    provenance    // who/what/when, retrievals, decisions
}
```

**Operation identity is the single most consequential data-model decision** (the open question from prior versions, now answered). Stable, content-addressed identity on operations and the artifact-elements they touch is the shared prerequisite for three things at once: **sound thread merge** (patch theory / CRDTs, §3.2), **intrinsic provenance** (any element traces to its originating operation, §3.8), and **future multi-user sync** (CRDTs, extended program). One decision, three payoffs.

**(a) Every operation declares its own evaluation** — Feature: *did useful possibility increase?* Test: *did uncertainty decrease?* An operation whose evaluation is **undischarged is debt.**

**(b) The verb set is an open, versioned hypothesis — not a closed ontology.**

| Verb | Does | Success question |
|---|---|---|
| **Feature** | creates new capability | did useful possibility increase? |
| **Test** | reduces uncertainty | did uncertainty decrease? |
| **Refactor** | transforms structure, preserves behavior | is structure better, behavior unchanged? |
| **Research** | reduces design uncertainty | is the design space better understood? |
| **Verify** | increases trust | is trust justified? |
| **Compress** | reduces complexity | is complexity lower, meaning preserved? |
| **Simulate** | evaluates future states | what would happen? |
| **Stabilize** | converts process → artifact | is this ready to commit? |

**The generative grammar (the one rule):** **no unverified generation.** Every *generative* operation **automatically incurs a paired evaluative obligation** (Feature → undischarged Test; Generate → undischarged Verify; Research ↔ Critique), surfacing immediately as **verification debt** (§3.5); **discharging it is scheduled under budget.** Double-entry bookkeeping for development.

**Why the grammar works — and when it doesn't (grounded in the generation-verification gap).** Separating generation from evaluation adds information **only when the verifier's errors decorrelate from the generator's**; this is precisely the information-theoretic fix the literature prescribes (separate generation from evaluation, fresh context, external feedback). A same-model, same-context "Test" is near-worthless — correlated errors amplify confidence without information. This has teeth in §3.5 (verifier types) and RQ4 (cross-model split).

**Note on reversibility.** The grammar pairs *generate↔evaluate*, not *undo*. Universal reversibility is rejected as paralysis by optionality: **Stabilize is deliberately low-reversibility** — a committing, debt-clearing act. Creation requires the courage to foreclose.

### 3.2 Thread (operation graph) — and patch-theoretic merge

A **thread** is a *structured, durable graph of operations* — durable, forkable, budgeted, terminable, no longer opaque:

```
Research → Feature → Test → Refactor → Verify → Stabilize
```

**Forking and merging threads = merging operation graphs**, and the merge follows patch-theoretic principles (Mimram–Di Giusto / Pijul, §2): operations are designed to **commute** where independent (forked threads merge order-independently to the same result), and **conflicts are first-class conflict-tolerant states** — surfaced explicitly, never silently wrong, and once resolved they don't recur — rather than merge failures. The categorical framing (merge as pushout; conflicts as the absence of one, repaired by free cocompletion) ties to the `free ⊣ forgetful` adjoint language in §2. A thread's provenance log *is its operation graph* — typed, hence far more interpretable than a raw event stream (RQ2). This is also the boundary where the single-user kernel needs only operation identity + patch-style merge; full CRDTs arrive with multi-user (extended).

### 3.3 Artifact (materialized projection)

`artifact = projection(operation_graph)` — formally a **fold (catamorphism)** over the operation log. An **artifact** is a *materialized projection* of the graph's current state — a temporary crystallization, not the primary object. Files are **one projection mode among several**: artifact snapshots · thread logs · decision histories · graph evolution · research packets · center topology · verification lineage. And, per §3.8, **provenance views are themselves projections of the same log** — the projection ontology runs all the way down.

### 3.4 Center (organizing principle) — preserved, and fenced

Threads and operation graphs cluster into **centers** — coherent sub-wholes — which nest recursively. Two claims kept apart: the **testable** claim (recursive center structure improves navigability and re-comprehensibility versus flat structure — §6) and the **design-philosophy** claim ("aliveness"/wholeness, retained as a heuristic, not a promised empirical result).

Centers are also the scope of the **rigor regime** (§3.5), with a project-level default — so a low-rigor project can still carry high-rigor centers (a checkout flow, an auth boundary, anything touching money or PII). **Rigor is a property of the center, not the repository.**

### 3.5 Budget + Verification Debt — the rigor metabolism, and false discharge

**Verification debt** is the accumulated gap between *generated* and *validated* artifacts, kept visible and bounded rather than invisible. It is **distinct from the existing SE term "test debt"** (shortcuts *in* test code); the quantification borrows the technical-debt vocabulary (density ≈ `unverified_mass`, diffusion ≈ `blast_radius`, interest ≈ deferred-verification cost). The stock:

```
verification_debt(graph) = Σ over artifacts a:
        residual_unverified_mass(a) · blast_radius(a) · criticality(a)
```

The **coupling** between generation and debt is **not flat** — it is the project's **rigor metabolism**, the domain- and stakes-dependent exchange rate between generative freedom and verification work, decomposed into two functions:

```
Δdebt⁺(a) = generative_mass(a) · accrual_rate(r)                      # accrual
Δdebt⁻(a) = verification_effort · discharge_efficiency(r, verifier),  # discharge
            bounded below by floor(r)
where  r = rigor_regime(center(a))
```

**`discharge_efficiency` is grounded in the generation-verification gap** (§2): it is the size of the *exploitable* gap in a domain — large where ground truth is machine-checkable, collapsing where there is no formal correctness.

| | HTML / UI | ML research |
|---|---|---|
| accrual (gen → debt) | low | high |
| discharge efficiency (≈ exploitable GV-gap) | high | low |
| irreducible floor | ~zero | high |
| error latency | instant | deferred |
| blast radius | local | systemic |

**Verifiers are typed by efficiency and bias, not interchangeable.** Deterministic, checkable verification (execution, tests, types, property-based, formal methods) is **preferred**; an **LLM-as-judge is a low-and-biased-efficiency verifier of last resort** (position/verbosity/self-preference/family bias; unreliable under stress — §2).

> **False discharge — a first-class failure.** A biased or correlated verifier can mark an obligation satisfied when it is not, creating *invisible* unverified state behind a green check. This is **worse than no verification**, because it is the exact failure the system exists to prevent, now originating inside the verifier. Mitigations: prefer deterministic verification; require decorrelation (cross-model/family, fresh context); treat an LLM-judge discharge as *partial* (sampled, re-checkable), never full.

Regimes ship as named **profiles** — *exploratory · production · research-grade · safety-critical* — generalizing risk-based testing (`-O0..-O3`, branch-tiered CI gates), with per-center overrides. **Budgets** cap depth, branching, compute, and allowable debt; when debt would exceed budget the runtime must spend on verification, escalate to the human, or halt — never silently accumulate.

*Extension (beyond the kernel):* debt is likely **typed** — correctness vs. validity vs. reproducibility vs. safety — and different verifiers discharge different types; HTML is almost all correctness debt, ML dominated by validity/reproducibility debt (why a green unit test there clears almost nothing).

### 3.6 Closure and Meta-Control

SyberRuntime is **organizationally closed** when its operation graph produces not only artifacts but the **policies** governing future operation selection, budget allocation, verification depth, and stabilization thresholds. The regulator is not an external judge; it is a **policy projection** over operation history:

```
Artifact   = projection(operation_graph)
Policy     = projection(operation_graph)
Controller = projection(operation_graph + budgets + debt_history)
```

This is closure in the systems-science sense — operationally closed, structurally open. The controller-as-projection is *motivated* by control theory's **internal model principle** (a regulator benefits from embodying a model of what it regulates) and by **second-order cybernetics** (the controller is part of the system it describes). It does **not** rest on the strong good-regulator claim, which is contested (§2); the architecture needs only the weak, safe reading.

**The accounting boundary closes regulation, not purpose.** Teleologically, SyberRuntime is **allopoietic**: its product is the human's artifacts and preserved capacity for synthesis (CFC), not its own persistence. So **intent** is deliberately *exogenous* — supplied by the human, with whom the runtime is **structurally coupled** (the human's perturbations trigger changes the runtime's own organization determines; they do not instruct it). A *fully* closed system would be autotelic.

**Two laws govern the closed loop.**
1. **Closure.** *No cost-regulator is outside the accounting boundary.* Generation, verification, coordination, and meta-control are all operations subject to the same debt accounting.
2. **Requisite variety (Ashby).** *Regulatory variety must match generative variety within budget, or control degrades.* Permitted freedom and required verification capacity are set together.

**The controller is an allocator.** `Total cost = generation + verification + coordination + meta-control` is its decision variable; it allocates a bounded total to **maximize validated generative return** (§6). The three pathologies are the three mis-allocations: over-generation → **chaos** (a requisite-variety failure), over-verification → **bureaucracy**, over-meta-control → **paralysis**.

**The rigor regime is a policy — fixed, then calibrated.** In the kernel it is a hand-set profile per center; under closure it is **calibrated from consequences** (the controller compares actual downstream defect rate against the declared regime and corrects `accrual_rate`). Guardrail against gaming: **floor rigor** for irreversible/expensive error classes regardless of declared profile, and calibration overrides a mis-declared regime.

**Anti-regress condition.** Meta-control is bounded by budget and cannot recursively demand unlimited verification of itself; closure makes the stopping *principled* (meta-control is the same kind of thing as object-control), so there is no infinite tower.

**The closing law:**
> *No regulator is outside the accounting boundary — except intent, which is the reference the boundary serves.*

### 3.7 Adapter (externalized inference)

Inference, IDEs, repos, browsers, and diagram tools remain **external**; the runtime integrates rather than owns them — keeping it model-agnostic and auditable, and the provenance boundary clean (every external call is a logged adapter operation). **Files are one projection-export adapter.** MCP is the natural first adapter.

### 3.8 Research Provenance — PROV-aligned and semiring-graded

Research is the operation sequence **Question → Retrieval → Claims → Contradictions → Synthesis → Artifact** — a graph of Research/Test/Verify operations producing claims. Two complementary groundings: alignment with **W3C PROV** (interoperable export as an RO-Crate-style research object), and the **provenance-semiring** frame (§2). The Runtime's typed operation graph **is how-provenance** — the most general point on the semiring hierarchy — and cheaper provenance views (why / where / lineage) are **homomorphic projections** of it. This unifies provenance with the Runtime's projection ontology (§3.3) and turns RQ3's "granularity is the crux" into a principled lattice with a known top.

---

## 4. System architecture, with the build line drawn

The primitive stack is operation-primary, **platforms are operation venues**, the **controller is a projection** of the log, and **operation identity is the data-model spine**.

```
Operation   atomic: { id (content-addressed), type, inputs, outputs, constraints, evaluation, provenance }
   │        verbs (open, versioned): Feature · Test · Refactor · Research · Verify · Compress · Simulate · Stabilize
   │        grammar: generative op ⇒ paired evaluation obligation (= debt at the center's accrual rate), discharged under budget
Thread      = a structured graph of operations; fork/merge via patch-theoretic (commuting, conflict-tolerant) semantics
   │
Artifact    = a fold/projection of the operation graph
   │
Center      = recursive structure over operation graphs; scope of the rigor regime
   │
Platforms   = venues typed by operation kind:
   │           Code Forge → Feature / Refactor / Compress / Stabilize
   │           Tribunal   → Test / Verify   (deterministic first; LLM-judge last-resort, cross-model)
   │           Lab        → Research
   │           Simulator  → Simulate
   │           Archive    → operation log + projections (artifacts, policies, controller, provenance views)
   │           Diagrammer / Studio → projection & authoring surfaces
   │
Controller  = policy projection over operation log + budgets + debt history (§3.6); intent enters from outside
   │
Adapters    files are ONE projection-export adapter (MCP · VS Code · Browser AI · GitHub · CLI)
```

**── KERNEL (solo-buildable; this is the real project) ──**
- **Runtime:** local-first, **event-sourced** core — operation log primary; threads fork/merge/terminate via patch-style merge; **content-addressed operation/element identity** is the spine. Event-sourcing discipline: **versioned events + upcasting + snapshots + autonomous per-projection rebuild + content-addressed blobs** (keep events lean — store payloads by hash, reference in events).
- **Provenance store** (= minimal **Archive**): append-only operation log = how-provenance; cheaper views materialized as projections; W3C-PROV-compatible export.
- **Budget + verification-debt engine with the grammar, fixed policy + rigor profiles** (= slice of **Tribunal** + minimal controller): Feature auto-creates an undischarged Test obligation at the center's accrual rate; discharge required once debt nears budget. Controller **reads** history and enforces hand-set policy — it does **not** self-modify or calibrate (RQ7, extended).
- **Verification mechanism:** deterministic-first (execution, tests, diffs); LLM-judge only where unautomatable, and **a different model/family** than the generator (decorrelation). LLM-judge discharge is partial/sampled.
- **One adapter:** **MCP**. **Minimal Code Forge:** execute and diff artifact projections.
- *Feasibility note:* the **single-user local-first** kernel sidesteps the hardest event-sourcing problems — eventual consistency, event collisions, distributed ordering — which are multi-user concerns.

**── EXTENDED PROGRAM (needs collaborators / institutional support) ──**
Full Diagrammer/Simulator/Studio and richer Lab; VS Code / Browser / GitHub / CLI adapters; **CRDT-based multi-user concurrency**; the RQ1 environment-theory study; richer verification (formal methods); centers-operationalization; **typed verification debt**; **endogenous meta-control + rigor calibration** (closure, RQ7). For multi-user durable execution, **Temporal is a candidate substrate** rather than reinventing distributed durability.

> **The build line.** The kernel tests RQ0, RQ2, RQ3, RQ6 and is buildable by one person. Operation identity answers the data-model question; the durable-thread substrate is commodity (adopt patterns, don't reinvent); the *self-generating* controller and multi-user sync are deferred. Build the kernel; let its results earn the rest.

---

## 5. Research Questions (operationalized)

### RQ0 — Operation as primitive & process ontology *(foundational; solo-tractable)*
- **Hypothesis (H0):** an operation-primary model outperforms a file/snapshot model on the §6 metrics — especially generative return and structural rigor — at acceptable cost; the typed operation graph yields higher re-comprehensibility than a commit log.
- **Method/measures:** kernel + autobiographical/small-n comparison; generative return, rigor composite, re-comprehension time, capture/replay cost.
- **Feasibility:** **solo (kernel)** — the empirical core and P0 headline.

### RQ1 — Environment & Cognitive Disposition *(most ambitious; team-scale)*
- **Hypothesis (H1):** environments differ systematically along Cognitive Dimensions; lowering *viscosity*/*hidden dependencies* and raising *role-expressiveness* shifts users toward exploratory-yet-rigorous dispositions vs. a raw IDE+chat baseline. Treat disposition as hypothesis, never premise.

### RQ2 — Operation/Provenance Layer atop a Commodity Thread Substrate *(reframed; core bet; solo-tractable)*
- **Motivation:** durable stateful threads are now commodity (§2). The real question is whether the **operation-with-evaluation + intrinsic-provenance + accounting** layer delivers concurrent creative work *with* preserved understanding that the bare substrate does not.
- **Hypothesis (H2):** a single creator sustains N>1 concurrent threads (operation graphs) with higher generative return and no loss of rigor versus serial work, *and* re-comprehends a runtime-built system faster than the same system built on a checkpoint-only substrate (recovery-state, not provenance). Collapse is predictable from budget/debt signals.
- **Feasibility:** **solo (kernel).**

### RQ3 — Minimally Sufficient Provenance via the Semiring Hierarchy *(sharpened; solo-tractable)*
- **Construct:** the operation graph = **how-provenance** (the semiring top, Green & Tannen); cheaper views (why / where / lineage) are **homomorphic projections** of it. The open variable is *which projection* is trust-sufficient.
- **Hypothesis (H3):** trust/interpretability rises sharply as provenance reaches a why-/how-provenance grain and saturates beyond it, while interpretability *cost* rises faster than storage — so a non-trivial point on the hierarchy (≈ the operation/derivation) is "minimally sufficient."
- **Feasibility:** **solo (kernel).** Granularity is the crux; the hierarchy makes it principled.

### RQ4 — Cross-Model Role Specialization in Human–AI Coordination *(sharpened; partly solo)*
- **Hypothesis (H4):** separating *generator* from *verifier* yields the largest gain — **but only when the split decorrelates errors** (different model/family, fresh context); a same-model verifier over-approves via self-preference and correlated errors, approaching no gain. Other role splits give diminishing returns.
- **Method/measures:** ablation across role configurations *and* across same-model vs. cross-model verifiers; verification debt incurred, **false-discharge rate**, defect rate, intervention frequency.
- **Feasibility:** **partly solo** (cross-model generator/verifier split is in the kernel). The verifier is RQ6's actuator.

### RQ5 — Executable Context / Structure-as-Architecture *(partly solo)*
- **Hypothesis (H5):** treating centers as executable coordinators over operation graphs improves navigability/re-comprehension (the §3.4 testable claim) versus inert structure, at tractable cost.

### RQ6 — Verification Debt as Generative Grammar, with a Domain-Dependent Coupling *(keystone; solo-tractable)*
- **Construct:** debt per §3.5; the generation↔debt coupling is the center's **rigor regime**, with `discharge_efficiency` grounded in the **generation-verification gap**.
- **Hypothesis (H6):** enforcing the grammar lowers downstream defect/regression rates and raises re-comprehensibility vs. unbounded generation, *without* proportional throughput loss — **and** the correct coupling is regime-determined (matched profile beats flat; mismatched profile fails predictably: too-low → defect surge, too-high → throughput collapse). **False discharge is bounded** by deterministic-first verification and cross-model decorrelation.
- **Feasibility:** **solo (kernel).** The most fundable single result, backed by a mechanism (the grammar) and a domain-aware, theory-grounded coupling.

### RQ7 — Organizational Closure, Meta-Control Stability & Rigor Calibration *(novel; partly solo)*
- **Hypothesis (H7):** a bounded endogenous controller converges to a stable allocation beating a fixed policy across heterogeneous tasks without pathological regimes, **and** calibrating the rigor coefficient from observed defects beats any fixed profile. Ablations confirm necessity: drop the budget ceiling → paralysis; drop requisite-variety matching → chaos; drop calibration → mis-declared regimes go uncorrected.
- **Feasibility:** **partly solo** (simulation/autobiographical); full closure is extended. *Caution: endogenous self-modifying meta-control is the riskiest component; establish the fixed-policy baseline first.* "*The system learned its own rigor regime from observed defect rates*" is the headline-fundable claim.

---

## 6. Evaluation methodology

**Metric operationalizations:** *action cost* (effort per unit realized intent), *degrees of freedom* (breadth of explored operation space), *generative return* (**validated** artifacts per unit action cost), *structural rigor* (provenance completeness + verification-debt level + downstream defect/regression rate + re-comprehensibility, with **false-discharge rate** as a debt-integrity check).

**Four-tier spectrum:** (1) **autobiographical design (n=1)** — dogfood the kernel; existence/feasibility claims only; (2) **small-n think-aloud (5–8)** — Cognitive Dimensions questionnaire + operation-graph/debt traces; (3) **controlled comparison** — RQ0/RQ6/RQ2 including matched-vs-flat **rigor profiles**, **same-model vs. cross-model verifiers** (false-discharge), and runtime-vs-checkpoint-only re-comprehension; also closure stability + calibration (RQ7) with per-law ablation; (4) **longitudinal field deployment** — does the grammar + a closed, calibrating controller prevent complexity collapse over time?

**First validation** (kernel gate), mapped onto operations: create thread → first **Feature**; fork → fork the operation graph (patch-style); produce artifact → **Feature** output materialized; track provenance → **the operation graph** (how-provenance); stabilize → a **Stabilize** op that clears debt.

---

## 7. Roadmap and institutional readiness

| Phase | Build | Study tier | Output | Venue / ask |
|---|---|---|---|---|
| **P0 — Kernel** | Event-sourced operation runtime (content-addressed identity, patch-style merge) + Archive (how-provenance) + debt engine *with grammar, fixed policy + rigor profiles* + MCP + deterministic-first/cross-model Tribunal-lite | First-validation gate, then Tier 1 | Working kernel + **RQ0/RQ6** result | Tech report / blog; portfolio |
| **P1 — Formative** | Minimal centers (RQ5), cross-model generator/verifier split (RQ4) | Tier 2 | RQ2/RQ3/RQ6 incl. matched-vs-flat profiles + false-discharge | Workshop paper (CHI/UIST/PL-HCI) |
| **P2 — Confirmatory** | Hardening; second verification mechanism; fixed-vs-endogenous policy + rigor calibration (RQ7) | Tier 3 | Central result (freedom *and* rigor) + closure + calibration | Full paper; **first grant / lab-collab ask** |
| **P3 — Extended** | Diagrammer/Simulator/Studio, more adapters, **CRDT multi-user (or on Temporal)**, RQ1 study, full endogenous + self-calibrating controller, typed debt | Tier 4 | The full program | Funded lab program / partnership |

**Credible to** HCI, PL/SE, and AI-oversight labs. **The oversight angle is direct:** preserving human understanding as AI does more of the work *is* the §0 thesis at the developer-infrastructure layer; closure-with-an-intent-aperture and a consequence-calibrated rigor coefficient are a concrete account of how a self-regulating system stays answerable to a human's ends. Provenance-for-re-comprehension (not recovery) is the throughline that makes the program fundable beyond tooling.

---

## 8. Risk register (honest)

- **Scope vs. solo feasibility — dominant.** *Mitigation:* the §4 kernel/extended line; operation identity clarifies the kernel; self-generating controller and multi-user sync deferred.
- **Differentiation collapse — now partly realized.** LangGraph 1.0 / Temporal have caught up on the *substrate* (durable threads, rewind, HITL). *Mitigation:* relocate the contribution to the accounting + closure + rigor + re-comprehension-provenance layer (§0, §2); defend at the substrate-of-meaning level, not the durable-execution level.
- **False discharge from biased/correlated verification.** A biased verifier clears debt that isn't cleared — invisible unverified state behind a green check, worse than no check. *Mitigation:* deterministic-first verification; cross-model/family + fresh-context split (RQ4); LLM-judge discharge treated as partial/sampled.
- **Good-regulator over-reliance.** *Mitigation (applied):* the strong claim is dropped; anchored on the internal model principle + second-order cybernetics; closure needs only the weak reading.
- **Autotelic drift (teleological closure).** *Mitigation:* the intent aperture (§3.6) — closure is regulatory only; intent stays exogenous and legible.
- **Endogenous meta-control instability.** Premature self-modifying policy is the pathology generator. *Mitigation:* fixed-policy kernel; staged RQ7; ablation-guarded by both laws.
- **Calibration lag in latent-error domains.** Defects surface late in ML/distributed systems, starving the calibrator where rigor matters most; absence of surfaced defects ≠ safety. *Mitigation:* **start high, relax on evidence** for high-latency profiles; floor rigor backstop; slow calibration loop.
- **Operations-primary is proven but subtle.** Event-schema evolution, projection-rebuild cost (grows non-linearly), idempotency-on-resume, naive-patch-theory merge blowups (the Darcs lesson). *Mitigation:* the named ES tactics (§4); patch-theoretic merge (§3.2); content-addressed identity.
- **Deletion rights vs. append-only log.** A provenance-everything local-first tool collides with right-to-be-forgotten. *Mitigation:* store sensitive payloads outside the log (reference by hash) + crypto-shredding.
- **Granularity is the whole game (RQ3).** *Mitigation:* the why/how/where + semiring lattice makes grain principled; verb taxonomy stays a versioned hypothesis.
- **The economics of verification.** Formal verification is expensive; LLM-judge cheap but unreliable; the grammar is only as good as the verification it can afford. *Mitigation:* RQ6 measures the throughput cost of the grammar across regimes.
- **Requisite-variety failure; "aliveness" as unmeasurable; autopoiesis as overclaim; building on shifting ground.** *Mitigations as in prior versions:* couple freedom to verification capacity; §3.4 two-claim split; "generalized cybernetic closure" not literal autopoiesis; externalized adapters + model-agnostic event-sourced core.

---

## 9. Long-term vision

Software may become less like writing instructions and more like cultivating responsive environments — and, beneath that, less like editing objects and more like *steering processes that crystallize into objects.* The central challenge is not generation but the preservation of understanding. SyberRuntime is one wager on the substrate for that future, on a single ontological commitment, a single disciplining rule, and a single closure: **process is primary; files are projections; nothing generative goes unverified — at a rigor the domain actually demands, by a verifier whose errors are decorrelated from the generator's; and the system regulates itself from inside, leaving only intent outside the boundary, because intent is what the boundary serves.**

It is **Consciousness-First Computing made operational** — an architecture whose entire purpose is to keep the human capable of conscious synthesis upon a world that machines are increasingly able to generate faster than we can comprehend.

Build the kernel. Give every operation an identity. Make the operation the primitive. Enforce the grammar. Let the rigor match the stakes. Close the loop on everything but intent. Let the evidence earn the program.
