---
name: kiro-cli-v3-guide
description: Teach, explain, demonstrate, design, audit, migrate, or troubleshoot Kiro CLI 3.0 end to end. Use when someone asks how Kiro CLI v3 works or needs practical examples for installation, authentication, the v3 TUI, models and effort, Plan mode, specs, goals, sessions, checkpoints, custom Markdown agents, capability permissions, steering, AGENTS.md, Agent Skills, hooks, MCP and OAuth, tool search, subagents, parallel sessions, code intelligence, migration from v2, diagnostics, or safe production and SRE workflows.
---

# Kiro CLI v3 Guide

## Purpose

Give an accurate mental model of Kiro CLI v3, then turn it into a smallest useful, copy-ready example. Cover the whole system when asked for a complete guide; load only the relevant reference for a focused question.

Kiro CLI 3.0 is an Early Access agent engine shared with Kiro IDE and Kiro Web. Treat the v3 pages as authoritative for v3 behavior. Generic CLI pages can describe classic behavior that is not yet available in v3, especially non-interactive chat and session compatibility.

## Route the request

| Request | Read |
| --- | --- |
| Learn, install, authenticate, navigate, plan, use specs, run goals, manage sessions, or understand models | [start-and-workflow.md](references/start-and-workflow.md) |
| Configure agents, permissions, skills, steering, hooks, MCP, OAuth, environment variables, settings, or subagents | [configuration-and-security.md](references/configuration-and-security.md) |
| Build a complete example workspace or adapt a pattern for coding, SRE, incident response, or production review | [examples-cookbook.md](references/examples-cookbook.md) |
| Upgrade v2, diagnose errors, compare classic and v3 behavior, or recover a broken setup | [migration-and-troubleshooting.md](references/migration-and-troubleshooting.md) |

For broad “everything I need to know” requests, read all four references in that order.

## Response workflow

1. Identify the installed CLI version, platform, workspace, and goal when they materially affect the answer.
2. State the v3 mental model in one sentence: instructions and resources shape behavior; visible tools define reach; permissions authorize actions; approval settings decide which authorized actions still require confirmation.
3. Distinguish documented v3 behavior from generic/classic CLI behavior.
4. Start with the smallest safe command or file and explain where it belongs.
5. Add one realistic example for every feature discussed.
6. Explain scope and precedence whenever multiple config locations exist.
7. Show how to validate the result in Kiro.
8. Call out Early Access limitations and version-sensitive syntax.

When the user asks for actual configuration changes, use the companion `kiro-v3-config` skill if available. For creating or securing an MCP server, use `kiro-v3-mcp-creator` if available.

## Teaching pattern

For each feature, provide:

- **What it is:** the problem it solves.
- **When to use it:** a concrete decision rule.
- **Smallest example:** a command or complete file.
- **Authority:** what the feature can read, write, execute, or call.
- **Validation:** the command, slash command, or observable result that proves it works.
- **Version note:** any Early Access or classic-vs-v3 caveat.

Prefer a guided path over a feature dump:

1. Start Kiro with `kiro-cli --v3`.
2. Explore safely with read-only tools and Plan mode.
3. Capture durable project context in `AGENTS.md` or steering.
4. Create a focused Markdown custom agent.
5. Add capability permissions.
6. Add reusable Agent Skills.
7. Add specs for structured work.
8. Add hooks only for deterministic automation.
9. Add MCP only for external systems, with least privilege.
10. Add subagents or `/spawn` only when parallelism has a clear boundary.

## Accuracy guardrails

- Recheck official Kiro documentation when the user asks for the latest behavior or the installed CLI disagrees with this guide.
- Never present classic `kiro-cli chat --no-interactive` as a v3 feature while v3 remains TUI-only.
- Do not treat `tools` as authorization. It controls visibility; `permissions.rules` controls authority.
- Do not treat `autoApprove` as permission. It suppresses a tool prompt only after the tool is visible and authorized.
- In v3 permissions, use glob patterns. Hook matchers remain regular expressions.
- Keep v3 hooks in standalone `.kiro/hooks/*.json` files with schema version `v1` and PascalCase triggers.
- Never place tokens, passwords, cookies, private keys, or OAuth client secrets in committed configuration.
- Do not assume environment substitution works in undocumented fields such as `oauth.clientSecret`.
- Flag destructive commands, broad wildcard permissions, `--trust-all-tools`, and blanket MCP approval as unsafe defaults.
- Preserve and merge existing config; never overwrite an unknown `.kiro` setup wholesale.

## Production and SRE default

For infrastructure, monitoring, incident, database, or production tasks, default to read-only evidence collection:

- allow filesystem reads and narrow diagnostic commands;
- allow only named read-only MCP tools;
- deny filesystem writes, deploys, syncs, restarts, deletes, and mutating API tools;
- keep credentials in private user configuration or environment variables;
- separate investigator, reviewer, and operator roles;
- require a human-controlled apply step for mutations.

Use explicit conclusions for production review: `BLOCK PRODUCTION`, `CONDITIONAL GO`, or `GO`, followed by evidence and required actions.

## Definition of done

A complete answer or generated workspace should:

- say how to launch and verify v3;
- put every file at the correct workspace or user path;
- use Markdown agents and capability permissions;
- include runnable examples without placeholder secrets;
- explain tool visibility, permission, and approval as separate layers;
- include validation and rollback or disable steps;
- mention relevant Early Access limitations;
- link the official pages used when freshness matters.
