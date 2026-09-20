"""单次读取：新版采集器批量读四点；旧温度CLI仍只读一个寄存器。"""
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException
from points import POINTS, DEVICE_ID, BATCH_ADDRESS, BATCH_COUNT

class DataValidationError(ValueError):
    """协议读取成功，但寄存器值不满足点位的数据契约。"""


SCALE = POINTS['temperature'].scale


def read_registers(port, address, count):
    client = ModbusTcpClient('127.0.0.1', port=port, timeout=2, retries=0)
    try:
        if not client.connect():
            raise ConnectionError('无法连接，请检查模拟器是否启动、端口是否一致')
        response = client.read_holding_registers(address, count=count, device_id=DEVICE_ID)
        if response.isError():
            raise ModbusException(f'设备返回错误：{response}；新版采集器需要四个保持寄存器')
        registers = getattr(response, 'registers', None)
        if registers is None or len(registers) != count:
            raise ModbusException(f'响应必须包含{count}个寄存器，不接受缺失测点或部分结果')
        if any(type(raw) is not int or not 0 <= raw <= 65535 for raw in registers):
            raise ModbusException('寄存器必须为无符号16位整数')
        return registers
    finally:
        client.close()


def read_temperature(port=15020):
    point = POINTS['temperature']
    raw = read_registers(port, point.address, 1)[0]
    return raw, round(raw * point.scale, point.decimals)


def read_points(port=15020):
    registers = read_registers(port, BATCH_ADDRESS, BATCH_COUNT)
    values = {}
    for metric, point in POINTS.items():
        raw = registers[point.address - BATCH_ADDRESS]
        if point.allowed_raw is not None and raw not in point.allowed_raw:
            raise DataValidationError(f'{metric} raw={raw}，允许值={point.allowed_raw}；本轮四点均不保存')
        values[metric] = round(raw * point.scale, point.decimals)
    return values
