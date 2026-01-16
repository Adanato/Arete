# TODO: Test Coverage & QA Cleanup

## Remaining Coverage Tasks
Current Coverage: **89.50%**
Target: **95%**

- [ ] **AnkiConnectAdapter Error Handling**:
    - [ ] Update `get_model_styling` and `get_model_templates` to re-raise exceptions instead of swallowing them with `return ""/{}`, or update tests to verify the default return values.
    - [ ] Fix `test_adapter_errors.py` to use `http://127.0.0.1:8765` (matching the adapter's default).
- [ ] **Agent Gemini Mocking**:
    - [ ] Debug `test_create_arete_agent_gemini` in `tests/application/test_agent.py`. The `AttributeError: module 'arete.agent' has no attribute 'genai'` suggests the internal `import google.generativeai as genai` is not mapping to the injected mock correctly in the testing environment.
- [ ] **CLI Logic Gaps**:
    - [ ] Add `deck: Default` to `test_check_file_valid` data in `tests/interface/test_cli_extra.py` to satisfy `arete: true` validation requirements.
    - [ ] Review `src/arete/interface/cli.py` missing lines (mostly help/error cases and less common flags).
- [ ] **AnkiDirectAdapter & Repository**:
    - [ ] Review missing lines in `src/arete/infrastructure/adapters/anki_direct.py` (86%) and `src/arete/infrastructure/anki/repository.py` (84%). Add targeted unit tests for edge cases (e.g. database locks, missing cards).

## Known Issues
- `test_sync_prune_flow` in `tests/integration/test_advanced_scenarios.py` is an expected `xfail`.
- `RuntimeWarning: coroutine 'run_sync_logic' was never awaited` in CLI tests (Typer/Asyncio interaction).

## Next Steps
1. Run `uv run pytest --cov=arete --cov-report=term-missing tests` to see current baseline.
2. Apply fixes to `tests/application/test_agent.py` and `tests/interface/test_cli_extra.py`.
3. Refactor `AnkiConnectAdapter` error handling to be more transparent for testing.
