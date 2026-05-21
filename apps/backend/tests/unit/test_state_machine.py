"""Avaluació state-machine pure-function tests."""
from __future__ import annotations

import pytest

from app.models.grading import EstatAvaluacio
from app.services.avaluacio_state import (
    BACKWARD_TRANSITIONS,
    FORWARD_TRANSITIONS,
    is_rollback,
    is_valid_transition,
)


def test_forward_chain() -> None:
    chain = [
        EstatAvaluacio.OBERTA,
        EstatAvaluacio.DOCENT,
        EstatAvaluacio.JUNTA,
        EstatAvaluacio.TANCADA,
    ]
    for cur, nxt in zip(chain, chain[1:]):
        assert is_valid_transition(current=cur, target=nxt)


def test_skip_steps_are_invalid() -> None:
    # oberta -> junta (skip docent) is not allowed
    assert not is_valid_transition(
        current=EstatAvaluacio.OBERTA, target=EstatAvaluacio.JUNTA
    )
    assert not is_valid_transition(
        current=EstatAvaluacio.DOCENT, target=EstatAvaluacio.TANCADA
    )
    assert not is_valid_transition(
        current=EstatAvaluacio.OBERTA, target=EstatAvaluacio.TANCADA
    )


def test_rollback_one_step_is_valid() -> None:
    assert is_valid_transition(
        current=EstatAvaluacio.DOCENT, target=EstatAvaluacio.OBERTA
    )
    assert is_valid_transition(
        current=EstatAvaluacio.JUNTA, target=EstatAvaluacio.DOCENT
    )
    assert is_valid_transition(
        current=EstatAvaluacio.TANCADA, target=EstatAvaluacio.JUNTA
    )


def test_rollback_two_steps_is_invalid() -> None:
    assert not is_valid_transition(
        current=EstatAvaluacio.TANCADA, target=EstatAvaluacio.DOCENT
    )
    assert not is_valid_transition(
        current=EstatAvaluacio.JUNTA, target=EstatAvaluacio.OBERTA
    )


def test_is_rollback_flag() -> None:
    assert is_rollback(current=EstatAvaluacio.DOCENT, target=EstatAvaluacio.OBERTA)
    assert not is_rollback(current=EstatAvaluacio.OBERTA, target=EstatAvaluacio.DOCENT)


def test_state_tables_are_inverses() -> None:
    """Every forward transition has a matching backward and vice-versa."""
    for src, dst in FORWARD_TRANSITIONS.items():
        assert BACKWARD_TRANSITIONS[dst] == src
