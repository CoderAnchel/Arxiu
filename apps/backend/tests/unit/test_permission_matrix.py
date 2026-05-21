"""Phase-3 permission matrix — every combination of (role, estat, has_assig, is_tutor)."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.core import permissions


@dataclass
class FakeUser:
    role: str
    active: bool = True


# Pure predicate test matrix:
#   role        × estat   × has_assig × is_tutor → expected
MATRIX = [
    # admin: always (when active)
    ("admin",     "oberta",   False, False, True),
    ("admin",     "docent",   False, False, True),
    ("admin",     "junta",    False, False, True),
    ("admin",     "tancada",  False, False, True),
    # admin inactive: always False
    # (handled via separate test below)
    # professor + assigned, in `docent` → can edit
    ("professor", "docent",   True,  False, True),
    # professor + assigned, in any other state → cannot
    ("professor", "oberta",   True,  False, False),
    ("professor", "junta",    True,  False, False),
    ("professor", "tancada",  True,  False, False),
    # professor + tutor of grup, in `junta` → can edit
    ("professor", "junta",    False, True,  True),
    # professor + tutor, but in any other state → cannot
    ("professor", "docent",   False, True,  False),
    ("professor", "oberta",   False, True,  False),
    ("professor", "tancada",  False, True,  False),
    # professor with neither relationship → never
    ("professor", "docent",   False, False, False),
    ("professor", "junta",    False, False, False),
    ("professor", "oberta",   False, False, False),
    ("professor", "tancada",  False, False, False),
]


@pytest.mark.parametrize("role,estat,has_assig,is_tutor,expected", MATRIX)
def test_can_edit_qualif_ra_matrix(role, estat, has_assig, is_tutor, expected):  # type: ignore[no-untyped-def]
    user = FakeUser(role=role, active=True)
    assert (
        permissions.can_edit_qualif_ra(
            user=user,
            avaluacio_estat=estat,
            has_assignacio=has_assig,
            is_tutor_of_grup=is_tutor,
        )
        is expected
    )


def test_inactive_user_cannot_edit_anything() -> None:
    inactive = FakeUser(role="admin", active=False)
    assert not permissions.can_edit_qualif_ra(
        user=inactive, avaluacio_estat="docent", has_assignacio=True, is_tutor_of_grup=True
    )


def test_can_view_admin_always() -> None:
    assert permissions.can_view_qualifs_for_grup(
        user=FakeUser(role="admin"), has_assignacio=False, is_tutor_of_grup=False
    )


def test_can_view_professor_requires_relationship() -> None:
    p = FakeUser(role="professor")
    assert not permissions.can_view_qualifs_for_grup(
        user=p, has_assignacio=False, is_tutor_of_grup=False
    )
    assert permissions.can_view_qualifs_for_grup(user=p, has_assignacio=True, is_tutor_of_grup=False)
    assert permissions.can_view_qualifs_for_grup(user=p, has_assignacio=False, is_tutor_of_grup=True)


def test_can_transition_avaluacio_admin_only() -> None:
    assert permissions.can_transition_avaluacio(FakeUser(role="admin"))
    assert not permissions.can_transition_avaluacio(FakeUser(role="professor"))


def test_can_edit_qualif_modul_mirrors_ra_rules() -> None:
    # Same rules — sanity check that edit_modul == edit_ra for the same inputs.
    user = FakeUser(role="professor")
    for estat in ("oberta", "docent", "junta", "tancada"):
        for has_assig in (False, True):
            for is_tutor in (False, True):
                a = permissions.can_edit_qualif_ra(
                    user=user, avaluacio_estat=estat,
                    has_assignacio=has_assig, is_tutor_of_grup=is_tutor,
                )
                b = permissions.can_edit_qualif_modul(
                    user=user, avaluacio_estat=estat,
                    has_assignacio=has_assig, is_tutor_of_grup=is_tutor,
                )
                assert a == b
