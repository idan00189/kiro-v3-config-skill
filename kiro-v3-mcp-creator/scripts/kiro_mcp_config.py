#!/usr/bin/env python3
"""Create, merge, and validate Kiro CLI v3 MCP JSON configuration."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SERVER_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
TOOL_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
PLACEHOLDER = re.compile(r"^(?:Bearer\s+)?\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")
SECRET_NAME = re.compile(r"(api[_-]?key|authorization|cookie|credential|password|private[_-]?key|secret|token)", re.I)
TOKENISH = re.compile(r"^(?:gh[pousr]_|github_pat_|AKIA)[A-Za-z0-9_\-]{8,}|^Bearer\s+\S+", re.I)


@dataclass
class Finding:
    severity: str
    path: str
    message: str


class ConfigError(ValueError):
    pass


def config_path(root: Path, scope: str, explicit: Path | None) -> Path:
    if explicit:
        return explicit.expanduser().resolve()
    if scope == "workspace":
        return (root.resolve() / ".kiro" / "settings" / "mcp.json")
    return Path.home() / ".kiro" / "settings" / "mcp.json"


def load_config(path: Path, allow_missing: bool = False) -> dict[str, Any]:
    if not path.exists():
        if allow_missing:
            return {"mcpServers": {}}
        raise ConfigError(f"Configuration does not exist: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError("Top-level MCP configuration must be an object")
    servers = data.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise ConfigError("mcpServers must be an object")
    return data


def split_assignment(value: str, label: str) -> tuple[str, str]:
    if "=" not in value:
        raise ConfigError(f"{label} must use NAME=VALUE syntax: {value!r}")
    key, item = value.split("=", 1)
    key = key.strip()
    if not key:
        raise ConfigError(f"{label} has an empty name")
    return key, item


def unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def secret_file_value(path: Path) -> str:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise ConfigError(f"Client-secret file does not exist: {path}")
    if os.name != "nt":
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode & 0o077:
            raise ConfigError(f"Client-secret file must not be accessible by group/others (mode is {mode:o})")
    value = path.read_text(encoding="utf-8").strip()
    if not value or "\n" in value or "\r" in value:
        raise ConfigError("Client-secret file must contain exactly one non-empty line")
    return value


def validate_remote_url(value: str) -> None:
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.hostname:
        raise ConfigError(f"Invalid remote URL: {value!r}")
    loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    if parsed.scheme != "https" and not (parsed.scheme == "http" and loopback):
        raise ConfigError("Remote MCP URL must use HTTPS, except HTTP on loopback")
    if parsed.fragment:
        raise ConfigError("Remote MCP URL must not contain a fragment")


def validate_redirect(value: str) -> None:
    if re.fullmatch(r":\d{1,5}", value):
        port = int(value[1:])
        if 1 <= port <= 65535:
            return
    if re.fullmatch(r"(?:127\.0\.0\.1|localhost):\d{1,5}", value):
        port = int(value.rsplit(":", 1)[1])
        if 1 <= port <= 65535:
            return
    parsed = urlparse(value)
    if parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"} and parsed.port:
        return
    raise ConfigError("OAuth redirect must be HTTP loopback URL, host:port, or :port")


def build_entry(args: argparse.Namespace, target: Path) -> tuple[dict[str, Any], list[str]]:
    if not SERVER_NAME.fullmatch(args.name):
        raise ConfigError("Server name must start with a letter and use at most 64 letters, digits, dots, underscores, or hyphens")
    entry: dict[str, Any] = {}
    required_env: list[str] = []
    if args.command:
        entry["command"] = args.command
        if args.arg:
            entry["args"] = args.arg
    else:
        if args.arg:
            raise ConfigError("--arg is valid only with a local --command server")
        validate_remote_url(args.url)
        entry["url"] = args.url

    env: dict[str, str] = {}
    for name in args.env:
        if not ENV_NAME.fullmatch(name):
            raise ConfigError(f"Invalid environment variable name: {name!r}")
        env[name] = "${" + name + "}"
        required_env.append(name)
    for assignment in args.literal_env:
        key, value = split_assignment(assignment, "--literal-env")
        if not ENV_NAME.fullmatch(key):
            raise ConfigError(f"Invalid environment variable name: {key!r}")
        if SECRET_NAME.search(key) or TOKENISH.search(value):
            raise ConfigError(f"Refusing literal secret-like environment value for {key}; use --env {key}")
        env[key] = value
    if env:
        entry["env"] = env

    headers: dict[str, str] = {}
    for assignment in args.header_env:
        header, env_name = split_assignment(assignment, "--header-env")
        if not ENV_NAME.fullmatch(env_name):
            raise ConfigError(f"Invalid environment variable name: {env_name!r}")
        prefix = "Bearer " if header.lower() == "authorization" else ""
        headers[header] = prefix + "${" + env_name + "}"
        required_env.append(env_name)
    for assignment in args.header_literal:
        header, value = split_assignment(assignment, "--header-literal")
        if SECRET_NAME.search(header) or TOKENISH.search(value):
            raise ConfigError(f"Refusing literal secret-like header {header!r}; use --header-env")
        headers[header] = value
    if headers:
        if args.command:
            raise ConfigError("Headers are valid only for remote HTTP servers")
        entry["headers"] = headers

    if args.oauth_mode != "none":
        if args.command:
            raise ConfigError("OAuth is valid only for remote HTTP servers; use environment credentials for stdio")
        oauth: dict[str, Any] = {}
        if args.oauth_mode in {"public", "confidential"}:
            if not args.client_id:
                raise ConfigError(f"--client-id is required for {args.oauth_mode} OAuth")
            oauth["clientId"] = args.client_id
            if args.redirect_uri:
                validate_redirect(args.redirect_uri)
                oauth["redirectUri"] = args.redirect_uri
        elif args.client_id or args.redirect_uri or args.client_secret_file:
            raise ConfigError("DCR must not include client ID, redirect URI, or client secret")
        if args.oauth_mode == "confidential":
            if args.scope != "global" or args.config is not None:
                raise ConfigError("Confidential OAuth may be written only to the default user-level global config")
            if not args.client_secret_file:
                raise ConfigError("--client-secret-file is required for confidential OAuth")
            oauth["clientSecret"] = secret_file_value(args.client_secret_file)
        elif args.client_secret_file:
            raise ConfigError("--client-secret-file is valid only for confidential OAuth")
        if oauth:
            entry["oauth"] = oauth
        if args.oauth_scope:
            entry["oauthScopes"] = unique(args.oauth_scope)
    elif args.client_id or args.redirect_uri or args.client_secret_file or args.oauth_scope:
        raise ConfigError("OAuth fields require --oauth-mode dcr, public, or confidential")

    for tool in args.auto_approve:
        if tool == "*":
            raise ConfigError("Refusing wildcard auto-approval; enumerate reviewed read-only tools")
        if len(tool) > 64 or not TOOL_NAME.fullmatch(tool):
            raise ConfigError(f"Invalid auto-approved tool name: {tool!r}")
    for tool in args.disable_tool:
        if tool != "*" and (len(tool) > 64 or not TOOL_NAME.fullmatch(tool)):
            raise ConfigError(f"Invalid disabled tool name: {tool!r}")
    if args.auto_approve:
        entry["autoApprove"] = unique(args.auto_approve)
    if args.disable_tool:
        entry["disabledTools"] = unique(args.disable_tool)
    entry["disabled"] = bool(args.disabled)
    return entry, unique(required_env)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            result[key] = "<redacted>" if key == "clientSecret" else redact(item)
        return result
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=".mcp.", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if os.name != "nt":
            os.chmod(temp_name, 0o600)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def create_command(args: argparse.Namespace) -> int:
    target = config_path(args.root, args.scope, args.config)
    data = load_config(target, allow_missing=True)
    servers = data["mcpServers"]
    if args.name in servers and not args.replace:
        raise ConfigError(f"Server {args.name!r} already exists; use --replace after reviewing the current entry")
    entry, required_env = build_entry(args, target)
    servers[args.name] = entry
    rendered = json.dumps(redact(data), indent=2, ensure_ascii=False)
    if args.dry_run:
        print(rendered)
        return 0
    atomic_write(target, data)
    print(f"Wrote {target}", file=sys.stderr)
    if required_env:
        print("Required environment names: " + ", ".join(required_env), file=sys.stderr)
    return 0


class Validator:
    def __init__(self, path: Path, check_env: bool):
        self.path = path
        self.check_env = check_env
        self.findings: list[Finding] = []

    def add(self, severity: str, message: str) -> None:
        self.findings.append(Finding(severity, str(self.path), message))

    def error(self, message: str) -> None:
        self.add("error", message)

    def warn(self, message: str) -> None:
        self.add("warning", message)

    def info(self, message: str) -> None:
        self.add("info", message)

    def check_placeholder(self, value: str, location: str) -> None:
        match = PLACEHOLDER.fullmatch(value)
        if match and self.check_env and match.group(1) not in os.environ:
            self.warn(f"{location} references unset environment variable {match.group(1)!r}")

    def check_scopes(self, value: Any, location: str) -> None:
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            self.error(f"{location} must be an array of non-empty strings")

    def check_tools(self, value: Any, location: str) -> None:
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            self.error(f"{location} must be an array of strings")
            return
        if "*" in value:
            self.warn(f"{location} contains wildcard approval/exclusion; review the effective tool set")
        for tool in value:
            if tool != "*" and (len(tool) > 64 or not TOOL_NAME.fullmatch(tool)):
                self.warn(f"{location} contains tool name {tool!r} that may violate Kiro naming constraints")

    def check_oauth(self, server_name: str, server: dict[str, Any], local: bool) -> None:
        oauth = server.get("oauth")
        top_scopes = server.get("oauthScopes")
        if top_scopes is not None:
            self.check_scopes(top_scopes, f"{server_name}.oauthScopes")
        if oauth is None:
            return
        if local:
            self.error(f"{server_name}.oauth is invalid for stdio; use environment credentials")
        if not isinstance(oauth, dict):
            self.error(f"{server_name}.oauth must be an object")
            return
        client_id = oauth.get("clientId")
        client_secret = oauth.get("clientSecret")
        redirect = oauth.get("redirectUri")
        nested_scopes = oauth.get("oauthScopes")
        if client_id is not None and not isinstance(client_id, str):
            self.error(f"{server_name}.oauth.clientId must be a string")
        if client_secret is not None:
            if not isinstance(client_secret, str) or not client_secret:
                self.error(f"{server_name}.oauth.clientSecret must be a non-empty string")
            elif not client_id:
                self.error(f"{server_name}.oauth.clientSecret requires clientId")
            elif PLACEHOLDER.fullmatch(client_secret):
                self.warn(f"{server_name}.oauth.clientSecret uses an environment placeholder; Kiro documents expansion for env/headers, not this field")
            else:
                self.warn(f"{server_name}.oauth.clientSecret is stored in config; keep this file private, mode 600, and uncommitted")
        if redirect is not None:
            if not isinstance(redirect, str):
                self.error(f"{server_name}.oauth.redirectUri must be a string")
            else:
                try:
                    validate_redirect(redirect)
                except ConfigError as exc:
                    self.error(f"{server_name}.oauth.redirectUri: {exc}")
        if nested_scopes is not None:
            self.check_scopes(nested_scopes, f"{server_name}.oauth.oauthScopes")
            if top_scopes is not None:
                self.info(f"{server_name} defines scopes twice; oauth.oauthScopes takes priority")

    def run(self) -> list[Finding]:
        try:
            data = load_config(self.path)
        except ConfigError as exc:
            self.error(str(exc))
            return self.findings
        if os.name != "nt":
            mode = stat.S_IMODE(self.path.stat().st_mode)
            if mode & 0o077:
                self.warn(f"Config mode is {mode:o}; chmod 600 is recommended")
        for server_name, server in data["mcpServers"].items():
            if not SERVER_NAME.fullmatch(server_name):
                self.warn(f"Server name {server_name!r} is not a conservative Kiro-compatible identifier")
            if not isinstance(server, dict):
                self.error(f"Server {server_name!r} must be an object")
                continue
            has_command = isinstance(server.get("command"), str) and bool(server["command"])
            has_url = isinstance(server.get("url"), str) and bool(server["url"])
            if has_command == has_url:
                self.error(f"{server_name} must define exactly one of command or url")
                continue
            local = has_command
            if "args" in server and not (isinstance(server["args"], list) and all(isinstance(item, str) for item in server["args"])):
                self.error(f"{server_name}.args must be an array of strings")
            if has_url:
                try:
                    validate_remote_url(server["url"])
                except ConfigError as exc:
                    self.error(f"{server_name}.url: {exc}")
            env = server.get("env", {})
            if not isinstance(env, dict):
                self.error(f"{server_name}.env must be an object")
            else:
                for key, value in env.items():
                    if not ENV_NAME.fullmatch(key) or not isinstance(value, str):
                        self.error(f"{server_name}.env must map valid names to strings")
                        continue
                    if SECRET_NAME.search(key) and not PLACEHOLDER.fullmatch(value):
                        self.warn(f"{server_name}.env.{key} may contain a literal secret; use ${{{key}}}")
                    self.check_placeholder(value, f"{server_name}.env.{key}")
            headers = server.get("headers", {})
            if headers and local:
                self.error(f"{server_name}.headers is valid only for remote HTTP servers")
            if not isinstance(headers, dict):
                self.error(f"{server_name}.headers must be an object")
            else:
                for key, value in headers.items():
                    if not isinstance(key, str) or not isinstance(value, str):
                        self.error(f"{server_name}.headers must map strings to strings")
                        continue
                    if SECRET_NAME.search(key) and not PLACEHOLDER.fullmatch(value):
                        self.warn(f"{server_name}.headers.{key} may contain a literal credential")
                    self.check_placeholder(value, f"{server_name}.headers.{key}")
            self.check_oauth(server_name, server, local)
            if "autoApprove" in server:
                self.check_tools(server["autoApprove"], f"{server_name}.autoApprove")
            if "disabledTools" in server:
                self.check_tools(server["disabledTools"], f"{server_name}.disabledTools")
            if "disabled" in server and not isinstance(server["disabled"], bool):
                self.error(f"{server_name}.disabled must be boolean")
        if not self.findings:
            self.info("No common Kiro CLI v3 MCP configuration issues found")
        return self.findings


def validate_command(args: argparse.Namespace) -> int:
    target = config_path(args.root, args.scope, args.config)
    findings = Validator(target, args.check_env).run()
    counts = {kind: sum(item.severity == kind for item in findings) for kind in ("error", "warning", "info")}
    if args.json:
        print(json.dumps({"path": str(target), "counts": counts, "findings": [asdict(item) for item in findings]}, indent=2))
    else:
        for item in findings:
            print(f"{item.severity.upper():7} {item.message}")
        print(f"Summary: {counts['error']} error(s), {counts['warning']} warning(s), {counts['info']} info")
    if counts["error"]:
        return 1
    if args.strict and counts["warning"]:
        return 2
    return 0


def add_location_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Workspace root")
    parser.add_argument("--scope", choices=("workspace", "global"), default="workspace")
    parser.add_argument("--config", type=Path, help="Explicit mcp.json path (overrides root/scope)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="operation", required=True)

    create = subparsers.add_parser("create", help="Create or merge one MCP server entry")
    add_location_args(create)
    create.add_argument("--name", required=True)
    transport = create.add_mutually_exclusive_group(required=True)
    transport.add_argument("--command", help="Local stdio executable")
    transport.add_argument("--url", help="Remote Streamable HTTP endpoint")
    create.add_argument("--arg", action="append", default=[], help="Repeat for each local command argument")
    create.add_argument("--env", action="append", default=[], help="Repeat for each environment placeholder name")
    create.add_argument("--literal-env", action="append", default=[], metavar="NAME=VALUE")
    create.add_argument("--header-env", action="append", default=[], metavar="HEADER=ENV_NAME")
    create.add_argument("--header-literal", action="append", default=[], metavar="HEADER=VALUE")
    create.add_argument("--oauth-mode", choices=("none", "dcr", "public", "confidential"), default="none")
    create.add_argument("--client-id")
    create.add_argument("--client-secret-file", type=Path, help="Permission-restricted one-line file; confidential mode only")
    create.add_argument("--redirect-uri")
    create.add_argument("--oauth-scope", action="append", default=[])
    create.add_argument("--auto-approve", action="append", default=[])
    create.add_argument("--disable-tool", action="append", default=[])
    create.add_argument("--disabled", action="store_true")
    create.add_argument("--replace", action="store_true")
    create.add_argument("--dry-run", action="store_true")
    create.set_defaults(handler=create_command)

    validate = subparsers.add_parser("validate", help="Validate MCP configuration")
    add_location_args(validate)
    validate.add_argument("--check-env", action="store_true")
    validate.add_argument("--strict", action="store_true")
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(handler=validate_command)
    return parser.parse_args()


def main() -> int:
    try:
        args = parse_args()
        return args.handler(args)
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
