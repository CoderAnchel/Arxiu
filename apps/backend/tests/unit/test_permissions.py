"""Permission predicates — pure functions."""
from __future__ import annotations

from dataclasses import dataclass

from app.core import permissions


@dataclass
class FakeUser:
    role: str
    active: bool = True


def test_admin_can_manage_users() -> None:
    assert permissions.can_manage_users(FakeUser(role="admin"))


def test_professor_cannot_manage_users() -> None:
    assert not permissions.can_manage_users(FakeUser(role="professor"))


def test_inactive_admin_cannot_manage_users() -> None:
    assert not permissions.can_manage_users(FakeUser(role="admin", active=False))


def test_admin_can_view_audit_log() -> None:
    assert permissions.can_view_audit_log(FakeUser(role="admin"))


def test_professor_cannot_view_audit_log() -> None:
    assert not permissions.can_view_audit_log(FakeUser(role="professor"))


def test_role_predicates() -> None:
    assert permissions.is_admin(FakeUser(role="admin"))
    assert not permissions.is_admin(FakeUser(role="professor"))
    assert permissions.is_professor(FakeUser(role="professor"))
    assert not permissions.is_professor(FakeUser(role="admin"))
