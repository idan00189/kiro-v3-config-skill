#!/usr/bin/env python3
"""Validate common Kiro CLI 3.0 configuration files without external deps."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


VALID_EFFECTS = {"allow", "ask", "deny"}
VALID_CAPABILITIES = {
    "all", "builtin", "context", "diagnostics", "filesystem", "fs_read",
    "fs_write", "mcp", "power", "sandbox_network", "shell", "skill",
    "subagent", "web_fetch", "web_search",
}
VALID_TOOL_TAGS = {
    "*", "@builtin", "@mcp", "knowledge", "read", "shell", "subagent",
    "todo_list", "web", "write",
}
LEGACY_TOOL_IDS = {
    "execute_bash", "fs_read", "fs_write", "fileSearch", "glob", "grep",
    "grepSearch", "listDirectory", "readFile", "webFetch", "webSearch",
    "writeFile",
}
LEGACY_POLICY_TOOL_SETTINGS = {
    "execute_bash", "fs_read", "fs_write", "read", "shell", "write",
}
VALID_HOOK_TRIGGERS = {
    "Manual", "PostFileCreate", "PostFileDelete", "PostFileSave", "PostTaskExec",
    "PostToolUse", "PreTaskExec", "PreToolUse", "SessionStart", "Stop",
    "UserPromptSubmit",
}
LEGACY_HOOK_TRIGGERS = {
    "agentSpawn", "agentStop", "fileCreated", "fileDeleted", "fileEdited",
    "postTaskExecution", "postToolUse", "preTaskExecution", "preToolUse",
    "promptSubmit", "stop", "userPromptSubmit", "userTriggered",
}
SECRET_KEY = re.compile(r"(api[_-]?key|authorization|cookie|credential|password|private[_-]?key|secret|token)", re.I)
ENV_PLACEHOLDER = re.compile(r"^(?:Bearer\s+)?\$\{[A-Za-z_][A-Za-z0-9_]*\}$")
FRONTMATTER_LINE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):(?:\s*(.*))?$")


@dataclass
class Finding:
    severity: str
    path: str
    message: str


class Validator:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.findings: list[Finding] = []

    def add(self, severity: str, path: Path | str, message: str) -> None:
        try:
            rendered = str(Path(path).resolve().relative_to(self.root))
        except (ValueError, TypeError):
            rendered = str(path)
        self.findings.append(Finding(severity, rendered, message))

    def error(self, path: Path | str, message: str) -> None:
        self.add("error", path, message)

    def warn(self, path: Path | str, message: str) -> None:
        self.add("warning", path, message)

    def info(self, path: Path | str, message: str) -> None:
        self.add("info", path, message)

    def load_json(self, path: Path) -> Any | None:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            self.error(path, f"Invalid JSON: {exc}")
            return None

    def simple_frontmatter(self, path: Path) -> tuple[dict[str, Any], str] | None:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            self.error(path, f"Cannot read file: {exc}")
            return None
        lines = text.splitlines()
        if not lines or lines[0].strip() != "---":
            self.error(path, "Missing opening YAML frontmatter delimiter")
            return None
        try:
            end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
        except StopIteration:
            self.error(path, "Missing closing YAML frontmatter delimiter")
            return None
        raw = "\n".join(lines[1:end])
        parsed: dict[str, Any] = {}
        try:
            import yaml  # type: ignore
            value = yaml.safe_load(raw)
            if not isinstance(value, dict):
                raise ValueError("frontmatter must be a mapping")
            parsed = value
        except ImportError:
            for line in lines[1:end]:
                match = FRONTMATTER_LINE.match(line)
                if match and not line.startswith((" ", "\t")):
                    parsed[match.group(1)] = (match.group(2) or "").strip().strip("\"'")
            self.info(path, "PyYAML is unavailable; nested YAML received limited validation")
        except Exception as exc:
            self.error(path, f"Invalid YAML frontmatter: {exc}")
        return parsed, "\n".join(lines[end + 1 :])

    def validate_permission_rules(self, rules: Any, path: Path | str) -> None:
        if not isinstance(rules, list):
            self.error(path, "permissions.rules must be an array")
            return
        for index, rule in enumerate(rules):
            label = f"permissions.rules[{index}]"
            if not isinstance(rule, dict):
                self.error(path, f"{label} must be an object")
                continue
            capability = rule.get("capability")
            effect = rule.get("effect")
            if capability not in VALID_CAPABILITIES:
                self.warn(path, f"{label} has unknown capability {capability!r}")
            if effect not in VALID_EFFECTS:
                self.error(path, f"{label} effect must be allow, ask, or deny")
            for key in ("match", "exclude"):
                patterns = rule.get(key)
                if patterns is not None and not (
                    isinstance(patterns, list) and all(isinstance(item, str) for item in patterns)
                ):
                    self.error(path, f"{label}.{key} must be an array of strings")
                for pattern in patterns or []:
                    if pattern.startswith("^") or pattern.endswith("$") or ".*" in pattern:
                        self.warn(path, f"{label}.{key} contains regex-like pattern {pattern!r}; v3 permissions use glob")
            if capability == "all" and effect == "allow" and not rule.get("match"):
                self.warn(path, f"{label} grants unrestricted capability: all")

    def validate_tools_settings(self, settings: Any, path: Path) -> None:
        if not isinstance(settings, dict):
            self.error(path, "toolsSettings must be an object")
            return
        for key in settings:
            if key in LEGACY_POLICY_TOOL_SETTINGS:
                self.warn(
                    path,
                    f"toolsSettings.{key} is legacy for shell/filesystem authority; "
                    "migrate it to permissions.rules",
                )
        subagent = settings.get("subagent")
        if subagent is None:
            return
        if not isinstance(subagent, dict):
            self.error(path, "toolsSettings.subagent must be an object")
            return
        for field in ("availableAgents", "trustedAgents"):
            patterns = subagent.get(field)
            if patterns is not None and not (
                isinstance(patterns, list) and all(isinstance(item, str) for item in patterns)
            ):
                self.error(path, f"toolsSettings.subagent.{field} must be an array of strings")

    def validate_mcp_servers(self, servers: Any, path: Path, source: str = "mcpServers") -> None:
        if not isinstance(servers, dict):
            self.error(path, f"{source} must be an object")
            return
        for name, server in servers.items():
            label = f"{source}.{name}"
            if not isinstance(name, str) or not name:
                self.error(path, f"{source} contains an empty or non-string server name")
                continue
            if not isinstance(server, dict):
                self.error(path, f"MCP server {name!r} must be an object")
                continue
            has_command = isinstance(server.get("command"), str) and bool(server["command"])
            has_url = isinstance(server.get("url"), str) and bool(server["url"])
            if has_command == has_url:
                self.error(path, f"MCP server {name!r} must define exactly one of command or url")
            args = server.get("args")
            if args is not None and not (
                isinstance(args, list) and all(isinstance(item, str) for item in args)
            ):
                self.error(path, f"{label}.args must be an array of strings")
            for mapping_name in ("env", "headers"):
                mapping = server.get(mapping_name)
                if mapping is not None and not (
                    isinstance(mapping, dict)
                    and all(isinstance(key, str) and isinstance(value, str) for key, value in mapping.items())
                ):
                    self.error(path, f"{label}.{mapping_name} must map strings to strings")
            if "disabled" in server and not isinstance(server["disabled"], bool):
                self.error(path, f"{label}.disabled must be true or false")
            for list_name in ("autoApprove", "disabledTools"):
                tools = server.get(list_name)
                if tools is not None and not (
                    isinstance(tools, list) and all(isinstance(item, str) for item in tools)
                ):
                    self.error(path, f"{label}.{list_name} must be an array of strings")
            if server.get("autoApprove") == ["*"]:
                self.warn(path, f"MCP server {name!r} auto-approves every tool")

    def validate_agent_data(self, data: dict[str, Any], path: Path) -> None:
        if "toolsSettings" in data:
            self.validate_tools_settings(data["toolsSettings"], path)
        tools = data.get("tools")
        if tools is not None:
            if not isinstance(tools, list) or not all(isinstance(item, str) for item in tools):
                self.error(path, "tools must be an array of strings")
            else:
                for tool in tools:
                    if tool in LEGACY_TOOL_IDS:
                        self.warn(path, f"Legacy tool ID {tool!r}; prefer a v3 category tag")
                    elif tool not in VALID_TOOL_TAGS and not tool.startswith("@"):
                        self.info(path, f"Tool {tool!r} is not a standard v3 tag; verify it exists")
        permissions = data.get("permissions")
        if permissions is not None:
            if not isinstance(permissions, dict):
                self.error(path, "permissions must be an object")
            else:
                self.validate_permission_rules(permissions.get("rules"), path)
        inline_mcp = data.get("mcpServers")
        if inline_mcp is not None:
            self.validate_mcp_servers(inline_mcp, path, "mcpServers")
        if "hooks" in data:
            self.warn(path, "Embedded hooks are a legacy format; move them to .kiro/hooks/*.json")
        if data.get("includeMcpJson") is True and not (self.root / ".kiro/settings/mcp.json").exists():
            self.info(path, "includeMcpJson is enabled but no workspace MCP file exists; a global MCP file may still provide servers")
        if data.get("includeMcpJson") is False and isinstance(tools, list):
            inline_names = set(inline_mcp) if isinstance(inline_mcp, dict) else set()
            for tool in tools:
                if tool == "@mcp" and not inline_names:
                    self.warn(path, "@mcp is visible but includeMcpJson is false and no inline MCP servers are defined")
                elif isinstance(tool, str) and tool.startswith("@") and tool not in {"@builtin", "@mcp"}:
                    server_name = tool[1:].split("/", 1)[0]
                    if server_name not in inline_names:
                        self.warn(
                            path,
                            f"Tool {tool!r} references MCP server {server_name!r}, but includeMcpJson is false "
                            "and that server is not defined in the agent",
                        )
        self.check_literals(data, path)

    def validate_agents(self) -> None:
        directory = self.root / ".kiro/agents"
        if not directory.exists():
            return
        for path in sorted(directory.glob("*")):
            if path.suffix == ".json":
                data = self.load_json(path)
                if isinstance(data, dict):
                    self.validate_agent_data(data, path)
            elif path.suffix == ".md":
                result = self.simple_frontmatter(path)
                if not result:
                    continue
                data, body = result
                name = data.get("name")
                if name and name != path.stem:
                    self.warn(path, f"Agent name {name!r} does not match filename {path.stem!r}")
                if not data.get("description"):
                    self.warn(path, "Agent description is missing")
                if not body.strip():
                    self.warn(path, "Markdown agent has an empty system-prompt body")
                self.validate_agent_data(data, path)

    def validate_hooks(self) -> None:
        directory = self.root / ".kiro/hooks"
        if not directory.exists():
            return
        for path in sorted(directory.glob("*.json")):
            data = self.load_json(path)
            if not isinstance(data, dict):
                continue
            if data.get("version") != "v1":
                self.error(path, 'Hook file version must be "v1"')
            hooks = data.get("hooks")
            if not isinstance(hooks, list):
                self.error(path, "hooks must be an array")
                continue
            for index, hook in enumerate(hooks):
                label = f"hooks[{index}]"
                if not isinstance(hook, dict):
                    self.error(path, f"{label} must be an object")
                    continue
                if not isinstance(hook.get("name"), str) or not hook["name"].strip():
                    self.error(path, f"{label}.name is required")
                trigger = hook.get("trigger")
                if trigger in LEGACY_HOOK_TRIGGERS:
                    self.error(path, f"{label} uses legacy trigger {trigger!r}; use PascalCase v3 trigger")
                elif trigger not in VALID_HOOK_TRIGGERS:
                    self.error(path, f"{label} has unknown trigger {trigger!r}")
                action = hook.get("action")
                if not isinstance(action, dict) or action.get("type") not in {"command", "agent"}:
                    self.error(path, f"{label}.action.type must be command or agent")
                elif action["type"] == "command" and not isinstance(action.get("command"), str):
                    self.error(path, f"{label}.action.command is required")
                elif action["type"] == "agent" and not isinstance(action.get("prompt"), str):
                    self.error(path, f"{label}.action.prompt is required")
                if action and action.get("type") == "command" and hook.get("enabled", True):
                    self.info(path, f"{label} is an enabled automatic command hook; review its side effects")

    def check_literals(self, value: Any, path: Path, prefix: str = "") -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                name = f"{prefix}.{key}" if prefix else str(key)
                if SECRET_KEY.search(str(key)) and isinstance(item, str) and item and not ENV_PLACEHOLDER.match(item):
                    self.warn(path, f"Possible literal secret in {name}; use a ${{VAR}} placeholder")
                self.check_literals(item, path, name)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                self.check_literals(item, path, f"{prefix}[{index}]")

    def validate_mcp(self) -> None:
        path = self.root / ".kiro/settings/mcp.json"
        if not path.exists():
            return
        data = self.load_json(path)
        if not isinstance(data, dict):
            return
        self.validate_mcp_servers(data.get("mcpServers"), path)
        self.check_literals(data, path)

    def validate_skills(self) -> None:
        directory = self.root / ".kiro/skills"
        if not directory.exists():
            return
        for path in sorted(directory.glob("*/SKILL.md")):
            result = self.simple_frontmatter(path)
            if not result:
                continue
            data, _ = result
            name = data.get("name")
            if name != path.parent.name:
                self.error(path, f"Skill name {name!r} must match folder {path.parent.name!r}")
            if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9-]{1,64}", name):
                self.error(path, "Skill name must be 1-64 lowercase letters, digits, or hyphens")
            if not data.get("description"):
                self.error(path, "Skill description is required")

    def validate_permissions_file(self, path: Path) -> None:
        try:
            import yaml  # type: ignore
        except ImportError:
            self.warn(path, "PyYAML is required for full permissions.yaml validation")
            text = path.read_text(encoding="utf-8")
            if re.search(r"capability:\s*all\s+effect:\s*allow", text, re.S):
                self.warn(path, "Permission file appears to grant unrestricted capability: all")
            return
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.error(path, f"Invalid permissions YAML: {exc}")
            return
        if not isinstance(data, dict):
            self.error(path, "Permission file must be a mapping")
            return
        self.validate_permission_rules(data.get("rules"), path)

    def run(self, permission_paths: list[Path]) -> list[Finding]:
        local_permissions = self.root / ".kiro/settings/permissions.yaml"
        if local_permissions.exists():
            self.error(local_permissions, "Repository-local permissions.yaml is not a valid v3 workspace policy location")
        self.validate_agents()
        self.validate_hooks()
        self.validate_mcp()
        self.validate_skills()
        for path in permission_paths:
            if not path.exists():
                self.error(path, "Permission file does not exist")
            else:
                self.validate_permissions_file(path)
        if not any(item.severity in {"error", "warning"} for item in self.findings):
            self.info(self.root, "No common Kiro CLI v3 configuration issues found")
        return self.findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Workspace root")
    parser.add_argument("--permissions", type=Path, action="append", default=[], help="External permissions.yaml to validate")
    parser.add_argument("--strict", action="store_true", help="Return nonzero when warnings exist")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    validator = Validator(args.root)
    findings = validator.run([path.resolve() for path in args.permissions])
    counts = {severity: sum(item.severity == severity for item in findings) for severity in ("error", "warning", "info")}
    if args.json:
        print(json.dumps({"root": str(validator.root), "counts": counts, "findings": [asdict(item) for item in findings]}, indent=2))
    else:
        for item in findings:
            print(f"{item.severity.upper():7} {item.path}: {item.message}")
        print(f"Summary: {counts['error']} error(s), {counts['warning']} warning(s), {counts['info']} info")
    if counts["error"]:
        return 1
    if args.strict and counts["warning"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
