"""Provider-backed MCP boundary, split by responsibility.

- `server`  : MCP stdio framing and tool dispatch.
- `clients` : provider HTTP dialects (OpenAI-compatible, Anthropic, Google).
- `payload` : prompt construction, JSON extraction, contract validation, retries.
- `errors`  : the typed provider error.

Adapter configs may invoke either `python -m syberruntime.providers.server` or
the legacy `python -m syberruntime.provider_mcp` shim.
"""

from syberruntime.providers.errors import ProviderMCPError
from syberruntime.providers.payload import call_provider
from syberruntime.providers.server import TOOL_NAME, main

__all__ = ["ProviderMCPError", "TOOL_NAME", "call_provider", "main"]
