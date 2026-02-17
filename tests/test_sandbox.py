"""Tests for sandbox security policy."""

from __future__ import annotations

import pytest

from phiacta_verify.sandbox.security import SecurityPolicy


class TestSecurityPolicy:
    """Tests for SecurityPolicy dataclass and its container config."""

    def test_default_policy(self):
        policy = SecurityPolicy()
        assert policy.network_disabled is True
        assert policy.read_only_rootfs is True
        assert policy.memory_limit_mb == 2048
        assert policy.timeout_seconds == 120
        assert policy.pids_limit == 64

    def test_network_disabled_enforced(self):
        with pytest.raises(ValueError, match="network_disabled MUST be True"):
            SecurityPolicy(network_disabled=False)

    def test_memory_limit_must_be_positive(self):
        with pytest.raises(ValueError, match="memory_limit_mb"):
            SecurityPolicy(memory_limit_mb=0)

    def test_timeout_must_be_positive(self):
        with pytest.raises(ValueError, match="timeout_seconds"):
            SecurityPolicy(timeout_seconds=-1)

    def test_pids_limit_must_be_positive(self):
        with pytest.raises(ValueError, match="pids_limit"):
            SecurityPolicy(pids_limit=0)

    def test_to_container_config_network_none(self):
        config = SecurityPolicy().to_container_config()
        assert config["network_mode"] == "none"

    def test_to_container_config_no_swap(self):
        policy = SecurityPolicy(memory_limit_mb=512)
        config = policy.to_container_config()
        assert config["mem_limit"] == "512m"
        assert config["memswap_limit"] == "512m"

    def test_to_container_config_cap_drop_all(self):
        config = SecurityPolicy().to_container_config()
        assert config["cap_drop"] == ["ALL"]

    def test_to_container_config_no_new_privileges(self):
        config = SecurityPolicy().to_container_config()
        assert "no-new-privileges" in config["security_opt"]

    def test_to_container_config_tmpfs(self):
        config = SecurityPolicy(tmpfs_size_mb=128).to_container_config()
        assert "/tmp" in config["tmpfs"]
        assert "128m" in config["tmpfs"]["/tmp"]

    def test_tmpfs_does_not_have_noexec(self):
        """Python and other runtimes need exec in /tmp for temp file operations."""
        config = SecurityPolicy().to_container_config()
        assert "noexec" not in config["tmpfs"]["/tmp"]

    def test_output_tmpfs_has_noexec(self):
        """/output is for data only, should have noexec."""
        config = SecurityPolicy().to_container_config()
        assert "noexec" in config["tmpfs"]["/output"]

    def test_frozen_dataclass(self):
        policy = SecurityPolicy()
        with pytest.raises(AttributeError):
            policy.network_disabled = False  # type: ignore[misc]

    def test_custom_values(self):
        policy = SecurityPolicy(
            memory_limit_mb=1024,
            timeout_seconds=60,
            pids_limit=32,
            tmpfs_size_mb=64,
        )
        assert policy.memory_limit_mb == 1024
        assert policy.timeout_seconds == 60
        assert policy.pids_limit == 32
        assert policy.tmpfs_size_mb == 64
