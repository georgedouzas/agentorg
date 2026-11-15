# Tasks

## 1. Spec

- [x] 1.1 Always require `CHAT_API_KEY` in `Runtime` and add a `librechat` setup step on Railway, with no chat-UI
  option. Verify with tests in `tests/core/spec/test_runtime.py`.

## 2. Chat API

- [x] 2.1 Add `core/operations/_chat_api.py` with `GET /v1/models` (enabled agents and units) and non-streaming
  `POST /v1/chat/completions` through `start_run`, with bearer auth on `CHAT_API_KEY`, `X-Agentorg-User-Id` attribution,
  404 for unknown models, the refusal reply and the `X-Agentorg-Run-Id` header. Mount it in `start_operations` only when
  the key is set. Verify with `tests/core/operations/test_chat_api.py`.
- [x] 2.2 Add streaming per D2: text deltas, tool-call and delegation lines, the approval message with its console link,
  keep-alive comments, the failure message, usage and `[DONE]`. Verify with tests that drive a run through
  `awaiting_approval` to approved and to rejected.
- [x] 2.3 Add the D3 session keys with `fork_session` on every resume, user and target isolation and handoff routing.
  Verify with tests for follow-up, regenerate, other user and handoff.
- [x] 2.4 Split the router per D7 into the OpenAI layer and the `ChatBackend` protocol, with `OrgChat` as the node's
  backend and the user's email read from `X-Agentorg-User-Email`. Verify that the existing chat API tests pass
  unchanged in behaviour.
- [x] 2.5 Add the org commands per D8 (`/approve`, `/reject`, `/runs`, `/run`, `/inbox`, `/status`, `/pause`, `/resume`,
  `/help`) with the approver check, and name the commands in the approval-hold message. Verify with tests for each
  scenario in `ui/chat-api`'s command and approval requirements.

## 3. LibreChat for rendered orgs

- [x] 3.1 Pick and pin the LibreChat version and confirm its header placeholders. Verify against the pinned version's
  source.
- [x] 3.2 Always render `librechat.yaml` per D6, the LibreChat, MongoDB and Meilisearch services in `compose.yaml`, the
  LibreChat variables in `example.env` and the README instructions. Verify with render tests for docker and local orgs.
- [x] 3.3 Send `{{LIBRECHAT_USER_EMAIL}}` as `X-Agentorg-User-Email` from `librechat.yaml`. Verify with the render test.
- [x] 3.4 Remove the dashboard's chat panel, agent panel, chat-event parsing, Master view and the
  `/api/v1/reasoners/{name}/stream` route. Selecting an agent opens LibreChat, and the Inbox opens at the `approval`
  query parameter. Verify that the rendered frontend builds with `npm run build` and the rendered route tests pass.

## 4. Master

- [x] 4.1 Remove the chat-UI choice from `set_runtime_infra` and explain LibreChat in the Configure prompt. Verify with
  `tests/master/test_tools.py`.
- [x] 4.2 Add `MasterChat` per D7 and D8, serving model `agentorg` and the interview commands at `/v1` on the master
  server. Verify with tests in `tests/master/ui/test_chat.py` for an interview turn, a stage change, each command and a
  blocked `/next`.
- [x] 4.3 Start the preview node with the chat key on the master port plus one. Verify with a test in
  `tests/master/ui/test_preview.py` that the preview environment carries `CHAT_API_KEY` and the pinned port.
- [x] 4.4 Ship `master/ui/librechat/compose.yaml` and make `agentorg ui` check Docker, write the secrets and the two-
  endpoint `librechat.yaml`, start the stack, open LibreChat and stop the stack on exit, per D9. Verify with tests in
  `tests/cli/test_ui.py` with Docker calls faked, and by running `agentorg ui` once against a real Docker daemon.
- [x] 4.5 Reduce the master page to the preview and stage progress with a link to LibreChat, and delete
  `POST /api/chat`. Verify with `tests/master/ui/test_server.py`.

## 5. End to end

- [ ] 5.1 Add an e2e scenario that boots a support-desk org on `local-docker`, sends a chat completion through
  LibreChat's API, approves the held action with `/approve`, and sees the reply complete. Verify that it passes in
  `replay` × `local-docker` once the `local-docker` target from `test-architecture` lands.
- [x] 5.2 Update the golden-path scenario in `test-architecture` to drive the interview through the master's chat API.
  Verify that it collects and that its self-tests still pass.

## 6. Verification

- [x] 6.1 Run `uv run pytest tests/core/render/test_base.py::test_each_shipped_template_renders` and verify that it
  passes.
- [x] 6.2 Run `uv run nox -s formatting` and verify that a second run leaves no diff.
- [x] 6.3 Run `uv run nox -s checks` and verify that it passes.
- [x] 6.4 Run `uv run nox -s tests` and verify that it passes.
