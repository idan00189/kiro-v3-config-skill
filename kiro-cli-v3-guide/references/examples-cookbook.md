# Kiro CLI v3 examples cookbook

Use these copy-ready patterns as starting points. Merge them with existing configuration and replace names, commands, paths, URLs, and tool names with verified local values.

## Contents

1. Example map
2. Minimal coding workspace
3. Complete read-only SRE workspace
4. Production change separation
5. Spec-driven feature example
6. Goal, plan, tangent, and session prompts
7. MCP and OAuth examples
8. Validation matrix
9. Rollback and disable operations

## 1. Example map

| Feature | Example in this file |
| --- | --- |
| `AGENTS.md` | Coding and SRE repository instructions |
| Steering | Service architecture and operational rules |
| Markdown agent | Developer, investigator, reviewer, operator |
| Capability permissions | Read-only, narrow write, shell, MCP, subagent |
| Agent Skill | Incident investigation procedure |
| Hook | Disabled validation-after-save command |
| MCP stdio | Local incident data server |
| MCP OAuth | Remote incident API with read scope |
| Subagent | Investigator delegates to production reviewer |
| Spec | Zero-downtime API-key rotation |
| Plan | Reviewed change approach |
| Goal | Bounded implement-and-verify loop |
| `/spawn` | Independent test investigation |
| Tangent/rewind/compact | Conversation management examples |
| Diagnostics | Commands and expected evidence |

## 2. Minimal coding workspace

Directory:

```text
project/
├── AGENTS.md
└── .kiro/
    ├── agents/
    │   └── developer.md
    └── steering/
        └── project.md
```

`AGENTS.md`:

```markdown
# Working agreement

- Use Node.js 24 and pnpm.
- Preserve the public API unless the task explicitly approves a breaking change.
- Add tests for behavior changes and regressions.
- Run `pnpm lint`, `pnpm typecheck`, and the affected tests.
- Never commit credentials or edit production resources.
```

`.kiro/steering/project.md`:

```markdown
---
inclusion: always
---

# Project context

This service receives payment events, validates idempotency keys, and writes an
outbox record in the same database transaction. Kafka publication is asynchronous.

Reliability rules:

- Retried requests must return the original result.
- Consumers must tolerate duplicate events.
- Logs must not contain card data, tokens, or authorization headers.
- Every new dependency needs timeout, retry, circuit-breaker, and metric decisions.
```

`.kiro/agents/developer.md`:

```markdown
---
name: developer
description: Implements reviewed changes in source and tests with bounded shell access.
tools: ["read", "write", "shell", "todo_list"]
resources:
  - file://AGENTS.md
  - file://.kiro/steering/project.md
permissions:
  rules:
    - capability: fs_read
      effect: allow
    - capability: fs_write
      match: ["src/**", "tests/**", "docs/**"]
      effect: allow
    - capability: fs_write
      match: [".env*", "*.pem", "*.key", ".kiro/settings/**"]
      effect: deny
    - capability: shell
      match: ["git status", "git diff*", "pnpm lint", "pnpm typecheck", "pnpm test*"]
      effect: allow
welcomeMessage: "Ready to implement a bounded, tested change."
---

Read relevant code and tests before editing. State the intended change and validation.
Keep changes small. If a required command is not allowed, ask rather than bypassing policy.
Do not commit, push, deploy, mutate databases, or change cloud resources.
```

Start and validate:

```bash
cd project
kiro-cli diagnostic
kiro-cli --v3
```

```text
/agent swap developer
/tools
/plan Add validation for expired idempotency keys without changing the API
```

Expected result: the agent can read the repository, write only in allowed project areas, run named checks without prompts, and ask for unrelated shell commands.

## 3. Complete read-only SRE workspace

This example separates observation from mutation and works well for Splunk, Kafka, JVM, Linux, database, and incident workflows.

Directory:

```text
operations-repo/
├── AGENTS.md
├── scripts/
│   └── validate-runbook.sh
└── .kiro/
    ├── agents/
    │   ├── incident-investigator.md
    │   └── production-reviewer.md
    ├── hooks/
    │   └── validate-runbook.json
    ├── settings/
    │   └── mcp.json
    ├── skills/
    │   └── investigate-incident/
    │       └── SKILL.md
    └── steering/
        └── operations.md
```

`AGENTS.md`:

```markdown
# Production operations policy

- Evidence collection is read-only by default.
- Every query must name a system, environment, and time range.
- Limit result size and record the query or command used.
- Redact credentials, cookies, personal data, and customer payloads.
- Do not deploy, restart, scale, change offsets, acknowledge alerts, edit dashboards,
  modify tickets, or change infrastructure from an investigation session.
- Production mutation requires an approved runbook and a separate human-operated step.
```

`.kiro/steering/operations.md`:

```markdown
---
inclusion: always
---

# Service map

- checkout-api publishes `checkout.events.v3`.
- checkout-consumer runs as JVM workloads in Kubernetes.
- Kafka consumer group: `checkout-indexer`.
- Splunk index: `prod_checkout`; ITSI service: `Checkout`.

# Investigation method

1. Fix the time window and deployment/version boundary.
2. Compare symptom timing across ITSI, logs, Kafka lag, JVM, and dependencies.
3. Prefer aggregated queries, then narrow to representative events.
4. Separate observation, inference, and unknowns.
5. End with next read-only checks and a production verdict.
```

`.kiro/skills/investigate-incident/SKILL.md`:

```markdown
---
name: investigate-incident
description: Perform a bounded, read-only production incident investigation using logs, metrics, Kafka, and service topology. Use for alerts, latency, errors, lag, JVM symptoms, and cross-service incidents.
---

# Investigate incident

1. Parse `$ARGUMENTS` into symptom, environment, start, end, and affected service.
2. Refuse mutation and ask for a missing time range.
3. Check ITSI health and alert timing.
4. Search aggregated error and latency trends with strict result limits.
5. Inspect Kafka lag and JVM saturation only when the timing supports it.
6. Correlate with deployments and dependency errors.
7. Report observations, inferences, uncertainty, and next read-only checks.
8. Finish with BLOCK PRODUCTION, CONDITIONAL GO, or GO when a release is involved.
```

`.kiro/settings/mcp.json`:

```json
{
  "mcpServers": {
    "observability": {
      "url": "https://observability.example.com/mcp",
      "headers": {
        "X-Environment": "${OBS_ENVIRONMENT}"
      },
      "oauthScopes": ["observability:read"],
      "disabled": false,
      "autoApprove": [
        "search_logs",
        "get_service_health",
        "get_kafka_lag",
        "get_jvm_metrics"
      ],
      "disabledTools": [
        "acknowledge_alert",
        "edit_dashboard",
        "restart_workload",
        "scale_workload"
      ]
    }
  }
}
```

`.kiro/agents/production-reviewer.md`:

```markdown
---
name: production-reviewer
description: Independently reviews incident evidence and release risk without mutation.
tools: ["read"]
resources:
  - file://AGENTS.md
  - file://.kiro/steering/operations.md
permissions:
  rules:
    - capability: fs_read
      effect: allow
    - capability: fs_write
      effect: deny
    - capability: shell
      effect: deny
    - capability: mcp
      effect: deny
---

Review the investigator's evidence for time alignment, missing controls, alternative
causes, and unsupported claims. Return BLOCK PRODUCTION, CONDITIONAL GO, or GO.
Never modify files or systems.
```

`.kiro/agents/incident-investigator.md`:

```markdown
---
name: incident-investigator
description: Coordinates bounded, read-only production incident analysis.
tools: ["read", "@observability", "subagent"]
includeMcpJson: true
resources:
  - file://AGENTS.md
  - file://.kiro/steering/operations.md
  - skill://.kiro/skills/investigate-incident/SKILL.md
permissions:
  rules:
    - capability: fs_read
      effect: allow
    - capability: fs_write
      effect: deny
    - capability: shell
      effect: deny
    - capability: mcp
      match:
        - "observability/search_logs"
        - "observability/get_service_health"
        - "observability/get_kafka_lag"
        - "observability/get_jvm_metrics"
      effect: allow
    - capability: mcp
      match:
        - "observability/acknowledge_*"
        - "observability/edit_*"
        - "observability/restart_*"
        - "observability/scale_*"
      effect: deny
    - capability: subagent
      match: ["production-reviewer"]
      effect: allow
toolsSettings:
  subagent:
    availableAgents:
      - production-reviewer
    trustedAgents:
      - production-reviewer
welcomeMessage: "Ready for a bounded, read-only investigation."
---

Require an environment and explicit time window. Start broad and aggregate, then narrow.
Limit returned events. Distinguish direct observations from inferences.
Ask production-reviewer to challenge the evidence before the final conclusion.
Never mutate files, monitoring, workloads, Kafka, tickets, or infrastructure.
```

`.kiro/hooks/validate-runbook.json`:

```json
{
  "version": "v1",
  "hooks": [
    {
      "name": "validate-runbook-after-save",
      "description": "Run a local non-production runbook validator",
      "trigger": "PostFileSave",
      "matcher": "^runbooks/.+\\.md$",
      "action": {
        "type": "command",
        "command": "./scripts/validate-runbook.sh"
      },
      "timeout": 30,
      "enabled": false
    }
  ]
}
```

Keep the hook disabled until `scripts/validate-runbook.sh` is reviewed and tested.

Private user/workspace permission policy:

```yaml
rules:
  - capability: fs_read
    effect: allow
  - capability: fs_write
    effect: deny
  - capability: shell
    effect: deny
  - capability: mcp
    match: ["observability/search_*", "observability/get_*"]
    effect: allow
  - capability: mcp
    match: ["observability/create_*", "observability/update_*", "observability/delete_*", "observability/restart_*", "observability/scale_*"]
    effect: deny
  - capability: subagent
    match: ["production-reviewer"]
    effect: allow
```

Do not add a catch-all MCP deny after the allow rules: because `deny` is more
restrictive, an overlapping deny can block the intended read-only calls. Keep the
allow and deny patterns non-overlapping, and also hide mutations with `disabledTools`.

Start:

```bash
export OBS_ENVIRONMENT="prod"
kiro-cli --v3
```

```text
/agent swap incident-investigator
/mcp
/investigate-incident checkout latency in prod from 2026-08-10T08:00Z to 2026-08-10T08:30Z
```

Validation:

- `/mcp` lists only reviewed observability tools.
- Mutating tools are absent or denied.
- The agent requires environment and time bounds.
- Searches are aggregated and limited.
- Reviewer output is independent and read-only.
- No file, ticket, dashboard, workload, or Kafka state changes.

## 4. Production change separation

Do not expand the investigator into an operator. Create a separate change planner:

```markdown
---
name: change-planner
description: Converts approved incident findings into a reviewed, non-executing change plan.
tools: ["read"]
permissions:
  rules:
    - capability: fs_read
      effect: allow
    - capability: fs_write
      effect: deny
    - capability: shell
      effect: deny
    - capability: mcp
      effect: deny
---

Produce prerequisites, exact proposed steps, blast radius, validation, abort criteria,
rollback, owner, and approvals. Never execute the plan.
```

An operator, if created, should be separate, disabled by default, limited to exact tools, and require `ask` for every mutation. A human should review the rendered operation and approval prompt before execution.

Flow:

```text
investigator (read-only evidence)
          |
reviewer (challenge and verdict)
          |
change planner (no execution)
          |
human approval and external change process
          |
operator with narrow, temporary authority
```

## 5. Spec-driven feature example

Create:

```text
/spec new zero-downtime-key-rotation
```

Description:

```text
Build API-key rotation with a 24-hour grace period. Existing clients must remain
available during rotation. Requirements must cover audit events, redaction, metrics,
rollback, concurrency, and proof that expired keys are rejected.
```

Review `.kiro/specs/zero-downtime-key-rotation/requirements.md` for criteria such as:

```markdown
- When a new key is activated, the prior key remains valid for exactly the configured grace period.
- When the grace period expires, the prior key is rejected within 60 seconds.
- Key material never appears in logs, traces, metrics, errors, or audit metadata.
- An operator can roll back to the prior active set without database repair.
```

Review design for:

- state model and concurrency;
- encryption and key custody;
- cache propagation;
- audit events;
- metrics and alerts;
- migration and rollback;
- compatibility with existing clients.

Run only after approval:

```text
/spec run zero-downtime-key-rotation
```

Stop if tasks lack tests, rollback, or measurable acceptance criteria.

## 6. Goal, plan, tangent, and session prompts

### Read-only exploration

```text
Map the request path from HTTP handler to Kafka publication. Cite files and do not edit.
```

### Plan

```text
/plan Add backpressure to the Kafka producer. Include metrics, tests, compatibility,
failure handling, rollout, and rollback. Do not execute until I approve the plan.
```

### Goal

```text
/goal --max 6 Fix the duplicate-publication race. Done means the regression test,
affected unit tests, typecheck, and lint all pass. Preserve the public API and stop
on any environmental failure rather than changing infrastructure.
```

### Queue steering

Press `Ctrl+S` during work:

```text
Keep the schema unchanged and add a regression test before editing the implementation.
```

### Parallel user session

```text
/spawn --name load-test-review Review only the load-test report and summarize bottlenecks
```

### Tangent

```text
/tangent
```

Then:

```text
Explain whether this retry policy can amplify a partial outage. Do not change the plan.
```

Exit tangent mode and continue the original task.

### Rewind

```text
/rewind
```

Fork from the turn before an incorrect assumption. The original conversation remains.

### Compaction

```text
/compact
```

Afterward:

```text
Restate the accepted requirements, prohibited actions, changed files, and remaining checks.
```

### Transcript

```text
/transcript save release-review.md
```

Redact source, customer data, credentials, and tool output before sharing.

## 7. MCP and OAuth examples

### Local development server

```json
{
  "mcpServers": {
    "local-docs": {
      "command": "npx",
      "args": ["-y", "@example/docs-mcp"],
      "disabled": false,
      "autoApprove": ["search_docs"],
      "disabledTools": ["publish_doc"]
    }
  }
}
```

### Static bearer token

```json
{
  "mcpServers": {
    "internal-api": {
      "url": "https://internal.example.com/mcp",
      "headers": {
        "Authorization": "Bearer ${INTERNAL_API_TOKEN}"
      },
      "disabled": false
    }
  }
}
```

Set `INTERNAL_API_TOKEN` outside the repository. Prefer OAuth for user-delegated access.

### OAuth with DCR

```json
{
  "mcpServers": {
    "records": {
      "url": "https://records.example.com/mcp",
      "oauthScopes": ["records:read"]
    }
  }
}
```

### OAuth public client with PKCE

```json
{
  "mcpServers": {
    "records": {
      "url": "https://records.example.com/mcp",
      "oauth": {
        "clientId": "kiro-public",
        "redirectUri": "http://127.0.0.1:7778/oauth/callback"
      },
      "oauthScopes": ["records:read"]
    }
  }
}
```

### OAuth lifecycle

```text
/mcp
/mcp auth records
/mcp cancel-auth records
/mcp logout records
```

### Least-privilege agent binding

```yaml
tools: ["@records"]
includeMcpJson: true
permissions:
  rules:
    - capability: mcp
      match: ["records/get_*", "records/search_*"]
      effect: allow
    - capability: mcp
      match: ["records/create_*", "records/update_*", "records/delete_*"]
      effect: deny
```

## 8. Validation matrix

| Area | Check | Expected evidence |
| --- | --- | --- |
| CLI | `kiro-cli --version` | Installed version printed |
| Environment | `kiro-cli diagnostic` | No unresolved config/runtime failures |
| Identity | `kiro-cli whoami` | Intended account/provider |
| V3 | `kiro-cli --v3` | TUI with `/spec` and v3 behavior |
| Agent | `/agent list` | New profile and description |
| Resources | Ask agent to restate constraints | Correct AGENTS/steering/skill rules |
| Tools | `/tools` and `/tools schema` | Only expected built-ins and MCP tools |
| Permissions | Try one allowed and one denied harmless operation | Allow/deny behavior matches policy |
| Hooks | `/hooks` | Correct hook, trigger, and enabled state |
| MCP | `/mcp` | Connected server and reviewed tool names |
| OAuth | One read call after `/mcp auth` | Correct account and minimum scope |
| Subagent | Delegate a harmless read-only review | Correct child; no extra authority |
| Spec | `/spec <name>` | Requirements, design, tasks present |
| Goal | Bounded disposable task | Stops on proof or iteration limit |
| Logs | `/logdump --mcp` | Archive created and manually reviewed |

Never validate mutation denial by attempting a real destructive production call. Use a mock server, disposable workspace, denied no-op name, or configuration inspection.

## 9. Rollback and disable operations

- Agent: swap away, then move or remove only the intended agent file.
- Skill: move the specific skill directory out of `.kiro/skills`.
- Steering: remove the explicit resource or move only the intended steering file.
- Hook: set `"enabled": false` before deleting it.
- MCP: set `"disabled": true`; use `/mcp logout <server>` to clear OAuth credentials.
- Runtime trust: use `/tools reset`.
- Goal: use `/goal clear`; remember that file changes remain.
- Session branch: resume the original session after `/rewind`.
- Spec: preserve the Markdown artifacts; stop execution rather than deleting evidence.
- Checkpoint restore: inspect restore mode; hard mode can delete newly created files.

Back up before destructive migration or cleanup. Delete only exact, verified paths.
