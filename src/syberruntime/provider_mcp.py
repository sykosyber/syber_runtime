"""Compatibility shim: the provider MCP server moved to syberruntime.providers.

Kept so adapter configs that invoke `python -m syberruntime.provider_mcp`
keep working. New configs should use `python -m syberruntime.providers.server`.
"""

from __future__ import annotations

from syberruntime.providers.errors import ProviderMCPError
from syberruntime.providers.payload import build_user_prompt, call_provider, extract_json_payload
from syberruntime.providers.server import PROTOCOL_VERSION, TOOL_NAME, main

__all__ = [
    "PROTOCOL_VERSION",
    "ProviderMCPError",
    "TOOL_NAME",
    "build_user_prompt",
    "call_provider",
    "extract_json_payload",
    "main",
]

if __name__ == "__main__":
    raise SystemExit(main())
