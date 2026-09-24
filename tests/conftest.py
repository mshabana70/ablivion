from __future__ import annotations

import pytest
from helpers import prompt


@pytest.fixture
def three_role_rows() -> list[dict]:
    return [
        prompt("p1", "f1", "alpha"),
        prompt("p2", "f1", "alpha, reworded"),
        prompt("p3", "f2", "beta", category="harmful"),
        prompt("p4", "f3", "gamma"),
    ]
