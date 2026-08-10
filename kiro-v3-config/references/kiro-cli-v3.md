# Kiro CLI 3.0 configuration reference

Use this reference for current v3 structure. The official pages were checked on 2026-08-10 and reported updates through 2026-08-06.

## Contents

1. Paths and precedence
2. Custom agents
3. Permissions
4. MCP
5. Hooks
6. Skills and resources
7. Migration checklist
8. Official sources

## Paths and precedence

| Configuration | Workspace | User-wide |
| --- | --- | --- |
| Agents | `.kiro/agents/` | `~/.kiro/agents/` |
| Skills | `.kiro/skills/` | `~/.kiro/skills/` |
| Steering | `.kiro/steering/` | `~/.kiro/steering/` |
| Hooks | `.kiro/hooks/` | `~/.kiro/hooks/` |
| MCP | `.kiro/settings/mcp.json` | `~/.kiro/settings/mcp.json` |
| Permissions | Not stored in the repo | `~/.kiro/settings/permissions.yaml` or `~/.kiro/workspace-roots/<hash>/permissions.yaml` |

Local agents override same-named global agents. MCP precedence is agent profile, then workspace MCP, then global MCP. Custom agents inherit default steering, skills, and `AGENTS.md` unless `chat.disableInheritingDefaultResources` is enabled.

## Custom agents

Prefer Markdown profiles for human-maintained agents:

```markdown
---
name: production-readiness-reviewer
description: Read-only reviewer for production risks in pull requests and release candidates.
tools: ["read", "web", "@mcp"]
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
    - capability: subagent
      effect: ask
welcomeMessage: "Ready to review production risk."
---

Review evidence and report BLOCK PRODUCTION, CONDITIONAL GO, or GO.
Never merge, push, deploy, mutate infrastructure, change databases, or alter monitoring.
```

The `tools` field controls visibility. Current tags include `read`, `write`, `shell`, `web`, `subagent`, `knowledge`, `todo_list`, `@mcp`, `@builtin`, and `*`. Named MCP access uses `@server` or `@server/tool`.

Authorization belongs in `permissions.rules`. `allowedTools` still exists, but capability policy is clearer for filesystem, shell, web, MCP, and subagent authority. Avoid `toolsSettings` for shell and filesystem policy; it remains only for tool-specific settings such as MCP or subagent configuration.

Valid resource forms:

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

## Permissions

Permission rule fields:

- `capability`: `fs_read`, `fs_write`, `shell`, `web_fetch`, `web_search`, `mcp`, `subagent`, `skill`, `power`, `context`, `diagnostics`, `sandbox_network`, or meta-capabilities such as `all`, `builtin`, and `filesystem`.
- `match`: glob patterns scoped to paths, commands, URLs, or `server/tool` names.
- `exclude`: optional glob exceptions.
- `effect`: `allow`, `ask`, or `deny`.

Evaluation is restrictive: deny > ask > allow, regardless of scope. V3 permission patterns are glob, not regex.

Example user/workspace policy:

```yaml
rules:
  - capability: fs_read
    effect: allow
  - capability: fs_write
    match: ["src/**", "tests/**"]
    effect: ask
  - capability: fs_write
    match: ["*.env", "*.pem", "*.key", "secrets/**"]
    effect: deny
  - capability: shell
    match: ["git status", "git diff*", "git log*"]
    effect: allow
  - capability: shell
    match: ["rm -rf *", "sudo *", "kubectl apply*", "argocd app sync*"]
    effect: deny
  - capability: mcp
    match: ["splunk/search", "splunk/get_*", "kafka/describe_*"]
    effect: allow
```

Kiro has hardcoded invariants. In particular, agents cannot grant themselves permission by writing settings policy, and writes to agent/hook configuration may still ask even when another scope allows them.

## MCP

Workspace file: `.kiro/settings/mcp.json`.

```json
{
  "mcpServers": {
    "local-server": {
      "command": "npx",
      "args": ["-y", "@org/server"],
      "env": {
        "API_TOKEN": "${API_TOKEN}"
      },
      "disabled": false,
      "autoApprove": ["read_status"],
      "disabledTools": ["delete_resource"]
    },
    "remote-server": {
      "url": "https://example.com/mcp",
      "headers": {
        "Authorization": "Bearer ${API_TOKEN}"
      },
      "disabled": false
    }
  }
}
```

Local servers use `command`, optional `args`, `env`, `timeout`, and `requestTimeout`. Remote servers use `url`, optional `headers`, `oauth`, and `oauthScopes`. Both can use `disabled`, `autoApprove`, and `disabledTools`. Environment values expand `${VAR}` at runtime. Do not commit literal credentials.

## Hooks

Hooks are standalone `.kiro/hooks/<name>.json` files:

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

Current triggers: `SessionStart`, `Stop`, `UserPromptSubmit`, `PreTaskExec`, `PostTaskExec`, `PreToolUse`, `PostToolUse`, `PostFileCreate`, `PostFileSave`, and `PostFileDelete`. Some migration docs also describe `Manual`. Matchers are regex and match prompt text, tool name, or file path depending on trigger. Blocking command hooks exit with code 2 for blockable triggers. Agent actions use `{ "type": "agent", "prompt": "..." }`.

Review every automatic hook as executable code. Default side-effecting hooks to disabled until the user explicitly enables them.

## Skills and resources

Kiro skills follow the open Agent Skills layout:

```text
.kiro/skills/review-release/
├── SKILL.md
├── scripts/
├── references/
└── assets/
```

`SKILL.md` must have frontmatter with a lowercase hyphenated `name` matching its folder and a precise `description`. Kiro loads name and description at startup, then loads the body on demand. Use workspace skills for project/team workflows and global skills for reusable personal workflows.

## Migration checklist

- Run the available v3 migration helper (`kiro-cli agent migrate` and/or `/upgrade-agent` in an active session), retain backups, then review output.
- Replace `toolsSettings` shell/filesystem policy with `permissions.rules`.
- Convert permission regex to glob; hooks continue to use regex.
- Move embedded hooks to `.kiro/hooks/*.json` and convert trigger names to PascalCase.
- Replace removed `aws_tool` with an explicitly selected MCP server.
- Back up v2 sessions before upgrading because v3 session format is not backward-compatible.
- Run `kiro-cli diagnostic` after migration.

## Official sources

- [Kiro CLI 3.0 overview](https://kiro.dev/docs/cli/v3/)
- [Agent config changes](https://kiro.dev/docs/cli/v3/agent-config/)
- [Agent configuration reference](https://kiro.dev/docs/custom-agents/configuration-reference/)
- [Permissions](https://kiro.dev/docs/permissions/)
- [Permissions migration](https://kiro.dev/docs/cli/v3/permissions/)
- [Hooks](https://kiro.dev/docs/hooks/)
- [Hooks migration](https://kiro.dev/docs/cli/v3/hooks-migration/)
- [MCP configuration](https://kiro.dev/docs/mcp/configuration/)
- [Agent Skills](https://kiro.dev/docs/skills/)
- [Steering](https://kiro.dev/docs/steering/)
- [Full migration guide](https://kiro.dev/docs/cli/v3/migration-guide/)
