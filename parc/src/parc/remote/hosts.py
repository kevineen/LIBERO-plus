"""複数ホストへの SSH 経由操作。"""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Any

import yaml

from parc.paths import PARC_ROOT


def load_hosts() -> dict[str, dict[str, str]]:
    """configs/hosts.yaml（なければ example）から hosts 辞書を読む。"""
    for name in ("hosts.yaml", "hosts.example.yaml"):
        path = PARC_ROOT / "configs" / name
        if not path.is_file():
            continue
        data = yaml.safe_load(path.read_text()) or {}
        hosts = data.get("hosts") or {}
        if isinstance(hosts, dict) and hosts:
            return {str(k): dict(v) for k, v in hosts.items() if isinstance(v, dict)}
    return {}


def resolve_host(alias: str) -> dict[str, str]:
    hosts = load_hosts()
    if alias not in hosts:
        known = ", ".join(sorted(hosts)) or "(none — copy configs/hosts.example.yaml)"
        raise KeyError(f"unknown host {alias!r}; known: {known}")
    h = hosts[alias]
    if not h.get("ssh"):
        raise KeyError(f"host {alias!r} missing ssh:")
    if not h.get("parc_dir"):
        raise KeyError(f"host {alias!r} missing parc_dir:")
    return {
        "alias": alias,
        "ssh": str(h["ssh"]),
        "parc_dir": str(h["parc_dir"]),
        "web_port": str(h.get("web_port") or "3030"),
    }


def remote_run(
    alias: str,
    argv: list[str],
    *,
    check: bool = False,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    """``ssh <host> 'cd <parc_dir> && uv run ...'`` を実行する。"""
    h = resolve_host(alias)
    # リモート側: PARC ルートで uv run
    inner = " && ".join(
        [
            f"cd {shlex.quote(h['parc_dir'])}",
            "unset VIRTUAL_ENV",
            "uv run " + " ".join(shlex.quote(a) for a in argv),
        ]
    )
    cmd = ["ssh", "-o", "BatchMode=yes", h["ssh"], inner]
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture,
        text=True,
    )


def tunnel_hint(alias: str, *, local_port: int | None = None) -> str:
    """Web UI 用 SSH トンネルコマンドを返す。"""
    h = resolve_host(alias)
    hosts = load_hosts()
    raw = hosts.get(alias) or {}
    remote_port = int(raw.get("web_port") or h["web_port"] or 3030)
    if local_port is not None:
        lp = local_port
    elif raw.get("local_web_port"):
        lp = int(raw["local_web_port"])
    else:
        lp = remote_port
    return (
        f"ssh -N -L {lp}:127.0.0.1:{remote_port} {h['ssh']}\n"
        f"# then open http://127.0.0.1:{lp}"
    )


def list_host_summaries() -> list[dict[str, Any]]:
    out = []
    for alias, raw in load_hosts().items():
        out.append(
            {
                "alias": alias,
                "ssh": raw.get("ssh"),
                "parc_dir": raw.get("parc_dir"),
                "web_port": raw.get("web_port", "3030"),
                "local_web_port": raw.get("local_web_port"),
            }
        )
    return out
