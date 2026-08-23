"""
Multi-Process Render Sandbox & OS Security Isolation Engine.
Implements OS process sandboxing, per-origin Site Isolation (eTLD+1 boundary),
restricted IPC message validation gateway, and Cross-Origin Read Blocking (CORB).
"""

import sys
import os
import urllib.parse
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class ProcessType(Enum):
    BROWSER = 1
    RENDERER = 2
    GPU = 3
    UTILITY = 4


class SandboxLevel(Enum):
    UNRESTRICTED = 1
    LOW_INTEGRITY = 2
    ZERO_PRIVILEGE = 3


class SandboxPolicy:
    """Security Policy restricting filesystem, network, and syscall privileges."""

    def __init__(self, process_type: ProcessType):
        self.process_type = process_type

        if process_type == ProcessType.BROWSER:
            self.sandbox_level = SandboxLevel.UNRESTRICTED
            self.allow_network = True
            self.allow_disk_write = True
            self.allow_syscalls = True
        elif process_type == ProcessType.RENDERER:
            self.sandbox_level = SandboxLevel.ZERO_PRIVILEGE
            self.allow_network = False
            self.allow_disk_write = False
            self.allow_syscalls = False
        elif process_type == ProcessType.GPU:
            self.sandbox_level = SandboxLevel.LOW_INTEGRITY
            self.allow_network = False
            self.allow_disk_write = False
            self.allow_syscalls = True
        else: # UTILITY
            self.sandbox_level = SandboxLevel.LOW_INTEGRITY
            self.allow_network = True
            self.allow_disk_write = False
            self.allow_syscalls = False


class ProcessSandbox:
    """Represents an OS Process bounded by a SandboxPolicy."""

    def __init__(self, pid: int, process_type: ProcessType, origin: str = "about:blank"):
        self.pid = pid
        self.process_type = process_type
        self.origin = origin
        self.policy = SandboxPolicy(process_type)
        self.active = True

    def execute_disk_write(self, filepath: str, data: bytes) -> bool:
        """Attempts disk write operation under process sandbox constraints."""
        if not self.policy.allow_disk_write:
            raise PermissionError(
                f"SandboxAccessDenied: Process {self.pid} ({self.process_type.name}) denied disk write to {filepath}."
            )
        return True

    def execute_network_request(self, url: str) -> bool:
        """Attempts network socket request under process sandbox constraints."""
        if not self.policy.allow_network:
            raise PermissionError(
                f"SandboxAccessDenied: Process {self.pid} ({self.process_type.name}) denied network request to {url}."
            )
        return True


class SiteIsolationManager:
    """Enforces site isolation by assigning dedicated Renderer processes per eTLD+1 origin."""

    def __init__(self):
        self.origin_process_map: Dict[str, ProcessSandbox] = {}
        self.next_pid = 2000

    @classmethod
    def get_etld_plus_one(cls, url_or_origin: str) -> str:
        """Extracts eTLD+1 domain boundary for process isolation."""
        if url_or_origin.startswith("about:") or url_or_origin.startswith("chrome:"):
            return "system"

        parsed = urllib.parse.urlparse(url_or_origin)
        host = parsed.hostname or url_or_origin
        parts = host.split('.')
        if len(parts) >= 2:
            return f"{parts[-2]}.{parts[-1]}"
        return host

    def get_process_for_origin(self, origin: str) -> ProcessSandbox:
        """Returns dedicated isolated Renderer process for target origin."""
        etld = self.get_etld_plus_one(origin)

        if etld not in self.origin_process_map:
            pid = self.next_pid
            self.next_pid += 1
            proc = ProcessSandbox(pid, ProcessType.RENDERER, origin=origin)
            self.origin_process_map[etld] = proc

        return self.origin_process_map[etld]


class IPCBoundaryValidator:
    """Validates IPC message requests sent between isolated Renderer processes and Browser Process."""

    ALLOWED_RENDERER_IPC = {
        "DOM_MUTATION",
        "CANVAS_DRAW",
        "FETCH_REQUEST",
        "EVENT_EMIT",
        "WEBSOCKET_FRAME"
    }

    @classmethod
    def validate_ipc_message(
        cls,
        sender_process: ProcessSandbox,
        message_type: str,
        payload: Dict[str, Any]
    ) -> bool:
        """Validates IPC message legitimacy and enforces Cross-Origin Read Blocking (CORB)."""
        # Block unauthorized renderer syscall IPC requests
        if sender_process.process_type == ProcessType.RENDERER:
            if message_type not in cls.ALLOWED_RENDERER_IPC:
                raise SecurityError(
                    f"IPCSecurityViolation: Renderer Process {sender_process.pid} emitted forbidden IPC command '{message_type}'."
                )

        # Cross-Origin Read Blocking (CORB) verification
        target_origin = payload.get("target_origin")
        if target_origin and sender_process.process_type == ProcessType.RENDERER:
            sender_etld = SiteIsolationManager.get_etld_plus_one(sender_process.origin)
            target_etld = SiteIsolationManager.get_etld_plus_one(target_origin)
            if sender_etld != target_etld and payload.get("sensitive_data", False):
                raise SecurityError(
                    f"CORBViolation: Blocked cross-origin read from '{sender_process.origin}' targeting '{target_origin}'."
                )

        return True


class SecurityError(Exception):
    """Custom security boundary violation exception."""
    pass
