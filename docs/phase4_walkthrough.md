# SyberRuntime Phase 4 Walkthrough

This walkthrough exercises the current kernel end to end using the CLI.

Use the bundled Python executable if plain `python` is not associated on this
Windows machine:

```powershell
$PY='C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
```

Create a runtime and a thread:

```powershell
& $PY -m syberruntime.cli --root .syberruntime-demo create-thread --intent "Build a traced artifact"
```

Record a Feature operation:

```powershell
& $PY -m syberruntime.cli --root .syberruntime-demo feature <THREAD_ID> --artifact-name traced.txt --intent "Create traced text" --text "release-token"
```

Run deterministic verification and stabilize after it passes:

```powershell
& $PY -m syberruntime.cli --root .syberruntime-demo test <THREAD_ID> <ARTIFACT_DIGEST> --text-contains "release-token"
& $PY -m syberruntime.cli --root .syberruntime-demo stabilize <THREAD_ID> --artifact-digest <ARTIFACT_DIGEST>
```

Measure verifier discharge efficiency:

```powershell
& $PY -m syberruntime.cli --root .syberruntime-demo mutation-campaign <THREAD_ID> <ARTIFACT_DIGEST> --text-contains "release-token"
& $PY -m syberruntime.cli --root .syberruntime-demo metrics
```

Inspect provenance and hardening artifacts:

```powershell
& $PY -m syberruntime.cli --root .syberruntime-demo inspect-artifact <ARTIFACT_DIGEST>
& $PY -m syberruntime.cli --root .syberruntime-demo merkle-root
& $PY -m syberruntime.cli --root .syberruntime-demo inclusion-proof 0
& $PY -m syberruntime.cli --root .syberruntime-demo consistency-proof 1
& $PY -m syberruntime.cli --root .syberruntime-demo snapshot
& $PY -m syberruntime.cli --root .syberruntime-demo export-prov
& $PY -m syberruntime.cli --root .syberruntime-demo export-ro-crate
```

Deletion-rights path:

```powershell
& $PY -m syberruntime.cli --root .syberruntime-demo shred-blob <ARTIFACT_DIGEST> --reason "local deletion-rights exercise"
```

The operation log still preserves the process and references the artifact digest,
but the payload bytes are removed from the content-addressed store.
