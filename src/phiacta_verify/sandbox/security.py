"""Security policies and resource limits for sandboxed containers."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SecurityPolicy:
    """Immutable security policy that governs container resource limits.

    The ``network_disabled`` field is intentionally locked to ``True`` and
    enforced at both the dataclass level (``__post_init__``) and in
    ``to_container_config``.  Any attempt to create a policy with network
    access will raise ``ValueError``.
    """

    network_disabled: bool = True  # ALWAYS True – enforced in __post_init__
    read_only_rootfs: bool = True
    memory_limit_mb: int = 2048
    cpu_period: int = 100000
    cpu_quota: int = 100000  # 1 CPU
    pids_limit: int = 64
    tmpfs_size_mb: int = 256
    timeout_seconds: int = 120
    no_new_privileges: bool = True
    cap_drop: list[str] = field(default_factory=lambda: ["ALL"])

    def __post_init__(self) -> None:
        """Validate invariants that must never be violated."""
        if not self.network_disabled:
            raise ValueError(
                "SecurityPolicy.network_disabled MUST be True. "
                "Sandboxed containers are never allowed network access."
            )
        if self.memory_limit_mb <= 0:
            raise ValueError("memory_limit_mb must be a positive integer.")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be a positive integer.")
        if self.pids_limit <= 0:
            raise ValueError("pids_limit must be a positive integer.")
        if self.cpu_period <= 0:
            raise ValueError("cpu_period must be a positive integer.")
        if self.cpu_quota <= 0:
            raise ValueError("cpu_quota must be a positive integer.")
        if self.tmpfs_size_mb <= 0:
            raise ValueError("tmpfs_size_mb must be a positive integer.")

    def to_container_config(self) -> dict:
        """Convert to Docker SDK ``host_config`` parameters.

        Returns a dictionary suitable for passing as keyword arguments to
        ``docker.models.containers.ContainerCollection.run`` (or the
        equivalent low-level ``create_host_config`` call).
        """
        return {
            "network_mode": "none",  # Hard-coded regardless of field value
            "read_only": self.read_only_rootfs,
            "mem_limit": f"{self.memory_limit_mb}m",
            "memswap_limit": f"{self.memory_limit_mb}m",  # No swap
            "cpu_period": self.cpu_period,
            "cpu_quota": self.cpu_quota,
            "pids_limit": self.pids_limit,
            "security_opt": ["no-new-privileges"] if self.no_new_privileges else [],
            "cap_drop": self.cap_drop,
            "tmpfs": {"/tmp": f"size={self.tmpfs_size_mb}m,noexec,nosuid"},
        }
