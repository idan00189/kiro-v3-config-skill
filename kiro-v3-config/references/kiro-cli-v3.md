# Kiro CLI 3.x configuration reference

Use this reference for current Kiro CLI v3 configuration structure and runtime checks. Official documentation was rechecked on 2026-08-16.

## Contents

1. Configuration locations and precedence
2. Custom agents and subagents
3. Persistent permissions
4. MCP configuration and readiness
5. Hooks
6. Skills and resources
7. Validation and migration
8. Official sources

## Configuration locations and precedence

| Configuration | Workspace | User-wide |
| --- | --- | --- |
| Agents | `.kiro/agents/` | `~/.kiro/agents/` |
| Skills | `.kiro/skills/` | `~/.kiro/skills/` |
| Steering | `.kiro/steering/` | `~/.kiro/steering/` |
| Hooks | `.kiro/hooks/` | `~/.kiro/hooks/` |
| MCP | `.kiro/settings/mcp.json` | `~/.kiro/settings/mcp.json` |
| Permissions | Never repository-local | `~/.kiro/settings/permissions.yaml` or `~/.kiro/workspace-roots/<hash>/permissions.yaml` |

Local agents override same-named global agents. MCP server entries merge; a same-named definition resolves agent profile first, then workspace MCP JSON, then user MCP JSON. Custom agents inherit default steering, skills, and `AGENTS.md` unless `chat.disableInheritingDefaultResources` is enabled.

Keep permission policy outside the repository. Kiro prevents agents from writing its protected permission locations so an agent cannot authorize itself.

## Custom agents and subagents

Prefer Markdown for human-maintained agents:

```markdown
---
name: production-readiness-reviewer
description: Read-only reviewer for pull requests and release candidates.
tools: ["read", "web", "subagent", "@incident-data"]
includeMcpJson: true
includePowers: false
resources:
  - file://../../AGENTS.md
  - skill://../skills/**/SKILL.md
permissions:
  rules:
    - capability: fs_read
      effect: allow
    - capability: fs_write
      effect: deny
    - capability: shell
      effect: deny
    - capability: mcp
      match: ["incident-data/get_*", "incident-data/search_*"]
      effect: allow
    - capability: mcp
      match: ["incident-data/delete_*", "incident-data/update_*"]
      effect: deny
toolsSettings:
  subagent:
    availableAgents: ["security-reviewer", "test-reviewer"]
    trustedAgents: ["security-reviewer", "test-reviewer"]
welcomeMessage: "Ready to review production risk."
---

Review evidence and report BLOCK, CONDITIONAL GO, or GO.
Never merge, push, deploy, mutate infrastructure, or change data.
```

The configuration layers have different jobs:

| Field | Purpose |
| --- | --- |
| `tools` | Make built-in and MCP tools visible to the agent |
| `excludedTools` | Remove tools otherwise included by a tag |
| `includeMcpJson` | Include or exclude workspace/user MCP definitions |
| `mcpServers` | Define agent-specific MCP servers or overrides |
| `permissions.rules` | Allow, ask, or deny invocation capabilities |
| `toolsSettings.subagent` | Restrict and trust spawnable custom agents |
| MCP `autoApprove` | Suppress prompts for reviewed MCP tools |
| MCP `disabledTools` | Hide unwanted MCP tools at the server layer |

Current tool tags include `read`, `write`, `shell`, `web`, `subagent`, `knowledge`, `todo_list`, `@mcp`, `@builtin`, and `*`. Use `@server` for all tools from one MCP server and `@server/tool` for one tool.

Subagents share the workspace and durable permission configuration but have isolated conversation context. A custom child uses its own `tools` and agent-scoped `permissions`. `trustedAgents` removes the launch prompt; it does not grant the child's tool calls.

Retain `toolsSettings` only where v3 still documents tool-specific settings such as `subagent.availableAgents` and `subagent.trustedAgents`. Migrate shell and filesystem authority to `permissions.rules`.

## Persistent permissions

Permission rule fields:

- `capability`: `fs_read`, `fs_write`, `shell`, `web_fetch`, `web_search`, `mcp`, `subagent`, `skill`, `power`, `context`, `diagnostics`, `sandbox_network`, or meta-capabilities such as `all`, `builtin`, and `filesystem`.
- `match`: glob patterns scoped to paths, commands, URLs, MCP `server/tool` names, or other capability-specific targets.
- `exclude`: optional glob exceptions.
- `effect`: `allow`, `ask`, or `deny`.

Evaluation is restrictive across every scope: `deny > ask > allow`. No scope has precedence over a more restrictive matching rule.

Example durable user/workspace policy:

```yaml
rules:
  - capability: fs_read
    effect: allow

  - capability: fs_write
    match: ["src/**", "tests/**"]
    effect: ask

  - capability: fs_write
    match: ["**/.env", "**/.env.*", "**/*.pem", "secrets/**"]
    effect: deny

  - capability: shell
    match: ["git status", "git diff*", "git log*"]
    effect: allow

  - capability: shell
    match: ["rm -rf *", "sudo *", "kubectl apply*", "argocd app sync*"]
    effect: deny

  - capability: mcp
    match: ["incident-data/get_*", "incident-data/search_*"]
    effect: allow
```

V3 permission patterns are glob, not regex. Shell, web, and MCP patterns use `*` for an arbitrary character sequence. Filesystem patterns additionally support recursive `**` behavior and other filesystem glob features.

Interactive decisions have different lifetimes:

| Choice | Lifetime |
| --- | --- |
| `Allow` | One invocation |
| `Always allow` → This session | Current process/session |
| `Always allow` → This workspace | Persistent per-user workspace policy |
| `Always allow` → All workspaces | Persistent user policy |

The CLI flags `--trust-tools` and `--trust-all-tools` are session-scoped. Use persistent YAML for future sessions. Reserve unrestricted `capability: all` for explicitly approved isolated CI environments.

Kiro hardcoded rules cannot be weakened. Current documented examples include denial of writes to permission/config policy locations and mandatory prompts for sensitive repository/Kiro control files. Enterprise-managed policy can also force `ask` or `deny`.

## MCP configuration and readiness

Workspace example:

```json
{
  "mcpServers": {
    "local-reader": {
      "command": "uv",
      "args": ["run", "python", "server.py"],
      "env": {
        "SERVICE_TOKEN": "${SERVICE_TOKEN}",
        "LOG_LEVEL": "INFO"
      },
      "disabled": false,
      "autoApprove": ["get_status", "search_records"],
      "disabledTools": ["delete_record", "update_record"]
    },
    "remote-reader": {
      "url": "https://mcp.example.com/mcp",
      "headers": {
        "X-Tenant": "${SERVICE_TENANT}"
      },
      "oauthScopes": ["records:read"],
      "disabled": false
    }
  }
}
```

Use `command` for local stdio servers and `url` for remote HTTP servers. Do not configure OAuth for stdio. Use environment variables or OS credentials for local processes. Use HTTPS for non-loopback HTTP servers.

Approve only reviewed environment-variable names in Kiro's MCP approved-environment-variable setting. Set their values before launching Kiro and never commit literal credentials.

Use `includeMcpJson` deliberately:

- `true`: merge agent, workspace, and user MCP definitions. Suitable when all merged servers should be available.
- `false`: ignore workspace/user MCP JSON and use only agent-defined `mcpServers`. Suitable for a strict agent whose required server set must be stable.

### Startup gate

Start an MCP-dependent interactive session with:

```bash
kiro-cli chat --agent <agent-name> --require-mcp-startup
```

Kiro exits with code `3` when a configured MCP server fails startup. A disabled or excluded server is not part of the effective required set. Keep optional servers outside the gated agent or mark them disabled.

A reusable launcher can enforce both backend preflight and Kiro's native startup gate:

```bash
#!/usr/bin/env bash
set -euo pipefail

python3 scripts/mcp_preflight.py
exec kiro-cli chat --agent <agent-name> --require-mcp-startup "$@"
```

Protocol startup proves that Kiro initialized the server and obtained capabilities; it does not prove every upstream dependency is usable. For each required server, also verify:

1. Configuration parses and the executable or URL is reachable.
2. Referenced environment names are set and approved.
3. OAuth or local identity is valid.
4. MCP `initialize` and `tools/list` succeed.
5. Expected tools are present and pass Kiro tool-schema validation.
6. One safe identity, status, ping, or read-only operation reaches the real upstream service.
7. Returned account, tenant, project, database, or role context matches expectations.

Useful commands:

```bash
kiro-cli mcp list
kiro-cli mcp status --name <server>
```

Inside the session, use `/mcp` for active servers and tools. For remote OAuth, use `/mcp auth <server>`, `/mcp cancel-auth <server>`, and `/mcp logout <server>`.

Kiro excludes invalid MCP tools. The complete prefixed tool name must be no more than 64 characters, match Kiro's documented identifier rules, and have a non-empty description.

## Hooks

Use standalone `.kiro/hooks/<name>.json` files:

```json
{
  "version": "v1",
  "hooks": [
    {
      "name": "validate-after-save",
      "description": "Run a non-mutating validation after source changes",
      "trigger": "PostFileSave",
      "matcher": "\\.(ts|tsx)$",
      "action": {
        "type": "command",
        "command": "npm test -- --runInBand"
      },
      "timeout": 60,
      "enabled": false
    }
  ]
}
```

Current v1 triggers include `SessionStart`, `Stop`, `UserPromptSubmit`, `PreTaskExec`, `PostTaskExec`, `PreToolUse`, `PostToolUse`, `PostFileCreate`, `PostFileSave`, `PostFileDelete`, and `Manual`. Hook matchers remain regex even though permission patterns use glob. A blocking `PreToolUse` command hook can use exit code `2`; review all enabled command hooks as executable code.

Do not rely on a non-blocking `SessionStart` hook as the only MCP readiness gate. Use `--require-mcp-startup` and an external preflight launcher.

## Skills and resources

Kiro skills follow the Agent Skills layout:

```text
.kiro/skills/review-release/
├── SKILL.md
├── scripts/
├── references/
└── assets/
```

Require `name` and `description` frontmatter. Keep names lowercase and hyphenated, and match the folder name. Kiro loads skill metadata at startup and the body on demand.

Use resources according to loading behavior:

```yaml
resources:
  - file://README.md
  - file://docs/**/*.md
  - skill://.kiro/skills/**/SKILL.md
  - type: knowledgeBase
    source: file://./docs
    name: ProjectDocs
    description: Project documentation
    indexType: best
    autoUpdate: true
```

Use `file://` only for small context needed in every session. Prefer `skill://` for reusable procedures and a knowledge base for large indexed content.

## Validation and migration

Validate in layers:

```bash
python3 <skill-dir>/scripts/validate_kiro_v3.py --root . --strict
kiro-cli agent list
kiro-cli agent validate .kiro/agents/<agent-name>.md
kiro-cli doctor --all --strict
kiro-cli mcp list
kiro-cli mcp status --name <required-server>
kiro-cli chat --agent <agent-name> --require-mcp-startup
```

Then inspect `/mcp` and run one safe read-only tool from every required server. Distinguish four outcomes in the report: static-valid, permission-authorized, MCP-initialized, and upstream-healthy.

Migration checklist:

- Run the installed v3 migration helper and preserve backups.
- Replace shell/filesystem `toolsSettings` rules with `permissions.rules`.
- Convert permission regex to glob; leave hook matchers as regex.
- Move embedded hooks to standalone v1 hook files.
- Replace removed tool IDs and removed integrations with explicitly selected current alternatives.
- Preserve `skill://` resources and least-privilege specialist routing.
- Do not use `--trust-all-tools` as a permanent migration shortcut.

## Official sources

- [Kiro CLI commands](https://kiro.dev/docs/reference/cli-commands/)
- [Kiro exit codes and MCP startup gate](https://kiro.dev/docs/reference/exit-codes/)
- [Kiro CLI 3.0 overview](https://kiro.dev/docs/cli/v3/)
- [Agent configuration changes](https://kiro.dev/docs/cli/v3/agent-config/)
- [Custom-agent configuration](https://kiro.dev/docs/custom-agents/configuration-reference/)
- [Subagents](https://kiro.dev/docs/custom-agents/subagents/)
- [Permissions](https://kiro.dev/docs/permissions/)
- [Permissions migration](https://kiro.dev/docs/cli/v3/permissions/)
- [MCP overview](https://kiro.dev/docs/mcp/)
- [MCP configuration](https://kiro.dev/docs/mcp/configuration/)
- [MCP tools and status](https://kiro.dev/docs/mcp/usage/)
- [Hooks](https://kiro.dev/docs/hooks/)
- [Agent Skills](https://kiro.dev/docs/skills/)
- [Steering](https://kiro.dev/docs/steering/)
- [Full migration guide](https://kiro.dev/docs/cli/v3/migration-guide/)
