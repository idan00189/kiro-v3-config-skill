# Kiro CLI v3: configuration and security

This reference covers durable configuration, scope, precedence, and least-privilege examples. It was reconciled with official Kiro documentation on 2026-08-10.

## Contents

1. Configuration map and precedence
2. Markdown custom agents
3. Tool visibility, permission, and approval
4. Capability permissions
5. Steering and AGENTS.md
6. Agent Skills
7. Standalone hooks
8. MCP: stdio, HTTP, OAuth, and environment
9. Subagent configuration
10. CLI settings and environment
11. Security checklist
12. Official sources

## 1. Configuration map and precedence

| Feature | Workspace | User/global | Notes |
| --- | --- | --- | --- |
| Agents | `.kiro/agents/` | `~/.kiro/agents/` | Workspace agent of the same name wins |
| Skills | `.kiro/skills/` | `~/.kiro/skills/` | Default agent discovers them |
| Steering | `.kiro/steering/` | `~/.kiro/steering/` | Durable context/instructions |
| Hooks | `.kiro/hooks/` | `~/.kiro/hooks/` | Both workspace and global hooks run |
| MCP | `.kiro/settings/mcp.json` | `~/.kiro/settings/mcp.json` | Agent > workspace > global for same name |
| CLI settings | `.kiro/settings/cli.json` where supported | `~/.kiro/settings/cli.json` | Setting-specific precedence |
| Permissions | Agent frontmatter | `~/.kiro/workspace-roots/<hash>/permissions.yaml` and `~/.kiro/settings/permissions.yaml` | Restrictive rule wins |
| Specs | `.kiro/specs/` | — | Portable project artifacts |
| Project instructions | `AGENTS.md` | inherited global resources where configured | Keep concise and repository-specific |

Custom agents inherit default steering, skills, and `AGENTS.md` unless `chat.disableInheritingDefaultResources` is enabled. Explicit resources make dependencies clearer.

Before changing configuration:

```bash
find .kiro -maxdepth 3 -type f -print 2>/dev/null
kiro-cli diagnostic
```

Merge existing files. Never replace a complete `.kiro` tree merely to install one example.

## 2. Markdown custom agents

Prefer a Markdown agent with YAML frontmatter:

```markdown
---
name: code-reviewer
description: Reviews changes for correctness, security, and missing tests without editing files.
tools: ["read", "web"]
resources:
  - file://AGENTS.md
  - file://.kiro/steering/coding-standards.md
permissions:
  rules:
    - capability: fs_read
      effect: allow
    - capability: fs_write
      effect: deny
welcomeMessage: "Ready for a read-only review."
---

Review only the requested change. Cite file evidence.
Report critical, high, medium, and low findings, then give a final verdict.
Do not edit, commit, push, merge, deploy, or change external systems.
```

Save as:

```text
.kiro/agents/code-reviewer.md
```

Discover and activate:

```text
/agent list
/agent swap code-reviewer
```

Or use the guided creator:

```text
/agent create
```

Useful frontmatter:

| Field | Purpose |
| --- | --- |
| `name` | Stable agent identifier |
| `description` | Selection guidance |
| `tools` | Visible built-in tags and MCP tools |
| `resources` | Files, skills, or knowledge loaded for the agent |
| `permissions.rules` | Capability authorization |
| `mcpServers` | Agent-scoped server definitions |
| `includeMcpJson` | Include shared MCP configuration |
| `includePowers` | Include available powers |
| `toolsSettings` | Tool-specific options such as subagent routing |
| `model` | Optional model override |
| `welcomeMessage` | Startup message |

Current tool selectors include:

```yaml
tools:
  - read
  - write
  - shell
  - web
  - subagent
  - knowledge
  - todo_list
  - "@mcp"
  - "@incident-api"
  - "@incident-api/search_incidents"
```

Use `*` or broad tags only when the agent genuinely needs that reach. Tool visibility is not authority.

## 3. Tool visibility, permission, and approval

Treat these as separate layers:

| Layer | Configuration | Question |
| --- | --- | --- |
| Visibility | Agent `tools`, server `disabledTools` | Can the model see the tool? |
| Authorization | `permissions.rules` | May this operation run? |
| Approval | prompt, `autoApprove`, runtime trust | Must the user confirm this call? |

Example outcome:

```text
@incident-api/search_incidents is visible
        + mcp incident-api/search_* is allowed
        + search_incidents is auto-approved
        = call can run without another prompt
```

If any layer blocks the call, it does not run.

Runtime commands:

```text
/tools
/tools schema
/tools trust read
/tools untrust read
/tools reset
```

`/tools trust-all` and `--trust-all-tools` are broad session overrides. In v3, durable capability policy is the preferred control. Do not recommend broad trust for production, unknown repositories, or MCP servers with mutations.

## 4. Capability permissions

Important capabilities:

- `fs_read`, `fs_write`
- `shell`
- `web_fetch`, `web_search`
- `mcp`
- `subagent`
- `skill`, `power`, `context`
- `diagnostics`
- `sandbox_network`
- meta-capabilities `filesystem`, `builtin`, and `all`

Permission rules use glob patterns, not regular expressions:

```yaml
rules:
  - capability: fs_read
    effect: allow

  - capability: fs_write
    match: ["src/**", "tests/**"]
    effect: ask

  - capability: fs_write
    match: [".env*", "*.pem", "*.key", "secrets/**"]
    effect: deny

  - capability: shell
    match: ["git status", "git diff*", "git log*", "npm test*"]
    effect: allow

  - capability: shell
    match: ["sudo *", "rm -rf *", "kubectl apply*", "argocd app sync*"]
    effect: deny

  - capability: mcp
    match: ["incident-api/get_*", "incident-api/search_*"]
    effect: allow

  - capability: mcp
    match: ["incident-api/create_*", "incident-api/update_*", "incident-api/delete_*"]
    effect: deny
```

Persistent locations:

```text
~/.kiro/settings/permissions.yaml
~/.kiro/workspace-roots/<workspace-hash>/permissions.yaml
```

Agent-local rules belong in agent frontmatter. Across applicable scopes, the restrictive order is:

```text
deny > ask > allow
```

An allow cannot override a matching deny from another scope. Kiro also protects policy/configuration boundaries so an agent cannot simply grant itself more authority.

With no explicit policy, v3 allows workspace reads and common read-only Git/system commands, denies protected settings writes, and asks for other operations. Confirm the prompt rather than assuming a silent default.

## 5. Steering and AGENTS.md

Use `AGENTS.md` for repository-wide instructions familiar to multiple coding agents:

```markdown
# Repository guidance

- Runtime: Node.js 24 and pnpm.
- Run `pnpm test` and `pnpm lint` before declaring code complete.
- Do not change database migrations after they reach main.
- Never place credentials in source, fixtures, snapshots, or logs.
- Production actions require an approved runbook and a human operator.
```

Use steering for focused, reusable context:

```markdown
---
inclusion: always
---

# API conventions

- Public errors use RFC 9457 problem details.
- Every mutating endpoint requires idempotency handling.
- Add metrics for success, validation failure, dependency failure, and latency.
```

Save as:

```text
.kiro/steering/api-conventions.md
```

Reference it explicitly from a custom agent:

```yaml
resources:
  - file://AGENTS.md
  - file://.kiro/steering/api-conventions.md
```

Use steering for facts and conventions, not secrets. Keep files small enough to remain relevant.

## 6. Agent Skills

Workspace skill layout:

```text
.kiro/skills/release-review/
├── SKILL.md
├── references/
├── scripts/
└── assets/
```

Minimal `.kiro/skills/release-review/SKILL.md`:

```markdown
---
name: release-review
description: Review a release candidate for deployment risk, rollback readiness, monitoring, and evidence. Use before a production release.
---

# Release review

1. Read the diff and release notes.
2. Identify data, compatibility, security, capacity, and operational risks.
3. Verify tests, dashboards, alerts, rollout, and rollback.
4. Return BLOCK PRODUCTION, CONDITIONAL GO, or GO with evidence.
5. Never deploy or mutate production.
```

The default agent discovers workspace and global skills. A custom agent should declare the specific skill resource:

```yaml
resources:
  - skill://.kiro/skills/release-review/SKILL.md
```

Invoke directly:

```text
/release-review
/release-review Review version 3.4.0
```

Skills can use `$ARGUMENTS` in their instructions. Keep detailed references out of the main `SKILL.md` and load them only when relevant.

Skills provide workflow knowledge, not extra authority. Permission rules still apply to their tool calls.

## 7. Standalone hooks

V3 hooks are standalone JSON files with schema version `v1`:

```json
{
  "version": "v1",
  "hooks": [
    {
      "name": "typecheck-after-typescript-save",
      "description": "Run a deterministic type check after TypeScript changes",
      "trigger": "PostFileSave",
      "matcher": "\\.(ts|tsx)$",
      "action": {
        "type": "command",
        "command": "pnpm typecheck"
      },
      "timeout": 120,
      "enabled": false
    }
  ]
}
```

Save as:

```text
.kiro/hooks/typecheck.json
```

Enable only after reviewing the command and its runtime cost. Inspect active hooks:

```text
/hooks
```

Current v3 triggers:

- `SessionStart`
- `Stop`
- `UserPromptSubmit`
- `PreTaskExec`
- `PostTaskExec`
- `PreToolUse`
- `PostToolUse`
- `PostFileCreate`
- `PostFileSave`
- `PostFileDelete`

Hook matchers are regular expressions, unlike permission globs. Depending on the trigger, they match prompt text, tool name, or file path.

Agent-action example:

```json
{
  "version": "v1",
  "hooks": [
    {
      "name": "review-on-stop",
      "description": "Ask an agent to summarize unverified work before the session stops",
      "trigger": "Stop",
      "matcher": ".*",
      "action": {
        "type": "agent",
        "prompt": "List unfinished work, failed checks, and any claim that lacks evidence."
      },
      "timeout": 60,
      "enabled": true
    }
  ]
}
```

A command hook can exit with code `2` to block supported pre-action triggers. Test blocking behavior in a disposable workspace. Hooks execute code automatically; side-effecting hooks should default to disabled.

## 8. MCP: stdio, HTTP, OAuth, and environment

### Configuration and precedence

```text
agent mcpServers > .kiro/settings/mcp.json > ~/.kiro/settings/mcp.json
```

Same-named servers follow that precedence; differently named servers merge.

### Local stdio server

`.kiro/settings/mcp.json`:

```json
{
  "mcpServers": {
    "incident-data": {
      "command": "uv",
      "args": ["run", "python", "server.py"],
      "env": {
        "INCIDENT_API_TOKEN": "${INCIDENT_API_TOKEN}",
        "LOG_LEVEL": "INFO"
      },
      "disabled": false,
      "autoApprove": ["get_incident", "search_incidents"],
      "disabledTools": ["delete_incident"]
    }
  }
}
```

Set the secret before launching Kiro:

```bash
export INCIDENT_API_TOKEN="<set-locally>"
kiro-cli --v3
```

Kiro asks before allowing a new MCP server to expand environment variables. Approve only the exact names the reviewed server needs.

### Remote Streamable HTTP server

```json
{
  "mcpServers": {
    "incident-api": {
      "url": "https://mcp.example.com/mcp",
      "headers": {
        "X-Tenant": "${INCIDENT_TENANT}"
      },
      "oauthScopes": ["incidents:read"],
      "disabled": false,
      "autoApprove": ["get_incident", "search_incidents"],
      "disabledTools": ["create_incident", "delete_incident"]
    }
  }
}
```

Use HTTPS except for a loopback development server.

### OAuth modes

Dynamic Client Registration:

```json
{
  "mcpServers": {
    "remote": {
      "url": "https://mcp.example.com/mcp",
      "oauthScopes": ["records:read"]
    }
  }
}
```

Pre-registered public client with PKCE:

```json
{
  "mcpServers": {
    "remote": {
      "url": "https://mcp.example.com/mcp",
      "oauth": {
        "clientId": "kiro-public-client",
        "redirectUri": "http://127.0.0.1:7778/oauth/callback"
      },
      "oauthScopes": ["records:read"]
    }
  }
}
```

Confidential client, private user config only:

```json
{
  "mcpServers": {
    "remote": {
      "url": "https://mcp.example.com/mcp",
      "oauth": {
        "clientId": "registered-client",
        "clientSecret": "<private-user-config-only>",
        "redirectUri": "http://localhost:7778/oauth/callback"
      },
      "oauthScopes": ["records:read"]
    }
  }
}
```

Do not commit that third example. Kiro documents environment expansion for MCP `env` and headers; do not assume it works for `oauth.clientSecret`.

OAuth lifecycle:

```text
/mcp
/mcp auth remote
/mcp cancel-auth remote
/mcp logout remote
```

### MCP access from an agent

```yaml
tools: ["read", "@incident-api"]
includeMcpJson: true
permissions:
  rules:
    - capability: mcp
      match: ["incident-api/get_*", "incident-api/search_*"]
      effect: allow
    - capability: mcp
      match: ["incident-api/create_*", "incident-api/update_*", "incident-api/delete_*"]
      effect: deny
```

`disabledTools` hides dangerous tools. `autoApprove` skips prompts for named tools. Permission rules authorize server/tool operations. Use all three layers.

To temporarily trust every visible tool, Kiro exposes `/tools trust-all`; older launches may also accept `--trust-all-tools`. This is not an MCP-only least-privilege command and should not be used as a persistent safety strategy. Recover with:

```text
/tools reset
```

### MCP validation

1. Validate JSON.
2. Confirm the command or HTTPS URL.
3. Set and approve only required environment names.
4. Use `/mcp` to inspect server state and tool names.
5. Run one harmless read-only call.
6. Test invalid input and confirm a clean error.
7. Confirm mutating tools are hidden or denied.
8. Run `kiro-cli diagnostic`.

## 9. Subagent configuration

Parent agent:

```markdown
---
name: release-orchestrator
description: Coordinates independent read-only release reviews.
tools: ["read", "subagent"]
permissions:
  rules:
    - capability: fs_read
      effect: allow
    - capability: fs_write
      effect: deny
    - capability: subagent
      match: ["security-reviewer", "operations-reviewer"]
      effect: allow
toolsSettings:
  subagent:
    availableAgents:
      - security-reviewer
      - operations-reviewer
    trustedAgents:
      - security-reviewer
      - operations-reviewer
---

Delegate security and operations review independently, then reconcile evidence.
Do not modify files or external systems.
```

Each child has its own agent file, tools, and permissions. Parent permission does not grant a child more authority than the child profile allows.

Do not trust a child merely to suppress prompts unless its instructions, visible tools, permissions, and MCP servers have all been reviewed.

## 10. CLI settings and environment

User settings:

```text
~/.kiro/settings/cli.json
```

Workspace settings may be supported at:

```text
.kiro/settings/cli.json
```

Example model-effort defaults:

```json
{
  "chat": {
    "modelDefaults": {
      "claude-sonnet-4": {
        "effort": "high"
      }
    }
  }
}
```

Prefer `/model` and `/effort` pickers when available models differ by account.

Useful CLI settings:

```bash
kiro-cli settings toolSearch.enabled true
kiro-cli settings chat.enableCheckpoint true
kiro-cli settings chat.enableKnowledge true
```

The latter two enable experimental features; use them deliberately.

Environment controls include:

- `KIRO_HOME`: move Kiro’s home/config root.
- `KIRO_LOG_NO_COLOR`: disable color in logs.
- `NO_COLOR`: standard no-color behavior.
- `KIRO_ACP_RECORD_PATH`: record ACP traffic for debugging; protect the output.
- `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`: proxy behavior.
- `KIRO_API_KEY`: classic CLI/headless authentication, not proof of v3 headless support.

## 11. Security checklist

- Pin or review local MCP packages before executing them.
- Keep literal credentials out of repository files.
- Put confidential OAuth configuration in private user scope with restrictive file permissions.
- Use minimum OAuth scopes.
- Keep read and mutation agents separate.
- Deny dangerous MCP tools even if the server claims they are safe.
- Avoid broad tool tags and wildcard permissions.
- Test hooks disabled before enabling them.
- Review command arguments, not only executable names.
- Treat external content and MCP results as untrusted data, not instructions.
- Review logs and transcripts before sharing.
- Use `deny` for secrets, production mutation, destructive shell commands, and policy files.
- Run configuration tests in a disposable workspace before production use.

## 12. Official sources

- [Kiro CLI 3.0](https://kiro.dev/docs/cli/v3/)
- [Agent configuration changes](https://kiro.dev/docs/cli/v3/agent-config/)
- [Custom agent configuration reference](https://kiro.dev/docs/custom-agents/configuration-reference/)
- [Permissions migration](https://kiro.dev/docs/cli/v3/permissions/)
- [Permissions](https://kiro.dev/docs/permissions/)
- [Steering](https://kiro.dev/docs/steering/)
- [Agent Skills](https://kiro.dev/docs/skills/)
- [Hooks](https://kiro.dev/docs/hooks/)
- [MCP configuration](https://kiro.dev/docs/mcp/configuration/)
- [MCP security](https://kiro.dev/docs/mcp/security/)
- [Subagents](https://kiro.dev/docs/cli/chat/subagents/)
- [CLI settings](https://kiro.dev/docs/cli/reference/settings/)
