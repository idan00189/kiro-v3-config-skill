---
name: kiro-v3-mcp-creator
description: Create, configure, secure, test, or troubleshoot Model Context Protocol servers for Kiro CLI 3.0, including new MCP server implementation, stdio and Streamable HTTP transports, `.kiro/settings/mcp.json`, global MCP configuration, OAuth 2.1/DCR/PKCE, confidential clients, environment-variable approval, agent MCP permissions, tool approval, and credential lifecycle. Use for Kiro v3 MCP creation, OAuth callbacks or scopes, client IDs or secrets, environment setup, MCP connection/auth failures, or migrating an MCP integration into Kiro CLI.
---

# Kiro CLI v3 MCP creator

Create the smallest secure MCP integration that satisfies the user's use case. Separate server implementation, Kiro connection configuration, authentication, and agent authorization so each boundary can be tested independently.

## Discover before editing

1. Inspect applicable `AGENTS.md`, the project stack, existing MCP server code, `.kiro/settings/mcp.json`, `~/.kiro/settings/mcp.json` when accessible, and relevant agent profiles.
2. Determine whether the task is to:
   - Configure an existing local stdio server.
   - Configure an existing remote Streamable HTTP server.
   - Add OAuth or environment configuration.
   - Create a new MCP server and connect it to Kiro.
   - Diagnose an existing failure.
3. Resolve only material unknowns: server purpose, transport, workspace/global scope, identity provider, OAuth client type, required scopes, environment names, and read/write tool authority.
4. Read [references/kiro-mcp-v3.md](references/kiro-mcp-v3.md) for every task. Also read [references/mcp-server-build.md](references/mcp-server-build.md) before creating or changing server code.
5. Re-check the linked official documentation when the user requests the latest behavior, the installed Kiro version disagrees, or SDK APIs may have changed.

## Choose transport and authentication

| Situation | Transport | Authentication |
| --- | --- | --- |
| Local process launched by Kiro | stdio | Environment variables or local OS credentials |
| Remote service for a user | Streamable HTTP | MCP OAuth 2.1 flow, preferably DCR/public PKCE |
| Remote service with a pre-registered public app | Streamable HTTP | `oauth.clientId`, loopback redirect, least-privilege scopes |
| Provider requiring confidential client | Streamable HTTP, CLI only | `oauth.clientId` + private `oauth.clientSecret` in user-level config |
| Static API token supported by server | stdio env or remote header | `${VAR}` reference; never a committed literal |

Do not configure OAuth for stdio. The MCP authorization specification reserves OAuth for HTTP transports; stdio servers obtain credentials from their environment.

## Create an MCP server

1. Select an official MCP SDK and a stable release compatible with the repository. Prefer the repository's existing language; do not introduce a second runtime without a concrete reason.
2. Define tools, resources, and prompts from explicit user workflows. Give each tool a narrow responsibility, a non-empty description, a bounded input schema, structured errors, and predictable output.
3. Keep Kiro tool-name constraints in mind: the complete prefixed name must be at most 64 characters and match Kiro's allowed identifier pattern.
4. Make read versus write behavior obvious. Design write tools with idempotency keys, dry-run support, precondition checks, and explicit target identifiers where applicable.
5. For stdio, never log to stdout; send logs to stderr. For HTTP, implement Streamable HTTP and production HTTP controls appropriate to the deployment.
6. Validate server initialization, capability listing, one valid call, invalid input, upstream failure, timeout, cancellation, and clean shutdown.
7. For protected HTTP servers, follow the authorization and token-validation requirements in the server-build reference. Never forward the inbound MCP bearer token to an upstream API.

## Configure Kiro

Prefer the bundled deterministic tool for creating or merging a server entry:

```bash
python3 <skill-dir>/scripts/kiro_mcp_config.py create --help
```

Examples:

```bash
# Local stdio server with approved environment references
python3 <skill-dir>/scripts/kiro_mcp_config.py create \
  --root . --scope workspace --name my-server \
  --command uv --arg run --arg python --arg server.py \
  --env API_TOKEN --disable-tool delete_record

# Remote server using Dynamic Client Registration
python3 <skill-dir>/scripts/kiro_mcp_config.py create \
  --root . --scope workspace --name remote-server \
  --url https://mcp.example.com/mcp --oauth-mode dcr \
  --oauth-scope records:read

# Pre-registered public client using PKCE
python3 <skill-dir>/scripts/kiro_mcp_config.py create \
  --root . --scope workspace --name remote-server \
  --url https://mcp.example.com/mcp --oauth-mode public \
  --client-id my-public-client \
  --redirect-uri http://127.0.0.1:7778/oauth/callback \
  --oauth-scope records:read
```

Preserve existing servers. Require an explicit replacement when the same server name exists. Use workspace scope for project-specific integrations and user scope for personal/global integrations or confidential OAuth material.

## Configure environment variables

1. Put only `${VARIABLE_NAME}` references in shared Kiro configuration for credentials.
2. Tell the user which variable names must be set, never their values. Do not ask them to paste secrets into chat.
3. Set secrets in the shell, CI secret store, OS keychain, or approved enterprise secret manager before starting Kiro.
4. Account for Kiro's environment approval control: new environment references must be explicitly approved in Kiro's MCP approved-environment-variable setting.
5. Keep non-secret literals such as `DEBUG=false` or timeouts separate from secrets.
6. Restrict `mcp.json` permissions to the user when it can contain confidential client credentials.

## Configure OAuth

1. Prefer DCR when the server and authorization server support it; omit `clientId` and let Kiro initiate browser authorization.
2. For a public pre-registered client, configure `oauth.clientId`, an exact loopback `redirectUri` when required, and minimum scopes. Kiro performs PKCE.
3. For a confidential client, use CLI only. Never receive the secret in chat or command-line arguments. Read it from a local permission-restricted file and write it only to private user-level config. Prefer redesigning to DCR/public PKCE when possible.
4. Use HTTPS for remote MCP and authorization endpoints. Loopback OAuth callbacks may use HTTP only on `127.0.0.1` or `localhost`; the registered callback must match exactly.
5. Place scopes at top-level `oauthScopes` unless provider behavior requires nested `oauth.oauthScopes`; nested scopes take priority when both exist.
6. Validate discovery, protected-resource metadata, authorization-server metadata, issuer/JWKS, audience, PKCE support, scopes, refresh behavior, 401/403 handling, and logout.
7. Use `/mcp auth <server>`, `/mcp cancel-auth <server>`, and `/mcp logout <server>` for credential lifecycle troubleshooting.

## Control agent authority

- Include only verified servers/tools in agent `tools`, such as `@server` or `@server/tool`.
- Use `includeMcpJson: true` only when the agent should inherit workspace/global MCP servers.
- Add v3 `permissions.rules` for capability `mcp` with explicit `server/tool` glob patterns.
- Keep write/destructive tools out of `autoApprove`; default to interactive approval.
- Use `disabledTools` for delete, deploy, merge, execute, mutate, or administrative tools the agent does not need.
- Do not infer safety from a tool name. Inspect implementation and parameters.

## Validate and hand off

Run deterministic validation:

```bash
python3 <skill-dir>/scripts/kiro_mcp_config.py validate \
  --root . --scope workspace --check-env --strict
```

Then run the available runtime checks:

```bash
kiro-cli diagnostic
kiro-cli
```

Inside Kiro, use `/mcp` to inspect connection status and exposed tools. Review MCP logs without sharing them until secrets, file paths, and conversation data are removed.

Report the server/config files changed, transport, scope, required variable names, OAuth client type and callback, requested scopes, exposed/disabled/auto-approved tools, validation results, and any unverified runtime boundary. Never claim success solely because JSON parses; require a live initialization and at least one safe tool call when the environment permits it.
