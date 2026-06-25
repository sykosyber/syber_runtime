# SyberRuntime — Verification & Testing Playbook
## Maximizing testing and verification capability — literature consultation, evaluation of two proposals, and a structured playbook
### For a v0.7 decision — analysis, not yet merged

**Purpose.** You proposed two verification levers — (1) a metacognitive budget that spends ~20% of inference on tracking assumptions/reasoning with confidence intervals so the verifier has more to work with, and (2) a heuristic that routes planning and verification to the strongest models and implementation to standard ones to cut silent errors. This memo evaluates both against the literature (Part A), gives the organizing frame (Part B), lays out the full playbook (Part C), and specifies the v0.7 integration (Part D). Held as analysis so the merge stays your call.

**One-line verdict.** Both ideas are *correct in direction and well-grounded* — and both need one or two refinements the literature makes non-negotiable. Idea 1's core (verify the reasoning, not just the outcome) is empirically the more reliable approach; its two halves need guarding (reasoning can be unfaithful; verbalized confidence is overconfident — use conformal prediction instead). Idea 2 is sound routing practice; it needs to become *cross-family, task-type* routing, and its silent-error claim is conditional on the verifier's catch rate.

---

## Part A — The two proposals, evaluated

### Idea 1: metacognitive budget (assumption/reasoning tracking + confidence intervals)

**The core is strongly validated.** Externalizing reasoning so the verifier can check *steps* rather than only the *final answer* is exactly **process supervision**, which Lightman et al. (2023, "Let's Verify Step by Step") found *significantly outperforms* outcome supervision on hard problems — precisely because it pinpoints where an error occurs and is more interpretable. And it targets your stated goal directly: under outcome supervision, models "regularly use incorrect reasoning to reach the correct final answer" — that right-answer/wrong-reasoning case *is* the silent error, and only process-level verification catches it. The ~20% framing is also sound: it is an allocation of **test-time compute** to metacognition, and it should be *regime-dependent* (high-rigor centers warrant a larger fraction), which slots straight into the rigor metabolism.

**Refinement 1 — treat the reasoning record as checkable *structure*, not causal *truth* (the faithfulness problem).** Chain-of-thought is often **unfaithful**: Turpin et al. (2023) and Anthropic's own work (Chen et al. 2025) show models reach an answer for reasons they don't state, producing plausible-but-misleading traces. Two findings bite directly: faithfulness is *lower on harder questions* — exactly the complex projects your 20%-setting targets — and unfaithful traces were *longer*, so spending more inference on verbose tracking does not buy faithfulness. Implication: the assumption ledger is still valuable (the verifier can check whether the stated logic is internally valid and supports the conclusion, catching invalid reasoning regardless of faithfulness), but it cannot certify that the stated reasoning is *why* the model decided. Pair it with **perturbation-consistency checks** (a metamorphic relation on reasoning: irrelevant input changes shouldn't change the conclusion; relevant ones should) and keep external/deterministic output verification as the real silent-error catch.

**Refinement 2 — replace verbalized confidence with conformal prediction.** Asking the model for confidence intervals yields *systematically overconfident* numbers: on FermiEval, nominal 99% intervals covered the truth ~65% of the time, and this does not improve with scale; miscalibration even *reverses direction* across domains. So naive confidence would under-flag risk exactly when you need it. The rigorous replacement is **conformal prediction** — distribution-free prediction sets with finite-sample *coverage guarantees* ("95% confident the answer is in this set," empirically held). Crucially, conformal calibration needs a held-out exchangeable set — which the runtime's **operation history supplies** — and is best done *per rigor regime* (since miscalibration is domain-dependent). This makes confidence a trustworthy *triage signal* (where to look, where to abstain/escalate) and **unifies it with the closure calibration loop**: calibrating confidence from realized outcomes is the same mechanism as calibrating the rigor coefficient from observed defects (RQ7).

**Net:** keep Idea 1. Build it as *process-supervision-enabling structured records* + *perturbation-consistency faithfulness guards* + *conformal (not verbalized) confidence calibrated from history per regime*.

### Idea 2: capability-tiered roles (strong → plan/verify, standard → implement)

**Directionally sound and well-grounded.** This is **model routing / cascading**, a mature cost-quality technique (FrugalGPT; RouteLLM; SpecInfer's cheap-draft/expensive-verify is a near-exact precedent). The guidance matches yours: reserve the strongest models for hard reasoning, long-horizon planning, and anything where a wrong answer is expensive. And routing can *raise* quality, not just cut cost, by leaning on each model's specialized strengths — supporting your silent-error motivation.

**Refinement 1 — route by task-type, not a rigid strong/weak ladder (capability is multi-dimensional).** A single model can be strong at code yet weak at planning, so a global strong/weak ranking is misleading. The right framing: route each **operation type** to the model best at *that* type — your verb taxonomy (Feature / Test / Refactor / Research / Verify…) is the natural routing key. "Implementation" should go to the best *implementer* (often cheaper, not merely "weaker"); planning/verification to the best *reasoner*.

**Refinement 2 — make the tiering cross-family (capability *and* decorrelation together).** From the v0.6 finding: a verifier must have errors *decorrelated* from the generator's, or self-preference and correlated errors make it over-approve. So the strong verifier should be a *different family* than the implementer — capability tiering and cross-family decorrelation in one move.

**Refinement 3 — the silent-error reduction is conditional.** A weaker implementer raises the *input* error rate; net silent errors fall only if the strong verifier's catch rate compensates — and no verifier is perfect (false discharge, §Part C-F). So **gate the cheap-implementer choice by the rigor regime**: fine in low-rigor / high-discharge-efficiency domains (HTML), not in high-rigor ones (ML, safety-critical), where a strong implementer is warranted too. And don't escalate cascades on *verbalized* confidence (miscalibrated) — use consistency or conformal-calibrated confidence.

**Net:** keep Idea 2, as *cross-family, task-type routing*, with cheap implementers gated by the rigor regime and escalation driven by calibrated (not verbalized) confidence.

---

## Part B — The organizing frame

The rigor metabolism (v0.5/v0.6) says `discharge_efficiency` *is* the exploitable **generation-verification gap** in a domain. That makes one principle organize the entire playbook:

> **Every verification technique is a way to create, widen, or measure the generation-verification gap.** Where the gap is naturally large (machine-checkable ground truth), deterministic checks suffice. Where it collapses (no oracle), techniques must *manufacture* a gap. Where it is uncertain, techniques must *measure* it.

The six families below map to that: create (A), widen (B), exploit step-wise (C), quantify (D), allocate (E), and measure (F).

---

## Part C — The verification playbook

### A. Make the gap real where it has collapsed — **oracle-free verification**
The hardest case is domains with no ground-truth oracle (creative, ML research, open design), where LLM-judge fails and the gap is near-zero. The rigorous answer is the **oracle problem** literature:
- **Metamorphic testing (MT)** — verify via *metamorphic relations* (how outputs *should* change when inputs change: invariance, monotonicity) rather than checking any single output against an oracle. A violated relation reveals a fault *without knowing the correct answer*. Mature across classical software, ML, and now LLMs (191 relations catalogued for NLP). This is the single most valuable addition for the spec's low-discharge domains — it *raises the floor* where direct verification can't reach, and it doubles as the faithfulness/robustness check from Idea 1.
- **Differential testing** (run two independent implementations, compare — disagreement = bug) and **property-based testing** (assert invariants over generated inputs) are the other oracle-free staples. **Invariant inference** (Daikon-style) can *propose* likely invariants from operation history, which become checkable assertions.
*Slots into:* Tribunal, as the verifier of choice for ML/creative/open-research centers.

### B. Widen the gap — **adversarial & ensemble verification**
- **Debate / cross-examination** — the AI-safety-via-debate idea (Irving et al. 2018): an adversarial structure makes the correct answer *easier to identify than to generate*, i.e., it deliberately widens the gap. Multi-agent debate empirically improves factuality and reduces hallucination (Du et al. 2023), and works best with **diverse models** — reinforcing cross-family decorrelation. *Failure mode:* confidently-wrong consensus (correlated agents converging on an error); mitigate with diversity, confidence-weighting, and adversarial injection.
- **Self-consistency / majority voting** — sample N solutions; the *spread* is a free uncertainty signal and a debt trigger (high disagreement ⇒ low confidence ⇒ don't auto-discharge). The generation-verification gap shows up directly as majority-vote accuracy exceeding single-sample accuracy.
- **Best-of-N + verifier reranking** — generate many, let a (decorrelated) verifier select; the workhorse of verifier-guided systems.
*Slots into:* Tribunal (multi-verifier mode) and the grammar's discharge step for high-blast-radius artifacts.

### C. Exploit the gap step-wise — **process verification** (Idea 1, hardened)
Verify reasoning steps, not just outcomes (Lightman et al.); externalize assumptions as structured, checkable records; guard with perturbation-consistency (against unfaithfulness). The metacognitive budget is the *enabling* mechanism — it produces the artifact process-verification consumes — and its size is regime-dependent.
*Slots into:* a per-regime "tracking budget" setting; the Test/Verify verbs.

### D. Quantify the gap — **calibrated uncertainty as triage** (Idea 1, rigorous half)
Use **conformal prediction** (coverage guarantees), not verbalized confidence (overconfident, scale-invariant), calibrated from operation history per rigor regime. Confidence becomes a triage and **abstention/escalation** signal: low-confidence outputs are routed to heavier verification or to the human rather than auto-discharged. Conformal calibration *is* the closure calibration loop applied to confidence.
*Slots into:* the controller (§3.6) and the budget's escalate-or-halt decision.

### E. Allocate the gap-exploiting capability — **cross-family, task-type routing** (Idea 2, refined)
Route each operation type to the best-suited model; verifier cross-family from generator (decorrelation); cheap implementers gated by rigor regime; escalation on calibrated (not verbalized) confidence. Routing is durable across model churn (RouteLLM's transfer property) — good for a model-agnostic runtime.
*Slots into:* the operation→model assignment policy (a projection of the rigor regime + verb type).

### F. Measure the gap itself — **meta-verification** (so `discharge_efficiency` is measured, not guessed)
- **Mutation testing / fault injection** — inject synthetic faults ("mutants") and measure the **mutation score** (fraction caught). It is empirically the most stringent adequacy criterion (coverage is *not* a good proxy — Inozemtseva & Holmes 2014). For SyberRuntime this is the way to **empirically measure a verifier's `discharge_efficiency`** and to **detect false-discharge-prone verifiers** (a verifier that lets injected faults survive is over-approving). LLMs can now generate developer-like mutants, so the runtime can automate periodic mutation campaigns. *Caveat:* compute cost and equivalent-mutant noise.
*Slots into:* the closure loop — the controller runs mutation campaigns to calibrate `discharge_efficiency` per regime from injected-fault catch rates, exactly as it calibrates `accrual_rate` from observed defects. This makes the rigor metabolism *measured end-to-end*.

---

## Part D — Recommended v0.7 integration

The playbook expands the Tribunal from "test execution + LLM-judge" into a **typed verifier suite**, and makes the rigor metabolism *measured* rather than assumed. Concretely:

1. **§3.5 — verifier taxonomy + measured discharge.** Verifiers are typed by family (oracle-free / adversarial / process / calibrated-uncertainty / meta) and ranked by *measured* `discharge_efficiency`; mutation testing supplies the measurement. LLM-judge stays the low/biased-efficiency last resort.
2. **§3.5 + §3.6 — conformal confidence as the discharge/abstention signal**, calibrated from operation history per regime, unified with the closure calibration loop.
3. **§3.1/§3.5 — a regime-scoped "metacognitive tracking budget"** (Idea 1) that produces structured, process-verifiable assumption records, with perturbation-consistency faithfulness guards; budget fraction set by rigor regime.
4. **§4 — cross-family, task-type model routing** (Idea 2) as the operation→model assignment policy; cheap implementers gated by regime; escalation on calibrated confidence.
5. **§4 — Tribunal becomes a verification suite** offering A–F; the kernel ships the cheap subset (deterministic checks, self-consistency, conformal confidence, one mutation pass), with debate/MT-at-scale/formal methods as extensions.

**New / sharpened research questions:**
- **RQ8 — Verifier portfolio optimization:** which verification families maximize *measured* discharge efficiency per rigor regime at what cost, and does a portfolio beat any single verifier? (Solo-tractable via mutation-scored fault injection.)
- **RQ4 (sharpened):** the generator/verifier split must be cross-family; quantify the false-discharge reduction of cross-family vs. same-model verification.
- **RQ6 (sharpened):** does the metacognitive tracking budget + conformal confidence measurably reduce *silent* errors (right-output-wrong-reasoning, and undetected defects) versus outcome-only verification?

**Honest caveats carried in:** process records can be unfaithful (worst on hard problems); debate can converge on confident-wrong consensus; conformal needs exchangeable calibration data; metamorphic relations need domain insight to author; mutation testing is costly. None are blockers — each has a stated mitigation — but the spec should name them.

**Recommendation.** Fold all five integrations in; they cohere into one upgrade ("verification becomes a measured, typed, calibrated portfolio rather than a single judge") and they make both of your ideas defensible rather than merely plausible. The single highest-leverage item is **F (mutation-testing-as-discharge-measurement)**, because it turns `discharge_efficiency` from an assumed parameter into a measured one and closes the calibration loop. Say the word and I'll cut v0.7.
