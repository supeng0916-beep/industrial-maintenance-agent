"""教学点位表：协议零基地址；无符号16位；保持寄存器功能码03。"""
from dataclasses import dataclass

@dataclass(frozen=True)
class Point:
    address: int
    scale: float
    decimals: int
    unit: str
    default_raw: int
    allowed_raw: tuple[int, ...] | None = None

POINTS = {
    'temperature': Point(0, 0.1, 1, '℃', 653),
    'current': Point(1, 0.01, 2, 'A', 123),
    'speed': Point(2, 1, 0, 'rpm', 1450),
    'running_state': Point(3, 1, 0, '', 1, (0, 1)),
}
DEVICE_ID = 1
BATCH_ADDRESS = 0
BATCH_COUNT = 4
