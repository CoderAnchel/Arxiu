"""Role-based access control. Pure functions — caller fetches the contextual
data (assignacions, tutorship rows, avaluació estat) and passes them in.
This keeps every predicate independently unit-testable.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Protocol


class Role(StrEnum):
    ADMIN = "admin"
    PROFESSOR = "professor"


class HasRole(Protocol):
    role: str
    active: bool


# --- Role checks ------------------------------------------------------------

def is_admin(user: HasRole) -> bool:
    return user.role == Role.ADMIN and user.active


def is_professor(user: HasRole) -> bool:
    return user.role == Role.PROFESSOR and user.active


def can_manage_users(user: HasRole) -> bool:
    return is_admin(user)


def can_view_audit_log(user: HasRole) -> bool:
    return is_admin(user)


def can_manage_catalog(user: HasRole) -> bool:
    """Cicles, mòduls, RAs, cursos, grups, matrícules — admin only."""
    return is_admin(user)


# --- Avaluacions ------------------------------------------------------------

def can_transition_avaluacio(user: HasRole) -> bool:
    """Only admin advances avaluació state (oberta → docent → junta → tancada)."""
    return is_admin(user)


# --- Qualificacions per RA --------------------------------------------------
#
# A qualificació RA can be edited by:
#   - admin: always
#   - professor: when avaluació is `docent` AND there is an
#     assignacions_docents row for (user, grup, modul, curs_acad)
#   - professor acting as tutor: when avaluació is `junta` AND
#     grups_classe.tutor_user_id == user.id for the grup
#   - tancada: nobody (admin can rollback to junta first if a fix is needed)
#

def can_edit_qualif_ra(
    *,
    user: HasRole,
    avaluacio_estat: str,
    has_assignacio: bool,
    is_tutor_of_grup: bool,
) -> bool:
    if not user.active:
        return False
    if user.role == Role.ADMIN:
        return True
    if user.role != Role.PROFESSOR:
        return False
    if avaluacio_estat == "docent" and has_assignacio:
        return True
    if avaluacio_estat == "junta" and is_tutor_of_grup:
        return True
    return False


def can_view_qualifs_for_grup(
    *,
    user: HasRole,
    has_assignacio: bool,
    is_tutor_of_grup: bool,
) -> bool:
    """Read access. Admin always; professor if assigned or tutor of grup."""
    if not user.active:
        return False
    if user.role == Role.ADMIN:
        return True
    return has_assignacio or is_tutor_of_grup


# --- Qualificacions de mòdul ------------------------------------------------

def can_edit_qualif_modul(
    *,
    user: HasRole,
    avaluacio_estat: str,
    has_assignacio: bool,
    is_tutor_of_grup: bool,
) -> bool:
    """Final mòdul nota — same rule set as RA notes."""
    return can_edit_qualif_ra(
        user=user,
        avaluacio_estat=avaluacio_estat,
        has_assignacio=has_assignacio,
        is_tutor_of_grup=is_tutor_of_grup,
    )
