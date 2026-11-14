# Tasks

## 1. Spec

- [ ] 1.1 Add `Infra.chat_ui` (`dashboard` | `librechat`, default `dashboard`) with validation that `librechat` requires
  `packaging='docker'` and `auth='none'`. Verify with tests in `tests/core/spec/test_runtime.py` for the default and
  both rejected combinations.

## 2. Chat API

- [ ] 2.1 Add `core/operations/_chat_api.py` with `GET /v1/models` (enabled agents and units) and non-streaming
  `POST /v1/chat/completions` through `start_run`, with bearer auth on `CHAT_API_KEY`, `X-Agentorg-User-Id` attribution,
  404 for unknown models, the refusal reply and the `X-Agentorg-Run-Id` header. Mount it in `start_operations` only when
  the key is set. Verify with `tests/core/operations/test_chat_api.py` covering each `ui/chat-api` scenario except
  streaming and sessions.
- [ ] 2.2 Add streaming per D2: text deltas, tool-call and delegation lines, the approval message with its console link,
  keep-alive comments, the failure message, usage and `[DONE]`. Verify with tests that drive a run through
  `awaiting_approval` to approved and to rejected.
- [ ] 2.3 Add the D3 session keys with `fork_session` on stale prefixes, user and target isolation and handoff
  routing. Verify with tests for follow-up, regenerate, other user and handoff.

## 3. LibreChat rendering

- [ ] 3.1 Pick and pin the LibreChat version. Confirm from its documentation which header placeholders it supports for
  the user id and conversation id, and record the result in design.md D4. Verify by reading the pinned version's
  configuration reference.
- [ ] 3.2 Add the `librechat.yaml` template per D6 and the LibreChat, MongoDB and Meilisearch services in `compose.yaml`,
  plus `CHAT_API_KEY`, `CONSOLE_URL` and the LibreChat secrets in `example.env`. Verify with render tests that a
  `librechat` spec yields model specs for every agent and unit with the disabled features off, and that a `dashboard`
  spec yields no LibreChat files or services.
- [ ] 3.3 Add `chat_ui` and `chat_url` to `/api/v1/config`. In the dashboard, hide the chat panel and agent chat views
  and show the Chat link when `chat_ui` is `librechat`, and open the Inbox at the `approval` query parameter. Verify that
  the rendered frontend builds with `npm run build` for both values.

## 4. Master

- [ ] 4.1 Add `chat_ui` to `set_runtime_infra` and to the Configure prompt, explaining the extra services. Make the live
  preview serve `chat_ui='dashboard'`. Verify with tests in `tests/master/test_tools.py` and
  `tests/master/ui/test_server.py`.

## 5. End to end

- [ ] 5.1 Add an e2e scenario that boots a `librechat` support-desk org on `local-docker`, sends a chat completion
  through LibreChat's API, follows the approval link and approves it, and sees the reply complete. Verify that it passes
  in `replay` × `local-docker` once the `local-docker` target from `test-architecture` lands.

## 6. Verification

- [ ] 6.1 Run `uv run pytest tests/core/render/test_base.py::test_each_shipped_template_renders` and verify that it
  passes.
- [ ] 6.2 Run `uv run nox -s formatting` and verify that a second run leaves no diff.
- [ ] 6.3 Run `uv run nox -s checks` and verify that it passes.
- [ ] 6.4 Run `uv run nox -s tests` and verify that it passes.
