"""Safety checks for shell commands and file paths (principle 3).

Verdicts
  ALLOW          read-only / test commands
  NEEDS_APPROVAL file deletion, permission change, installs, network, git writes, unknown commands
  DENY           destructive or remote-code patterns that are never run automatically
"""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path

ALLOW, NEEDS_APPROVAL, DENY = "allow", "needs_approval", "deny"
_RANK = {ALLOW: 0, NEEDS_APPROVAL: 1, DENY: 2}


@dataclass
class Verdict:
    level: str = ALLOW
    reasons: list = field(default_factory=list)

    def escalate(self, level: str, reason: str):
        if _RANK[level] > _RANK[self.level]:
            self.level = level
        self.reasons.append(reason)

    @property
    def allowed(self) -> bool:
        return self.level == ALLOW


READ_ONLY = {
    "ls", "cat", "head", "tail", "wc", "grep", "rg", "pwd", "echo", "date", "whoami", "uname",
    "stat", "file", "diff", "sort", "uniq", "cut", "tr", "basename", "dirname", "true", "df", "du",
}
GIT_READ = {"status", "log", "diff", "show", "branch", "rev-parse", "ls-files", "blame"}
DELETE_OR_PERM = {"rm", "rmdir", "unlink", "shred", "truncate", "chmod", "chown", "chgrp", "mv", "cp",
                  "ln", "tee", "touch", "mkdir"}
ALWAYS_DENY = {"mkfs", "dd", "fdisk", "parted", "shutdown", "reboot", "halt", "poweroff", "init",
               "iptables", "nft", "ufw", "passwd", "userdel", "usermod", "visudo", "crontab", "mount",
               "umount", "su", "sudo", "doas", "nc", "ncat", "netcat", "telnet"}
NETWORK = {"curl", "wget", "ssh", "scp", "sftp", "rsync", "ftp", "pip", "pip3", "npm", "apt", "apt-get",
           "yum", "dnf", "brew", "docker", "kubectl", "ansible", "ansible-playbook", "terraform"}
NETWORK_DEVICE_PATTERNS = re.compile(
    r"(?i)\b(?:write\s+erase|erase\s+startup|reload|format\s+(?:flash|bootflash)|"
    r"reset\s+saved-configuration|delete\s+flash|factory-reset|undo\s+\w+\s+\w+)\b")
DENY_PATTERNS = [
    (re.compile(r":\(\)\s*\{.*\};\s*:"), "fork bomb"),
    (re.compile(r"(?:curl|wget)[^|;&]*\|\s*(?:sudo\s+)?(?:ba|z|da)?sh\b"), "remote script piped to shell"),
    (re.compile(r"(?i)\bdrop\s+(?:table|database)\b|\bdelete\s+from\s+\w+\s*(?:;|$)"), "destructive SQL"),
    (re.compile(r"(?:>|>>)\s*/(?:etc|boot|dev/sd|dev/nvme|usr|bin|sbin|lib)"), "write to system path"),
    (re.compile(r"\brm\s+(?:-[a-zA-Z]*\s+)*(?:/|~|\*|\$HOME)(?:\s|$)"), "recursive delete of root/home"),
    (re.compile(r"git\s+push\b[^;&|]*(?:--force|-f\b)"), "force push"),
]
APPROVAL_PATTERNS = [
    (re.compile(r"[`]|\$\("), "command substitution"),
    (re.compile(r"(?:^|[^&])&(?!&)\s*$"), "background process"),
    (re.compile(r"git\s+(?:push|reset|clean|checkout|rebase|merge|commit|rm)\b"), "git write operation"),
    (re.compile(r"\s>>?\s*\S"), "file redirection"),
]
_SPLIT = re.compile(r"\|\||&&|;|\||\n")

SENSITIVE_FILES = re.compile(
    r"(?i)(?:^|/)(?:\.env(?:\..*)?|id_(?:rsa|ed25519|ecdsa)(?:\.pub)?|.*\.pem|.*\.key|credentials(?:\.json)?|"
    r"\.netrc|\.pgpass|\.git/config|known_hosts)$")


def check_command(command: str) -> Verdict:
    """Classify a shell command line. Compound commands take their worst part."""
    verdict = Verdict()
    command = (command or "").strip()
    if not command:
        verdict.escalate(DENY, "empty command")
        return verdict
    if len(command) > 4000:
        verdict.escalate(DENY, "command too long")
        return verdict
    for pattern, reason in DENY_PATTERNS:
        if pattern.search(command):
            verdict.escalate(DENY, reason)
    if NETWORK_DEVICE_PATTERNS.search(command):
        verdict.escalate(DENY, "network device change command")
    for pattern, reason in APPROVAL_PATTERNS:
        if pattern.search(command):
            verdict.escalate(NEEDS_APPROVAL, reason)
    for part in filter(None, (p.strip() for p in _SPLIT.split(command))):
        try:
            tokens = shlex.split(part)
        except ValueError:
            verdict.escalate(NEEDS_APPROVAL, "unparseable quoting")
            continue
        while tokens and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[0]):
            tokens.pop(0)  # leading VAR=value
        if not tokens:
            continue
        name = Path(tokens[0]).name
        args = tokens[1:]
        if name in ALWAYS_DENY:
            verdict.escalate(DENY, f"blocked program: {name}")
        elif name in DELETE_OR_PERM:
            verdict.escalate(NEEDS_APPROVAL, f"modifies files or permissions: {name}")
        elif name in NETWORK:
            verdict.escalate(NEEDS_APPROVAL, f"network or package operation: {name}")
        elif name in {"bash", "sh", "zsh", "eval", "exec", "source", "xargs", "find", "env"}:
            verdict.escalate(NEEDS_APPROVAL, f"indirect execution: {name}")
        elif name == "git":
            sub = next((a for a in args if not a.startswith("-")), "")
            if sub not in GIT_READ:
                verdict.escalate(NEEDS_APPROVAL, f"git {sub or '(no subcommand)'}")
        elif name in {"python", "python3"}:
            module = args[:2] == ["-m", "unittest"] or args[:2] == ["-m", "pytest"] or args[:1] == ["-m"] and \
                len(args) > 1 and args[1] in {"unittest", "pytest", "py_compile", "json.tool"}
            if not module:
                verdict.escalate(NEEDS_APPROVAL, "arbitrary python execution")
        elif name in {"pytest"}:
            pass
        elif name in READ_ONLY:
            for arg in args:
                if SENSITIVE_FILES.search(arg):
                    verdict.escalate(DENY, "reads a secret/credential file")
        else:
            verdict.escalate(NEEDS_APPROVAL, f"unknown program: {name}")
    return verdict


class PathViolation(ValueError):
    pass


def resolve_in_sandbox(path: str, root: Path | str, for_write: bool = False) -> Path:
    """Resolve *path* inside *root*; reject escapes, symlink tricks and secret files."""
    root = Path(root).resolve()
    candidate = (root / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise PathViolation("path escapes the sandbox root") from exc
    rel = candidate.relative_to(root).as_posix()
    if SENSITIVE_FILES.search(rel) or SENSITIVE_FILES.search(candidate.name):
        raise PathViolation("access to secret/credential files is blocked")
    if for_write and (rel == ".git" or rel.startswith(".git/")):
        raise PathViolation("writing inside .git is blocked")
    return candidate
