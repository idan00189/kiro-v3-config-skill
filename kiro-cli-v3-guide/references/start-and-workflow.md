# Kiro CLI v3: start, interaction, and daily workflow

This reference explains the v3 runtime and the features used inside a session. It was reconciled with official Kiro documentation on 2026-08-10.

## Contents

1. Status and mental model
2. Install, authenticate, and launch
3. Terminal UI and help
4. Models, effort, and modes
5. Prompts, context, and code intelligence
6. Specs
7. Goals
8. Subagents and parallel sessions
9. Sessions, compaction, tangents, and rewind
10. Checkpoints, transcripts, and diagnostics
11. Recommended learning path
12. Official sources

## 1. Status and mental model

Kiro CLI 3.0 is an Early Access engine on the unified Kiro agent harness. The same `.kiro` project configuration can be used by Kiro CLI, IDE, and Web where the feature is supported.

Start v3 explicitly:

```bash
cd /path/to/project
kiro-cli --v3
```

The v3 engine currently uses the terminal UI. Do not claim that classic non-TUI `kiro-cli chat` or `kiro-cli chat --no-interactive` runs the v3 engine. API-key headless mode exists for the classic CLI, but the v3 overview still lists classic mode as unsupported.

The useful mental model is:

```text
prompt + agent instructions + loaded resources
                     |
              visible tools
                     |
          capability permissions
                     |
          approval or automatic use
                     |
             observable result
```

- Instructions influence decisions; they are not a security boundary.
- Tool selection decides what the model can see.
- Permissions decide what operations are authorized.
- Approval settings decide whether an authorized operation still prompts.
- Hooks add deterministic reactions around session or tool events.
- MCP connects external systems.

## 2. Install, authenticate, and launch

### Install

The official download page currently provides this CLI installer for supported macOS and Linux systems:

```bash
curl -fsSL https://cli.kiro.dev/install | bash
```

Use the official Downloads page for Windows and platform-specific packages. Current v3 requirements exclude Amazon Linux 2.

Verify the executable:

```bash
kiro-cli --version
kiro-cli diagnostic
```

### Authenticate interactively

```bash
kiro-cli login
kiro-cli whoami
```

Browser sign-in supports GitHub, Google, AWS Builder ID, AWS IAM Identity Center, and configured organization identity. On an SSH or remote host, `kiro-cli login` can show a device URL and one-time code.

Authentication precedence is:

1. active browser session;
2. `KIRO_API_KEY`;
3. interactive sign-in prompt.

The API key is intended for classic headless automation:

```bash
export KIRO_API_KEY="<set-locally>"
kiro-cli chat --no-interactive "Summarize the repository"
```

That example is not a v3 invocation. Keep this distinction explicit until Kiro documents v3 headless support.

### Start the v3 TUI

```bash
cd ~/work/payments-api
kiro-cli --v3
```

Inside the session:

```text
/help
/changelog
/settings
/tools
```

Validation: the v3 TUI should expose v3 features such as `/spec`, Plan mode, capability permission prompts, and standalone hooks.

## 3. Terminal UI and help

Common commands:

| Command | Use | Example |
| --- | --- | --- |
| `/help` | Ask the documentation-grounded Help agent | `/help How do permissions work in v3?` |
| `/guide` | Switch to the Guide agent | `/guide` |
| `/settings` | Open interactive display/input settings | `/settings display` |
| `/tools` | Inspect visible tools, schemas, and runtime status | `/tools schema` |
| `/mcp` | Inspect MCP servers and exposed tools | `/mcp` |
| `/usage` | View credits and usage | `/usage` |
| `/changelog` | Read current CLI release notes | `/changelog` |
| `/quit` | Exit | `/quit` |

Useful keyboard controls:

- `Shift+Tab`: enter Plan mode; use it again or switch agent to return.
- `Ctrl+S`: queue steering at the next tool boundary.
- `Ctrl+G`: open the agent/subagent execution monitor.
- `Ctrl+T`: toggle tangent mode when enabled.
- `Ctrl+O`: expand collapsed shell output.
- `Ctrl+J`: insert a newline in any terminal.
- `Esc`: close a panel, stop execution, or clear queued input depending on context.
- `Tab`: autocomplete or drill into approval choices.

Example: while a long test run is active, press `Ctrl+S`, then queue:

```text
Do not change public APIs. If the failure is environmental, stop and report it.
```

## 4. Models, effort, and modes

### Model

```text
/model
```

Use the picker because available models can change. A direct model example is:

```text
/model claude-opus-4.6
```

The selected model is persisted in `~/.kiro/settings/cli.json`. Do not hard-code a model name in reusable guidance unless it is confirmed available for the account.

### Reasoning effort

```text
/effort
/effort high
```

Documented levels are `low`, `medium`, `high`, `xhigh`, and `max`, subject to model support. Use lower effort for quick lookups and higher effort for architecture, difficult debugging, or broad migrations.

### Default chat

Use normal chat for bounded exploration or implementation:

```text
Read the authentication module and explain the token refresh path. Do not edit files.
```

### Plan mode

Use Plan mode before complex, risky, or cross-cutting changes:

```text
/plan Replace the cache layer without changing the public API. Include rollback and tests.
```

As of CLI 2.15.0, v3 Plan mode can begin execution after the user approves the plan. Permissions still govern the operations.

### Spec mode

Use a spec when requirements, design decisions, and ordered tasks should be durable project artifacts. See section 6.

### Goal loop

Use `/goal` when the definition of done is testable and bounded. See section 7.

The short decision rule:

| Need | Choose |
| --- | --- |
| One answer or small edit | Default chat |
| Review a proposed approach before action | Plan mode |
| Durable requirements, design, and tasks | Spec |
| Repeated implement-and-verify cycles | Goal |

## 5. Prompts, context, and code intelligence

### Long prompts

Use the configured editor:

```text
/editor
```

Use `/reply` to open the last assistant response as quoted context:

```text
/reply
```

### Temporary context

Inspect or add context for the current agent:

```text
/context show
/context add README.md
/context add "docs/*.md"
/context remove README.md
/context clear
```

These interactive context changes are session-scoped. Put durable project instructions in `AGENTS.md`, steering, a custom agent resource, or a skill.

### File references

Use `@` completion where available:

```text
Compare @src/auth.ts with @tests/auth.test.ts and explain uncovered branches.
```

### Code intelligence

Kiro can use Tree-sitter for structural understanding across supported languages and optional language servers for deeper navigation and diagnostics. Inspect status rather than assuming an LSP is healthy:

```text
/code status
/code logs
```

Example:

```text
Find every implementation of PaymentGateway, then explain which tests cover each implementation.
```

### Tool search

Tool search keeps large MCP catalogs out of the prompt until relevant. Enable it persistently:

```bash
kiro-cli settings toolSearch.enabled true
```

Do not confuse tool discovery with permission. A discovered tool still needs to be visible, authorized, and possibly approved.

## 6. Specs

Specs implement requirements → design → tasks → execution:

```text
/spec new rotate-api-keys
```

Kiro asks for a description. A useful input is:

```text
Add zero-downtime API-key rotation. Preserve current clients, expose metrics,
include rollback, and prove old keys are rejected after the grace period.
```

Choose the spec type:

- **Build a Feature:** full requirements, design, and tasks.
- **Fix a Bug:** investigation, root cause, and correction.
- **Quick Spec:** lighter planning.

Artifacts:

```text
.kiro/specs/rotate-api-keys/
├── requirements.md
├── design.md
└── tasks.md
```

Resume or execute:

```text
/spec
/spec rotate-api-keys
/spec run rotate-api-keys
```

Review and edit each Markdown artifact before execution. `/spec run` works autonomously through the task list, but permissions, hooks, and MCP policy still apply.

Validation:

1. requirements contain measurable acceptance criteria;
2. design covers interfaces, failure handling, security, and rollback;
3. tasks are ordered, small, and verifiable;
4. execution records completion in `tasks.md`;
5. tests and diagnostics prove the result.

Specs are stored in `.kiro/specs`, so they can move between Kiro surfaces with the repository.

## 7. Goals

Start a bounded autonomous verification loop:

```text
/goal Fix the refresh-token race and finish only when the focused tests and typecheck pass
```

Increase the default five-iteration limit only when warranted:

```text
/goal --max 10 Migrate the test suite to Vitest; done means all tests pass and Jest is absent
```

Cancel:

```text
/goal clear
```

Good goal statements contain:

- a single outcome;
- explicit constraints;
- executable success criteria;
- a maximum iteration budget;
- a stop condition for environmental or permission failures.

Production-safe example:

```text
/goal --max 4 Diagnose why consumer lag increased. Use only read-only data sources.
Done means identify the most likely cause, evidence, uncertainty, and next checks.
Do not restart, scale, deploy, commit, or change offsets.
```

Files changed during a goal remain on disk even if the goal is cleared. Use permissions and checkpoints, not the clear command, as the safety boundary.

## 8. Subagents and parallel sessions

Use two different mechanisms intentionally:

| Mechanism | Started by | Best for | Lifetime |
| --- | --- | --- | --- |
| Subagent | Main agent | Focused delegated work in a task graph | Child task |
| `/spawn` | User | Independent, long-running parallel conversation | Separate session |

Subagent prompt example:

```text
Ask the security-reviewer subagent to audit only the authentication diff,
then return findings with file evidence. Do not modify files.
```

Parallel session example:

```text
/spawn --name api-tests Investigate the failing API integration tests; do not edit production code
```

Monitor with `Ctrl+G`. Kiro supports up to four subagents in the documented task graph. Use dependencies when one child needs another child’s output.

Avoid parallelism when tasks write the same files, operate on the same production resource, or require a single coherent decision.

## 9. Sessions, compaction, tangents, and rewind

Kiro automatically saves interactive sessions per working directory.

```text
/chat new
/chat new Review the release candidate
/chat resume
/session-id
```

Save and load explicit exports:

```text
/chat save ./review-session.json
/chat load ./review-session.json
```

### Compaction

```text
/compact
```

Use it when context is nearly full. Kiro replaces older conversation detail with a summary; verify critical requirements after compaction.

### Tangent

```text
/tangent
```

Use tangent mode to explore a side question and then return to the original context. Tangents are named and nestable in v3.

### Rewind

```text
/rewind
/rewind 4
```

Rewind forks the conversation at an earlier turn. It preserves the original session and does not itself restore files.

## 10. Checkpoints, transcripts, and diagnostics

### Checkpoints

Enable the experimental checkpoint feature:

```bash
kiro-cli settings chat.enableCheckpoint true
```

Checkpoints use a shadow Git repository and can restore conversation-associated file state. Hard restore can delete files created after a checkpoint, so inspect the selected checkpoint and restore mode first.

### Transcript

```text
/transcript
/transcript save conversation.md
/transcript save conversation.json --json
```

Review transcripts before sharing because they can contain source, file paths, prompts, and tool output.

### Diagnostics and support logs

Outside the TUI:

```bash
kiro-cli diagnostic
kiro-cli whoami
kiro-cli --version
```

Inside the TUI:

```text
/logdump
/logdump --mcp
/issue
```

Review a log archive before uploading it. MCP logs can contain tool arguments, resource identifiers, or user data.

## 11. Recommended learning path

1. Run `kiro-cli diagnostic`, `kiro-cli login`, and `kiro-cli --v3`.
2. Ask a read-only repository question.
3. Inspect `/tools` and reject any authority you do not understand.
4. Use `/plan` for one medium-sized change.
5. Create one quick spec and inspect its three files.
6. Try a read-only `/goal` with explicit completion criteria.
7. Use `/tangent`, `/compact`, and `/rewind` in a disposable repository.
8. Add the safe workspace configuration from the cookbook.
9. Add MCP only after local agent and permission behavior is understood.
10. Check `/changelog` because v3 is Early Access.

## 12. Official sources

- [What’s new in Kiro CLI 3.0](https://kiro.dev/docs/cli/v3/)
- [Kiro downloads](https://kiro.dev/downloads/)
- [Authentication](https://kiro.dev/docs/getting-started/authentication/)
- [Specs](https://kiro.dev/docs/specs/)
- [Slash commands](https://kiro.dev/docs/reference/slash-commands/)
- [CLI commands](https://kiro.dev/docs/reference/cli-commands/)
- [Subagents](https://kiro.dev/docs/cli/chat/subagents/)
- [Code intelligence](https://kiro.dev/docs/cli/code-intelligence/)
- [Tool search](https://kiro.dev/docs/cli/mcp/tool-search/)
- [CLI changelog](https://kiro.dev/changelog/cli/)
