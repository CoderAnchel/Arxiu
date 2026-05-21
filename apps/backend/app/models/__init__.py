"""ORM model package — import all so Alembic discovers them via Base.metadata."""
from app.models.app_settings import AppSettings
from app.models.audit_log import AuditLog
from app.models.catalog import Cicle, CursAcademic, FamiliaProfessional, Modul, Nivell, Ra
from app.models.enviaments import Enviament, EstatEnviament, TipusEnviament
from app.models.grading import Avaluacio, EstatAvaluacio, QualificacioModul, QualificacioRa
from app.models.imports import EstatImport, Import, TipusImport
from app.models.people import (
    Alumne,
    AssignacioDocent,
    EstatMatricula,
    GrupClasse,
    Matricula,
    TipusGrup,
    TutorLegal,
)
from app.models.user import User, UserRole

__all__ = [
    "Alumne",
    "AppSettings",
    "AssignacioDocent",
    "AuditLog",
    "Avaluacio",
    "Cicle",
    "CursAcademic",
    "Enviament",
    "EstatAvaluacio",
    "EstatEnviament",
    "EstatImport",
    "EstatMatricula",
    "FamiliaProfessional",
    "GrupClasse",
    "Import",
    "Matricula",
    "Modul",
    "Nivell",
    "QualificacioModul",
    "QualificacioRa",
    "Ra",
    "TipusEnviament",
    "TipusGrup",
    "TipusImport",
    "TutorLegal",
    "User",
    "UserRole",
]
