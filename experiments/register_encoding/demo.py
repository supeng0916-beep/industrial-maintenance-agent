"""离线教学：固定已知寄存器，比较整数/浮点类型及字顺序；不连接设备、不写数据库。"""
import math
import struct


def main():
    print('实验一：uint32，高16位在前，倍率0.001℃')
    registers = [1, 57920]  # 固定已知向量：0x0001E240 = 123456
    correct = (registers[0] * 65536 + registers[1]) * 0.001
    swapped = (registers[1] * 65536 + registers[0]) * 0.001
    print(f'寄存器：{registers}')
    print(f'正确顺序：{correct:.3f}℃')
    print(f'颠倒顺序：{swapped:.3f}℃')
    assert math.isclose(correct, 123.456)
    assert not math.isclose(swapped, 123.456)

    print('\n实验二：Float32，高16位在前，每个寄存器内高字节在前')
    registers = [0x4282, 0x999A]  # 独立固定向量：IEEE754 binary32，约65.3
    raw_bytes = struct.pack('>HH', *registers)
    correct = struct.unpack('>f', raw_bytes)[0]
    swapped = struct.unpack('>f', struct.pack('>HH', *registers[::-1]))[0]
    mistaken_integer = struct.unpack('>I', raw_bytes)[0]
    print(f'寄存器十六进制：[0x{registers[0]:04X}, 0x{registers[1]:04X}]')
    print(f'寄存器十进制：{registers}')
    print(f'按Float32正确解析：{correct:.12f}℃（页面保留1位小数：{correct:.1f}℃）')
    print(f'颠倒两个寄存器：{swapped:.8e}℃')
    print(f'误按uint32解析：{mistaken_integer}（本实验没有这种整数倍率约定）')
    assert math.isclose(correct, 65.3, abs_tol=0.00001)
    assert not math.isclose(swapped, 65.3, abs_tol=0.00001)
    print('\n检查通过：正确解析符合已知值；错误顺序/类型产生不同结果。')
    print('注意：范围合理不等于解析正确，仍必须核对点位表和已知测试值。')


if __name__ == '__main__':
    main()
