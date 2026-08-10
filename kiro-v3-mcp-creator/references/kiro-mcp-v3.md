# Kiro CLI 3.0 MCP configuration

Use this reference for Kiro-specific connection, OAuth, environment, permission, and troubleshooting behavior. The official pages were checked on 2026-08-10.

## Contents

1. Configuration locations and precedence
2. Local stdio servers
3. Remote HTTP servers
4. Environment variables
5. OAuth modes
6. Agent access and tool approval
7. Validation and credential lifecycle
8. Official sources

## Configuration locations and precedence

| Scope | Location | Use |
| --- | --- | --- |
| Workspace | `.kiro/settings/mcp.json` | Project-specific, team-shareable server definitions |
| User | `~/.kiro/settings/mcp.json` | Personal/global servers and confidential local material |
| Agent | `mcpServers` in agent profile | Server override or agent-specific server |

Same-named servers use this precedence: agent profile, workspace MCP JSON, then user MCP JSON. Different names merge. Kiro hot-reloads saved MCP changes and restarts only changed servers at an idle boundary.

## Local stdio servers

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

Local entries require `command`; `args` is optional. They may also use `env`, `disabled`, `autoApprove`, `disabledTools`, and implementation-dependent timeout fields. Use environment credentials for stdio rather than OAuth.

Kiro CLI can also add a local server from the command line:

```bash
kiro-cli mcp add \
  --name incident-data \
  --scope global \
  --command uv \
  --args run \
  --args python \
  --args server.py \
  --env INCIDENT_API_TOKEN='${INCIDENT_API_TOKEN}'
```

Prefer direct JSON merging when preserving a complex existing file; confirm the installed CLI syntax before relying on flags.

## Remote HTTP servers

```json
{
  "mcpServers": {
    "incident-api": {
      "url": "https://mcp.example.com/mcp",
      "headers": {
        "X-Tenant": "${INCIDENT_TENANT}"
      },
      "disabled": false,
      "autoApprove": ["get_incident"],
      "disabledTools": ["delete_incident"]
    }
  }
}
```

Use HTTPS for non-loopback remote endpoints. Static bearer-token headers may use `"Authorization": "Bearer ${API_TOKEN}"`, but OAuth is preferred when acting for a user and the server supports it.

## Environment variables

Reference the Kiro process environment with `${NAME}`:

```json
{
  "env": {
    "API_TOKEN": "${API_TOKEN}",
    "DEBUG": "false",
    "TIMEOUT": "30000"
  }
}
```

Set referenced variables in the shell before starting Kiro:

```bash
export API_TOKEN="<set locally>"
kiro-cli
```

Kiro requires explicit approval before expanding new environment variables for an MCP server. Approve only the named variables required by a reviewed server. The setting is presented as **MCP Approved Env Vars** in Kiro settings. Do not approve broad or unrelated environment access.

Restrict configuration permissions where supported:

```bash
chmod 600 ~/.kiro/settings/mcp.json
chmod 600 .kiro/settings/mcp.json
```

Do not commit literal tokens, passwords, cookies, private keys, or OAuth client secrets.

## OAuth modes

OAuth is supported for remote HTTP MCP servers. Kiro opens the browser flow and manages tokens.

### Dynamic Client Registration

Most compatible servers need only the URL:

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

With no `oauth.clientId`, Kiro attempts DCR and may fall back to default client configuration.

### Pre-registered public client

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

Setting `clientId` skips DCR. Without `clientSecret`, Kiro acts as a public client and uses PKCE. Valid loopback redirect forms include a full `http://localhost:<port>/<path>` URL, `127.0.0.1:<port>`, or `:<port>`. Omit it to allow a random available port when the provider supports dynamic callbacks.

### Confidential client (CLI only)

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

Kiro CLI supports confidential clients when a provider requires a secret. Keep this entry in private user-level configuration, restrict permissions, never commit it, and avoid printing it. Environment expansion is documented for `env` and headers, not guaranteed for `oauth.clientSecret`; do not assume `${VAR}` works in that field.

### Scope precedence and defaults

Scopes may appear at top-level `oauthScopes` or nested `oauth.oauthScopes`. Nested scopes take priority when both exist. When neither is configured, current Kiro documentation says the client requests `openid`, `email`, `profile`, and `offline_access`; explicitly set the provider's minimum scopes when those defaults are inappropriate.

An empty scope array can work around providers that reject scope requests, but use it only after verifying provider requirements.

### Redirect and provider requirements

- Use exact callback URI matching for pre-registered applications.
- Use HTTP only for loopback `localhost` or `127.0.0.1`; use HTTPS elsewhere.
- For an external identity provider, the MCP server must expose protected-resource metadata, point to the authorization server, and validate bearer tokens using issuer/JWKS/audience and scopes.

## Agent access and tool approval

Agent profile example:

```yaml
---
name: incident-reader
description: Read-only incident investigation agent
tools: ["read", "@incident-api"]
includeMcpJson: true
permissions:
  rules:
    - capability: mcp
      match: ["incident-api/get_*", "incident-api/search_*"]
      effect: allow
    - capability: mcp
      match: ["incident-api/delete_*", "incident-api/update_*"]
      effect: deny
---

Use incident evidence without mutating the source system.
```

`tools` controls visibility, `disabledTools` removes tools at the server configuration layer, `autoApprove` skips per-call approval, and `permissions.rules` controls agent authorization. Treat them as separate layers.

Kiro rejects or excludes invalid tool definitions. The complete tool name including prefix must be no more than 64 characters, match `^[a-zA-Z][a-zA-Z0-9_]*$`, and have a non-empty description. Avoid descriptions over 10,000 characters.

## Validation and credential lifecycle

1. Validate JSON and command paths.
2. Confirm referenced environment names are set and approved.
3. Start Kiro and use `/mcp` to inspect servers, status, and tools.
4. Run one safe read-only call, then one invalid-input test.
5. Use MCP logs for diagnosis; redact secrets and user data before sharing.
6. Run `kiro-cli diagnostic` for broader configuration checks.

OAuth commands:

```text
/mcp auth <server>         force a new browser authorization
/mcp cancel-auth <server>  cancel a stuck authorization flow
/mcp logout <server>       remove locally stored credentials
```

## Official sources

- [Kiro MCP overview](https://kiro.dev/docs/mcp/)
- [Kiro MCP configuration and OAuth](https://kiro.dev/docs/mcp/configuration/)
- [Kiro MCP security](https://kiro.dev/docs/mcp/security/)
- [Kiro MCP tools](https://kiro.dev/docs/mcp/usage/)
- [Kiro CLI slash commands](https://kiro.dev/docs/reference/slash-commands/)
- [Kiro CLI settings](https://kiro.dev/docs/cli/reference/settings/)
- [Kiro agent configuration](https://kiro.dev/docs/custom-agents/configuration-reference/)
