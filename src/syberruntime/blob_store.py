"""Content-addressed blob storage for artifact payloads."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from syberruntime.hashing import canonical_json, digest_bytes
from syberruntime.models import ArtifactRef


class BlobStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.blob_root = self.root / "blobs" / "sha256"

    def path_for_digest(self, digest: str) -> Path:
        return self.blob_root / digest[:2] / digest[2:]

    def put_bytes(
        self,
        data: bytes,
        *,
        media_type: str = "application/octet-stream",
        name: str | None = None,
    ) -> ArtifactRef:
        digest = digest_bytes(data)
        path = self.path_for_digest(digest)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            tmp_path = path.parent / f".{path.name}.{uuid4().hex}.tmp"
            tmp_path.write_bytes(data)
            os.replace(tmp_path, path)
        return ArtifactRef(digest=digest, size=len(data), media_type=media_type, name=name)

    def put_text(
        self,
        text: str,
        *,
        media_type: str = "text/plain; charset=utf-8",
        name: str | None = None,
    ) -> ArtifactRef:
        return self.put_bytes(text.encode("utf-8"), media_type=media_type, name=name)

    def get_bytes(self, ref_or_digest: ArtifactRef | str) -> bytes:
        digest = ref_or_digest.digest if isinstance(ref_or_digest, ArtifactRef) else ref_or_digest
        path = self.path_for_digest(digest)
        if not path.exists():
            raise FileNotFoundError(f"Blob not found: {digest}")
        return path.read_bytes()

    def get_text(self, ref_or_digest: ArtifactRef | str) -> str:
        return self.get_bytes(ref_or_digest).decode("utf-8")

    def exists(self, ref_or_digest: ArtifactRef | str) -> bool:
        digest = ref_or_digest.digest if isinstance(ref_or_digest, ArtifactRef) else ref_or_digest
        return self.path_for_digest(digest).exists()

    def shred(self, ref_or_digest: ArtifactRef | str, *, reason: str = "deletion-rights request") -> bool:
        digest = ref_or_digest.digest if isinstance(ref_or_digest, ArtifactRef) else ref_or_digest
        path = self.path_for_digest(digest)
        existed = path.exists()
        if existed:
            path.unlink()
        self._append_tombstone(digest=digest, reason=reason, existed=existed)
        return existed

    def _append_tombstone(self, *, digest: str, reason: str, existed: bool) -> None:
        tombstone_path = self.root / "deletion_tombstones.jsonl"
        tombstone_path.parent.mkdir(parents=True, exist_ok=True)
        with tombstone_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json({"digest": digest, "reason": reason, "existed": existed}))
            handle.write("\n")
