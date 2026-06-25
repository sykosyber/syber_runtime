# Live Release Gate Traceability

This is not a new roadmap phase. It is the first concrete execution of the v1
section 7 release gate after Phases 0 through 4 are implemented.

| Component | Roadmap requirement | Status |
|---|---|---|
| Live MCP stdio adapter | v0.6 section 3.7; v1 Phase 2; v1 section 7 | Implemented in `src/syberruntime/adapters.py` as `MCPStdioToolAdapter`. |
| Live adapter config loader | v0.6 section 3.7; v1 Phase 2; v1 section 7 | Implemented in `src/syberruntime/adapter_config.py`; defaults to `transport: mcp_stdio`. |
| Configured `ai-loop` CLI | v1 Phase 2; v1 section 7 | Implemented in `src/syberruntime/cli.py`. |
| Acceptance live-MCP criterion | v1 section 7 | Implemented as `live_mcp_real_ai_endpoint`; warns when no config is supplied and fails on bad supplied configs. |
| Dogfood report model | v0.6 section 6; v1 Phase 3; v1 section 7 | Implemented in `src/syberruntime/dogfood.py`. |
| Dogfood report CLI | v1 Phase 3; v1 section 7 | Implemented as `dogfood-report`. |
| Model capability envelope | v1 section 6; v1 Phase 3; v1 section 7 | Dogfood and harness reports record available role models, constrained access, unavailable preferred models, and lower-bound interpretation. |
| Acceptance dogfood criterion | v0.6 section 6; v1 Phase 3; v1 section 7 | Implemented as `dogfooding_rq0_rq6_results`; warns when no report directory exists and fails reports without artifact digests or explicit model capability envelopes. |
| First dogfood evidence report | v0.6 section 6; v1 Phase 3; v1 section 7 | Collected as `docs/dogfood_reports/rq0_rq6_run_001.json` from `.syberruntime-dogfood-rq0-rq6-001`. |
| Real endpoint config template | v1 Phase 2; roadmap risk mitigation for MCP/model churn in v1 section 6 | Added as `examples/mcp_adapter_config.example.json`. |
| Mock MCP server fixture | v1 Phase 2; roadmap risk mitigation for MCP/model churn in v1 section 6 | Added as `examples/mock_mcp_server.py` only for local smoke verification. |

## Remaining External Gate Items

1. Fill `examples/mcp_adapter_config.example.json` with the real MCP/model endpoint command and tool name.
2. Re-run `acceptance-check` with both `--mcp-config` and
   `--dogfood-report-dir`; v1 readiness requires `overall_status: pass`.
