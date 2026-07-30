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


def remote_shell(
    alias: str,
    command: str,
    *,
    check: bool = False,
    capture: bool = False,
    connect_timeout: int = 8,
) -> subprocess.CompletedProcess[str]:
    """``ssh <host> '<command>'`` を実行する（任意シェルコマンド）。

    ``remote_run`` と違い ``uv run`` / ``parc_dir`` に依存しない。
    GPU プローブ（``nvidia-smi``）など OS 側コマンド向け。
    """
    h = resolve_host(alias)
    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={connect_timeout}",
        h["ssh"],
        command,
    ]
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture,
        text=True,
    )


def remote_run(
    alias: str,
    argv: list[str],
    *,
    check: bool = False,
    capture: bool = False,
    connect_timeout: int = 8,
) -> subprocess.CompletedProcess[str]:
    """``ssh <host> 'cd <parc_dir> && uv run ...'`` を実行する。"""
    h = resolve_host(alias)
    # リモート側: PARC ディレクトリで uv run
    # 非対話 SSH は ~/.local/bin が PATH に入らないことが多い
    inner = " && ".join(
        [
            f"cd {shlex.quote(h['parc_dir'])}",
            'export PATH="$HOME/.local/bin:$PATH"',
            "unset VIRTUAL_ENV",
            "uv run " + " ".join(shlex.quote(a) for a in argv),
        ]
    )
    return remote_shell(
        alias,
        inner,
        check=check,
        capture=capture,
        connect_timeout=connect_timeout,
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


def host_gpu_recover_config(alias: str) -> dict[str, Any]:
    """auto_reboot 関連設定。未知ホストは KeyError。"""
    hosts = load_hosts()
    if alias not in hosts:
        raise KeyError(alias)
    raw = hosts[alias]
    method = str(raw.get("reboot_method") or "windows_shutdown").strip()
    if method not in {"windows_shutdown", "linux_reboot"}:
        method = "windows_shutdown"
    streak = raw.get("gpu_dead_streak_needed")
    cool = raw.get("reboot_cooldown_hours")
    return {
        "auto_reboot": bool(raw.get("auto_reboot", False)),
        "reboot_method": method,
        "streak_needed": int(streak) if streak not in (None, "") else 2,
        "cooldown_hours": float(cool) if cool not in (None, "") else 1.0,
        "parc_dir": str(raw.get("parc_dir") or ""),
        "ssh": str(raw.get("ssh") or ""),
    }


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
                "auto_reboot": bool(raw.get("auto_reboot", False)),
            }
        )
    return out
