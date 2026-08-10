# Kiro CLI v3 Configuration Skill

A reusable Agent Skill for creating, updating, auditing, and migrating **Kiro CLI 3.0** configuration.

## Included skills

- [`kiro-v3-config`](./kiro-v3-config/) — create, audit, validate, and migrate Kiro CLI v3 agents and workspace configuration.
- [`kiro-v3-mcp-creator`](./kiro-v3-mcp-creator/) — create and secure MCP servers, stdio/HTTP connections, OAuth, environment variables, and agent permissions.

Install the MCP creator directly from:

```text
https://github.com/idan00189/kiro-v3-config-skill/tree/main/kiro-v3-mcp-creator
```

It covers:

- Markdown custom agents in `.kiro/agents/`
- Capability-based `permissions.rules`
- MCP servers in `.kiro/settings/mcp.json`
- Standalone v3 hooks in `.kiro/hooks/`
- Kiro skills, steering, resources, and `AGENTS.md` integration
- Safe migration from Kiro CLI 2.x
- Deterministic configuration validation

## Install in Kiro

Import this folder from GitHub:

```text
https://github.com/idan00189/kiro-v3-config-skill/tree/main/kiro-v3-config
```

Or copy `kiro-v3-config/` into one of these locations:

```text
.kiro/skills/kiro-v3-config/
~/.kiro/skills/kiro-v3-config/
```

## Use

Invoke it explicitly:

```text
Use kiro-v3-config to create a read-only production readiness reviewer.
```

Or ask naturally:

```text
Migrate my Kiro CLI v2 agents, permissions, MCP config, and hooks to v3.
```

## Validate a workspace

```bash
python3 kiro-v3-config/scripts/validate_kiro_v3.py --root .
```

Useful options:

```bash
# Treat warnings as failures
python3 kiro-v3-config/scripts/validate_kiro_v3.py --root . --strict

# Machine-readable output
python3 kiro-v3-config/scripts/validate_kiro_v3.py --root . --json

# Validate permissions stored outside the repository
python3 kiro-v3-config/scripts/validate_kiro_v3.py \
  --root . \
  --permissions ~/.kiro/settings/permissions.yaml
```

Then run Kiro's own diagnostic when available:

```bash
kiro-cli diagnostic
```

## Safety defaults

The skill uses least privilege, preserves existing configuration, updates `AGENTS.md` additively, keeps secrets in environment variables, and separates read-only review agents from production operators.

For production review agents, it defaults to blocking merge, push, deployment, Argo sync, Kubernetes mutation, infrastructure mutation, database writes, and monitoring changes.

## Documentation basis

The bundled reference is based on the official Kiro documentation:

- [Kiro CLI 3.0](https://kiro.dev/docs/cli/v3/)
- [Agent configuration](https://kiro.dev/docs/custom-agents/configuration-reference/)
- [Permissions](https://kiro.dev/docs/permissions/)
- [Hooks](https://kiro.dev/docs/hooks/)
- [MCP configuration](https://kiro.dev/docs/mcp/configuration/)
- [Agent Skills](https://kiro.dev/docs/skills/)
- [Migration guide](https://kiro.dev/docs/cli/v3/migration-guide/)

## Repository layout

```text
kiro-v3-config/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── assets/
│   └── icon.svg
├── references/
│   └── kiro-cli-v3.md
└── scripts/
    └── validate_kiro_v3.py
```


The MCP creator package follows this layout:

```text
kiro-v3-mcp-creator/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── assets/
│   └── icon.svg
├── references/
│   ├── kiro-mcp-v3.md
│   └── mcp-server-build.md
└── scripts/
    └── kiro_mcp_config.py
```
No license has been added yet.
