import pytest

from backend.app.runtime.supervisor import RuntimeSupervisor


@pytest.mark.parametrize(
    ("current_hp", "expected"),
    [
        (100, "健康"),
        (76, "健康"),
        (75, "轻伤"),
        (51, "轻伤"),
        (50, "重伤"),
        (26, "重伤"),
        (25, "濒危"),
        (1, "濒危"),
        (0, "昏迷"),
    ],
)
def test_health_label_boundaries(current_hp: int, expected: str) -> None:
    assert RuntimeSupervisor._health_label(current_hp, 100) == expected
