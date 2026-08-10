# Kiro CLI v3 migration and troubleshooting

Use this reference to migrate from CLI 2.x, diagnose configuration behavior, and separate v3 limitations from setup errors. It was reconciled with official Kiro documentation on 2026-08-10.

## Contents

1. Before migration
2. Breaking-change map
3. Ordered migration
4. Agent migration
5. Permission migration
6. Hook migration
7. MCP and AWS migration
8. Session and runtime migration
9. Diagnostic decision tree
10. Common failures
11. Logs and support bundle
12. Official sources

## 1. Before migration

V3 runs alongside the 2.x engine during Early Access. Test it explicitly:

```bash
kiro-cli --version
kiro-cli diagnostic
kiro-cli --v3
```

Inventory configuration:

```bash
find .kiro -maxdepth 4 -type f -print 2>/dev/null
find ~/.kiro/agents ~/.kiro/hooks ~/.kiro/settings -maxdepth 3 -type f -print 2>/dev/null
```

Create a recoverable backup before converting agents, hooks, permissions, or sessions:

```bash
backup_dir="$PWD/kiro-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup_dir"
cp -a .kiro "$backup_dir/workspace-kiro" 2>/dev/null || true
cp -a ~/.kiro/agents "$backup_dir/global-agents" 2>/dev/null || true
cp -a ~/.kiro/hooks "$backup_dir/global-hooks" 2>/dev/null || true
cp -a ~/.kiro/sessions "$backup_dir/sessions" 2>/dev/null || true
```

Protect the backup because it may contain private settings, session content, or credentials. Do not commit it.

Record:

- CLI version and operating system;
- active account from `kiro-cli whoami`;
- workspace path;
- custom agent names;
- MCP server names and transport;
- hooks and enabled state;
- old trust flags or tool settings;
- any production authority.

## 2. Breaking-change map

| Area | CLI 2.x | CLI 3.0 | Action |
| --- | --- | --- | --- |
| Engine | Default/classic harness | Unified harness, opt in with `--v3` | Test explicitly |
| Agent format | Mostly JSON, tool IDs | Markdown supported, tag-based tools | Run `/upgrade-agent`, review |
| Permission policy | Trust flags and tool settings | Capability rules | Rewrite manually |
| Pattern syntax | Some rules used regex | Permission `match` uses glob | Convert carefully |
| Hooks | Embedded in agent | Standalone `.kiro/hooks/*.json` | Move and rewrite |
| Hook names | Older camelCase triggers | PascalCase v3 triggers | Use official mapping |
| MCP | Existing servers | OAuth, `disabledTools`, `autoApprove` | Review authority layers |
| AWS tool | Built-in `aws_tool` | Removed | Select an explicit MCP server |
| Sessions | V2 serialization | New incompatible v3 format | Preserve backups |
| “Vibe” | Older naming | Default chat | Update docs/prompts |
| Supervised/trust model | Trust-centered | Capability permissions | Replace policy |
| Non-TUI classic mode | Supported for classic engine | Not supported by v3 | Use TUI |

Do not perform a mechanical rename and assume equivalent security. The v3 model separates visibility, authorization, and approval.

## 3. Ordered migration

Use this order:

1. Update the CLI and run diagnostics.
2. Back up workspace, global config, and sessions.
3. Start `kiro-cli --v3` in a disposable branch or test repository.
4. Migrate one custom agent.
5. Replace trust/tool policy with capability permissions.
6. Move embedded hooks into standalone files, disabled.
7. Replace `aws_tool` and review all MCP tools.
8. Validate steering, skills, `AGENTS.md`, and resource inheritance.
9. Run a read-only smoke test.
10. Test one narrow write in a disposable file if the agent should write.
11. Enable deterministic hooks one at a time.
12. Compare results to v2 before adopting v3 for critical work.

Keep v2 and v3 sessions conceptually separate.

## 4. Agent migration

Inside a v3 session:

```text
/upgrade-agent
```

Choose a v2 custom agent. The command produces a universal configuration intended to work across current surfaces. Review the result rather than accepting it blindly.

Manual target:

```markdown
---
name: reviewer
description: Reviews code without modifying it.
tools: ["read"]
permissions:
  rules:
    - capability: fs_read
      effect: allow
    - capability: fs_write
      effect: deny
    - capability: shell
      effect: deny
---

Review only. Cite file evidence and do not mutate anything.
```

Review checklist:

- name matches the intended filename and identity;
- description accurately triggers the agent;
- old tool IDs became supported tags or named MCP selectors;
- filesystem and shell policy moved into `permissions.rules`;
- resources point to existing files or skills;
- inherited resources are intentional;
- MCP server inclusion is intentional;
- inline credentials are removed;
- subagent availability and trust are explicit;
- instructions state prohibited operations.

Validate:

```text
/agent list
/agent swap reviewer
/tools
```

If custom agents receive unwanted default resources:

```bash
kiro-cli settings chat.disableInheritingDefaultResources true
```

Use this only when explicit resources are complete, because it also disables inherited default steering, skills, and `AGENTS.md`.

## 5. Permission migration

Old intent such as “trust read and Git status, ask before writes, deny deploys” becomes:

```yaml
rules:
  - capability: fs_read
    effect: allow
  - capability: fs_write
    effect: ask
  - capability: shell
    match: ["git status", "git diff*", "git log*"]
    effect: allow
  - capability: shell
    match: ["kubectl apply*", "helm upgrade*", "argocd app sync*", "terraform apply*"]
    effect: deny
```

Conversion rules:

- regex `^git (status|diff)` is not a v3 permission pattern;
- use separate globs such as `git status` and `git diff*`;
- keep secret-path denies explicit;
- match MCP as `server/tool`;
- use `ask` when a reviewed human decision is required;
- remember `deny > ask > allow` across scopes.

Common migration error:

```yaml-invalid
rules:
  - capability: mcp
    match: ["ops/get_*"]
    effect: allow
  - capability: mcp
    effect: deny
```

The catch-all deny is more restrictive and can block the intended allow. Prefer non-overlapping mutation denies:

```yaml
rules:
  - capability: mcp
    match: ["ops/get_*", "ops/search_*"]
    effect: allow
  - capability: mcp
    match: ["ops/create_*", "ops/update_*", "ops/delete_*", "ops/restart_*"]
    effect: deny
```

Use `/tools` to inspect runtime resolution. Use `/tools reset` to clear session trust and test persistent policy again.

## 6. Hook migration

V2 embedded concept:

```json
{
  "hooks": {
    "postFileSave": [
      {
        "matcher": "\\.ts$",
        "command": "npm test"
      }
    ]
  }
}
```

V3 standalone target:

```json
{
  "version": "v1",
  "hooks": [
    {
      "name": "test-after-typescript-save",
      "description": "Run tests after a TypeScript file is saved",
      "trigger": "PostFileSave",
      "matcher": "\\.ts$",
      "action": {
        "type": "command",
        "command": "npm test"
      },
      "timeout": 120,
      "enabled": false
    }
  ]
}
```

Save as `.kiro/hooks/test-after-save.json`.

Migration rules:

- move hooks out of agent config;
- add `"version": "v1"`;
- use a `hooks` array;
- give every hook a name and description;
- use an `action` object;
- convert trigger names with the official migration table;
- use PascalCase v3 triggers;
- keep matchers as regex;
- set an explicit timeout;
- start with `"enabled": false`.

Check:

```text
/hooks
```

If a hook can block an action, test exit code `2` in a disposable workspace. Do not test blocking by attempting a real production mutation.

## 7. MCP and AWS migration

`aws_tool` is removed in v3. Replace it with a reviewed MCP server that exposes only the AWS operations needed for the agent.

Unsafe migration:

```yaml
tools: ["@mcp"]
```

Safer migration:

```yaml
tools: ["@aws-observer"]
includeMcpJson: true
permissions:
  rules:
    - capability: mcp
      match: ["aws-observer/describe_*", "aws-observer/get_*", "aws-observer/list_*"]
      effect: allow
    - capability: mcp
      match: ["aws-observer/create_*", "aws-observer/update_*", "aws-observer/delete_*", "aws-observer/start_*", "aws-observer/stop_*"]
      effect: deny
```

Server:

```json
{
  "mcpServers": {
    "aws-observer": {
      "command": "uvx",
      "args": ["reviewed-aws-observer-package"],
      "env": {
        "AWS_PROFILE": "${AWS_PROFILE}",
        "AWS_REGION": "${AWS_REGION}"
      },
      "disabled": true,
      "autoApprove": ["describe_service", "get_metric", "list_resources"],
      "disabledTools": ["delete_resource", "update_service"]
    }
  }
}
```

The package name is intentionally a placeholder. Select and pin a real, reviewed implementation before enabling it. Use an AWS identity with read-only IAM permissions; Kiro policy is an additional layer, not a replacement for server-side authorization.

For existing MCP:

1. confirm stdio command or HTTPS URL;
2. remove literal credentials;
3. approve only required environment names;
4. minimize OAuth scopes;
5. hide mutating tools with `disabledTools`;
6. narrow `autoApprove`;
7. add MCP capability rules;
8. inspect `/mcp`;
9. make one safe read call;
10. clear credentials with `/mcp logout <server>` when rotating accounts.

## 8. Session and runtime migration

V3 session data is not backward-compatible with v2. Back up sessions before changing workflows:

```bash
cp -a ~/.kiro/sessions "$PWD/kiro-v2-sessions-backup"
```

Do not expect a v3 session to appear when returning to the v2 engine.

Known v3 gaps:

- Amazon Linux 2 is unsupported;
- classic non-TUI mode does not use v3;
- v3 sessions cannot be resumed in v2.

If automation requires:

```bash
kiro-cli chat --no-interactive "..."
```

treat it as classic/headless CLI behavior unless current official documentation explicitly adds v3 headless support.

## 9. Diagnostic decision tree

Use this order:

```text
Does the executable run?
  no  -> installation, PATH, platform, proxy
  yes
   |
Does `kiro-cli diagnostic` pass?
  no  -> fix the first concrete diagnostic
  yes
   |
Does `kiro-cli --v3` open the TUI?
  no  -> version, Early Access availability, unsupported platform
  yes
   |
Is the agent listed?
  no  -> path, extension, frontmatter, schema
  yes
   |
Is the tool visible in `/tools` or `/mcp`?
  no  -> tools tag, includeMcpJson, disabledTools, server/governance
  yes
   |
Is the operation authorized?
  no  -> capability, match glob, more restrictive scope
  yes
   |
Does approval complete?
  no  -> runtime trust, env approval, OAuth, user denial
  yes
   |
Does execution succeed?
  no  -> command path, server logs, timeout, invalid input, dependency
```

Fix the earliest failing layer.

## 10. Common failures

### V3 features are missing

Symptoms: no `/spec`, classic interface, or legacy behavior.

Checks:

```bash
kiro-cli --version
kiro-cli --v3
```

Confirm the launch really used `--v3`.

### Agent is not listed

Check:

- `.kiro/agents/<name>.md` or `~/.kiro/agents/<name>.md`;
- valid YAML frontmatter delimited by `---`;
- `name` and `description`;
- no malformed indentation;
- workspace agent shadowing a global agent of the same name;
- output from `kiro-cli diagnostic`.

Then:

```text
/agent list
```

### Agent sees too many resources

Custom agents inherit default resources by default. Explicitly list resources and, only if intended, enable:

```bash
kiro-cli settings chat.disableInheritingDefaultResources true
```

### Agent cannot use a visible tool

Inspect:

```text
/tools
/tools schema
```

Then check capability rules in agent, workspace-root, and global scope. A matching `deny` or `ask` is more restrictive than `allow`.

### Permission rule does not match

Permission patterns are globs. Hook matchers are regex. Do not copy one syntax into the other.

Examples:

```text
Permission: git diff*
Hook regex: ^git diff
```

Inspect the exact command/path/server-tool string displayed in the approval or diagnostics.

### MCP server is absent

Check:

- file is valid JSON;
- server is not `"disabled": true`;
- custom agent has `includeMcpJson: true` or inline `mcpServers`;
- agent `tools` exposes `@mcp`, `@server`, or `@server/tool`;
- organization governance has not disabled MCP;
- the process has reached an idle boundary after a hot reload.

Use:

```text
/mcp
```

### MCP tool is absent

Check `disabledTools`, server startup logs, and the tool definition. Kiro rejects invalid definitions. Tool names including prefixes must meet Kiro’s length/character limits and have a non-empty description.

### MCP environment variable is not available

Check:

```bash
test -n "$REQUIRED_NAME" && echo set || echo missing
```

Launch Kiro from the shell where the variable is set and approve only that environment name when prompted. Never print the value.

### OAuth repeats or stalls

Use:

```text
/mcp cancel-auth server-name
/mcp logout server-name
/mcp auth server-name
```

Then check:

- exact registered redirect URI;
- DCR support or configured client ID;
- PKCE/public vs confidential client requirements;
- minimum accepted scopes;
- protected-resource and authorization-server metadata;
- issuer, audience, and clock skew at the server;
- browser/pop-up behavior.

Do not paste tokens or client secrets into logs or chat.

### Hook does not run

Check:

- path `.kiro/hooks/<name>.json` or `~/.kiro/hooks/<name>.json`;
- `"version": "v1"`;
- supported PascalCase trigger;
- `"enabled": true`;
- regex matches the event field;
- command exists and is executable;
- timeout is adequate;
- `/hooks` lists it.

### Skill is not discovered

Check:

- `.kiro/skills/<skill-name>/SKILL.md` or global equivalent;
- lowercase hyphenated name;
- frontmatter `name` and `description`;
- custom agent has an explicit `skill://` resource if needed;
- inherited resources have not been disabled.

Try:

```text
/skill-name
```

### Subagent cannot start

Check:

- child agent is listed;
- parent has `subagent` in `tools`;
- child is in `toolsSettings.subagent.availableAgents`;
- `subagent` capability matches the child name;
- child has its own sufficient but narrow tools and permissions;
- current workload has not reached the concurrency limit.

### Headless command does not behave like v3

This is currently a documented gap, not necessarily a config failure. Use the v3 TUI or confirm a newer release changed the limitation.

### V2 session is missing in v3 or vice versa

The formats are incompatible. Return to the corresponding engine or use a transcript/export as a human-readable bridge. Do not edit raw session storage.

## 11. Logs and support bundle

Basic evidence:

```bash
kiro-cli --version
kiro-cli whoami
kiro-cli diagnostic
```

In the TUI:

```text
/mcp
/tools
/hooks
/code status
/code logs
/logdump
/logdump --mcp
/issue
```

Before sharing a bundle:

- unpack or inspect it locally;
- remove credentials, authorization headers, cookies, customer data, source snippets, and private paths where possible;
- state the reproduction steps, expected behavior, actual behavior, version, platform, and whether the session was v2 or v3;
- preserve timestamps and the first error;
- avoid publicly uploading a full bundle unless the support channel explicitly requires it.

## 12. Official sources

- [Kiro CLI 3.0](https://kiro.dev/docs/cli/v3/)
- [Full v3 migration guide](https://kiro.dev/docs/cli/v3/migration-guide/)
- [Agent upgrade](https://kiro.dev/docs/cli/v3/agent-config/)
- [Permissions migration](https://kiro.dev/docs/cli/v3/permissions/)
- [Hooks migration](https://kiro.dev/docs/cli/v3/hooks-migration/)
- [MCP configuration](https://kiro.dev/docs/mcp/configuration/)
- [Kiro CLI settings](https://kiro.dev/docs/cli/reference/settings/)
- [Slash commands](https://kiro.dev/docs/reference/slash-commands/)
- [Kiro CLI changelog](https://kiro.dev/changelog/cli/)
