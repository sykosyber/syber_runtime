"""Merkle history tree proofs for the append-only operation log."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from syberruntime.hashing import digest_bytes


class MerkleProofError(ValueError):
    pass


def leaf_hash(entry_hash: str) -> str:
    return digest_bytes(b"\x00" + entry_hash.encode("ascii"))


def node_hash(left: str, right: str) -> str:
    return digest_bytes(b"\x01" + bytes.fromhex(left) + bytes.fromhex(right))


@dataclass(frozen=True)
class InclusionProof:
    tree_size: int
    leaf_index: int
    leaf_hash: str
    root_hash: str
    path: tuple[dict[str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "tree_size": self.tree_size,
            "leaf_index": self.leaf_index,
            "leaf_hash": self.leaf_hash,
            "root_hash": self.root_hash,
            "path": [dict(item) for item in self.path],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InclusionProof":
        return cls(
            tree_size=int(data["tree_size"]),
            leaf_index=int(data["leaf_index"]),
            leaf_hash=str(data["leaf_hash"]),
            root_hash=str(data["root_hash"]),
            path=tuple({"side": str(item["side"]), "hash": str(item["hash"])} for item in data.get("path", [])),
        )

    def verify(self) -> bool:
        return verify_inclusion(self)


@dataclass(frozen=True)
class ConsistencyProof:
    old_size: int
    new_size: int
    old_root_hash: str
    new_root_hash: str
    prefix_entry_hashes: tuple[str, ...]
    appended_entry_hashes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "old_size": self.old_size,
            "new_size": self.new_size,
            "old_root_hash": self.old_root_hash,
            "new_root_hash": self.new_root_hash,
            "prefix_entry_hashes": list(self.prefix_entry_hashes),
            "appended_entry_hashes": list(self.appended_entry_hashes),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConsistencyProof":
        return cls(
            old_size=int(data["old_size"]),
            new_size=int(data["new_size"]),
            old_root_hash=str(data["old_root_hash"]),
            new_root_hash=str(data["new_root_hash"]),
            prefix_entry_hashes=tuple(str(item) for item in data.get("prefix_entry_hashes", [])),
            appended_entry_hashes=tuple(str(item) for item in data.get("appended_entry_hashes", [])),
        )

    def verify(self) -> bool:
        return verify_consistency(self)


class MerkleHistoryTree:
    def __init__(self, entry_hashes: tuple[str, ...] | list[str]) -> None:
        self.entry_hashes = tuple(entry_hashes)

    @property
    def size(self) -> int:
        return len(self.entry_hashes)

    def root_hash(self, size: int | None = None) -> str:
        selected = self.entry_hashes if size is None else self.entry_hashes[:size]
        return merkle_root(selected)

    def inclusion_proof(self, leaf_index: int, *, size: int | None = None) -> InclusionProof:
        tree_size = self.size if size is None else size
        if leaf_index < 0 or leaf_index >= tree_size:
            raise MerkleProofError(f"Leaf index {leaf_index} outside tree size {tree_size}")
        leaves = tuple(leaf_hash(entry_hash) for entry_hash in self.entry_hashes[:tree_size])
        path: list[dict[str, str]] = []
        index = leaf_index
        level = list(leaves)
        while len(level) > 1:
            if index % 2 == 0:
                sibling_index = index + 1
                if sibling_index < len(level):
                    path.append({"side": "right", "hash": level[sibling_index]})
            else:
                sibling_index = index - 1
                path.append({"side": "left", "hash": level[sibling_index]})
            index //= 2
            level = _next_level(level)
        return InclusionProof(
            tree_size=tree_size,
            leaf_index=leaf_index,
            leaf_hash=leaves[leaf_index],
            root_hash=level[0] if level else merkle_root(()),
            path=tuple(path),
        )

    def consistency_proof(self, old_size: int, new_size: int | None = None) -> ConsistencyProof:
        target_size = self.size if new_size is None else new_size
        if old_size < 0 or target_size < old_size or target_size > self.size:
            raise MerkleProofError(f"Invalid consistency sizes old={old_size}, new={target_size}")
        prefix = self.entry_hashes[:old_size]
        appended = self.entry_hashes[old_size:target_size]
        return ConsistencyProof(
            old_size=old_size,
            new_size=target_size,
            old_root_hash=merkle_root(prefix),
            new_root_hash=merkle_root(prefix + appended),
            prefix_entry_hashes=prefix,
            appended_entry_hashes=appended,
        )


def merkle_root(entry_hashes: tuple[str, ...] | list[str]) -> str:
    if not entry_hashes:
        return digest_bytes(b"")
    level = [leaf_hash(entry_hash) for entry_hash in entry_hashes]
    while len(level) > 1:
        level = _next_level(level)
    return level[0]


def verify_inclusion(proof: InclusionProof) -> bool:
    if proof.leaf_index < 0 or proof.leaf_index >= proof.tree_size:
        return False
    computed = proof.leaf_hash
    index = proof.leaf_index
    for step in proof.path:
        side = step["side"]
        sibling = step["hash"]
        if side == "left":
            computed = node_hash(sibling, computed)
        elif side == "right":
            computed = node_hash(computed, sibling)
        else:
            return False
        index //= 2
    return computed == proof.root_hash


def verify_consistency(proof: ConsistencyProof) -> bool:
    if proof.old_size < 0 or proof.new_size < proof.old_size:
        return False
    if len(proof.prefix_entry_hashes) != proof.old_size:
        return False
    if len(proof.prefix_entry_hashes) + len(proof.appended_entry_hashes) != proof.new_size:
        return False
    old_root = merkle_root(proof.prefix_entry_hashes)
    new_root = merkle_root(proof.prefix_entry_hashes + proof.appended_entry_hashes)
    return old_root == proof.old_root_hash and new_root == proof.new_root_hash


def _next_level(level: list[str]) -> list[str]:
    next_level: list[str] = []
    for index in range(0, len(level), 2):
        left = level[index]
        if index + 1 >= len(level):
            next_level.append(left)
        else:
            next_level.append(node_hash(left, level[index + 1]))
    return next_level
