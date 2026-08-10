# MCP server creation and authorization

Use this reference when implementing or modifying an MCP server, not merely connecting an existing server to Kiro.

## Contents

1. SDK selection
2. Capability design
3. Transport behavior
4. HTTP OAuth requirements
5. Token and upstream API boundaries
6. Test matrix
7. Official sources

## SDK selection

Use an official Model Context Protocol SDK and verify its current stable release before generating code.

- Python: official `modelcontextprotocol/python-sdk`; stable v1 has used the `mcp` package and `FastMCP`.
- TypeScript: official `modelcontextprotocol/typescript-sdk`. As checked on 2026-08-10, its main branch described v2 as pre-alpha and recommended v1.x for production until v2 stabilizes. Do not copy main-branch v2 examples into a v1 project.
- Go: official `modelcontextprotocol/go-sdk`.

Pin an appropriate stable major version. Keep server business logic independent of the transport so stdio and HTTP can be tested separately.

## Capability design

MCP servers may expose tools, resources, and prompts.

- Tools perform bounded actions. Define strict input schemas and useful descriptions.
- Resources expose addressable, read-oriented content.
- Prompts provide reusable parameterized workflows.

For tools:

1. Use short stable identifiers.
2. Validate every field at the boundary.
3. Return structured, actionable errors without secrets or stack traces.
4. Mark and document read-only versus mutating behavior.
5. Add timeouts, cancellation, pagination, and bounded result sizes where relevant.
6. Add idempotency and dry-run support to mutations.
7. Treat tool arguments and upstream output as untrusted.

## Transport behavior

### stdio

- Read and write only MCP JSON-RPC on stdin/stdout.
- Never log to stdout; write diagnostics to stderr.
- Receive credentials from the process environment or OS-native credential source.
- Shut down cleanly when the client closes the stream.

### Streamable HTTP

- Use the official SDK transport.
- Serve non-loopback deployments over HTTPS.
- Validate `Origin` and host routing where required by the SDK/deployment.
- Bound request size, concurrency, duration, and response size.
- Authenticate before running tools or returning protected data.
- Avoid trusting session IDs as authorization.

## HTTP OAuth requirements

The MCP 2025-11-25 authorization specification applies to HTTP transports. A protected MCP server acts as an OAuth resource server.

Implement:

1. OAuth Protected Resource Metadata (RFC 9728), including `authorization_servers`.
2. Discovery through `WWW-Authenticate` on 401 and/or the well-known protected-resource URI.
3. Authorization Server Metadata (RFC 8414) or OpenID Connect discovery.
4. OAuth 2.1 authorization code flow with PKCE support for public clients.
5. Exact redirect URI validation.
6. Resource indicators/audience binding for the canonical MCP server URI.
7. Bearer-token validation for issuer, signature, expiration, audience/resource, and required scopes.
8. Correct errors: 401 for missing/invalid/expired token, 403 for insufficient scope.
9. Short-lived tokens and secure refresh-token behavior appropriate to the client type.

Client registration may use pre-registration, Client ID Metadata Documents, or DCR depending on provider/client support. Kiro can use DCR or pre-registered clients.

## Token and upstream API boundaries

- Never accept a token issued for a different audience.
- Never forward the inbound MCP bearer token to an upstream API.
- When calling an upstream API, obtain a separate upstream token issued for that API.
- Never put access tokens in query strings, logs, tool results, exceptions, or telemetry.
- Keep authorization decisions server-side; tool descriptions are not security controls.
- Redact secrets and personal data from MCP logs.

## Test matrix

| Area | Required tests |
| --- | --- |
| Protocol | initialize, list capabilities, valid call, invalid method/input, cancellation, shutdown |
| stdio | stdout purity, stderr logging, missing env, process exit |
| HTTP | HTTPS/routing, malformed request, request limits, concurrency, timeout |
| OAuth discovery | protected-resource metadata, auth-server metadata, issuer/JWKS |
| Tokens | missing, malformed, expired, wrong issuer, wrong audience, insufficient scope |
| OAuth flow | PKCE, state, exact redirect, refresh, revocation/logout |
| Tools | least privilege, dry-run, idempotency, upstream failure, output bounds |

## Official sources

- [MCP specification](https://modelcontextprotocol.io/specification/2025-11-25)
- [MCP authorization](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization)
- [Build an MCP server](https://modelcontextprotocol.io/docs/develop/build-server)
- [Official Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Official TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk)
- [Official Go SDK](https://github.com/modelcontextprotocol/go-sdk)
