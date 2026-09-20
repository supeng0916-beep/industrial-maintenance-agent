"""一条命令启动本地教学看板；Ctrl+C 仅停止本次启动的四个服务。"""
import argparse
from contextlib import ExitStack
from points import POINTS
from datetime import datetime
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent


def check_ports(ports):
    if len(set(ports)) != len(ports):
        raise RuntimeError('三个服务端口必须不同。')
    for port in ports:
        if not 1024 <= port <= 65535:
            raise RuntimeError('端口必须在 1024～65535 之间。')
        with socket.socket() as sock:
            try:
                sock.bind(('127.0.0.1', port))
            except OSError as exc:
                raise RuntimeError(f'端口 {port} 已被占用或不可用。不会停止已有程序；请用 --web-port / --api-port / --modbus-port 更换对应端口。') from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--web-port', type=int, default=5175)
    parser.add_argument('--api-port', type=int, default=8010)
    parser.add_argument('--modbus-port', type=int, default=15030)
    parser.add_argument('--raw', type=int, default=POINTS['temperature'].default_raw, help='本地模拟温度原始值，默认653，即65.3℃')
    parser.add_argument('--current-raw', type=int, default=POINTS['current'].default_raw, help='电流原始值，默认123，即1.23A')
    parser.add_argument('--speed-raw', type=int, default=POINTS['speed'].default_raw, help='转速原始值，默认1450 rpm')
    parser.add_argument('--running-state-raw', type=int, default=POINTS['running_state'].default_raw, help='运行状态原始值，默认1；0停止、1运行，其他uint16用于故障注入')
    parser.add_argument('--db', default='data/dashboard-demo.sqlite3', help='相对路径以项目根目录为准；保留并追加已有历史')
    args = parser.parse_args()
    children = []
    try:
        check_ports([args.web_port, args.api_port, args.modbus_port])
        if not 0 <= args.raw <= 65535:
            raise RuntimeError('--raw 必须为 0～65535。')
        if not 0 <= args.current_raw <= 65535:
            raise RuntimeError('--current-raw 必须为0～65535。')
        for name in ('speed_raw', 'running_state_raw'):
            if not 0 <= getattr(args, name) <= 65535:
                raise RuntimeError(f'--{name.replace("_", "-")} 必须为0～65535。')
        npm = shutil.which('npm')
        if not npm:
            raise RuntimeError('未找到 npm，请先安装项目要求的 Node.js。')
        if not (ROOT / 'frontend/node_modules/.bin/vite').exists():
            raise RuntimeError('前端依赖尚未安装。请先运行 npm --prefix frontend ci，再启动本命令。')
        db = Path(args.db).expanduser()
        if not db.is_absolute():
            db = ROOT / db
        logs = ROOT / 'data' / 'dashboard-logs' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        logs.mkdir(parents=True, exist_ok=True)
        print(f'本地教学模拟，初始温度 {args.raw * .1:.1f}℃，电流 {args.current_raw * .01:.2f}A，转速 {args.speed_raw}rpm，运行状态原始值 {args.running_state_raw}\n数据库：{db}\n运行日志：{logs}', flush=True)
        with ExitStack() as files:
            def launch(name, command, cwd=ROOT, env=None):
                logfile = files.enter_context(open(logs / f'{name}.log', 'w'))
                proc = subprocess.Popen(command, cwd=cwd, env=env, stdout=logfile, stderr=subprocess.STDOUT, start_new_session=True)
                children.append((name, proc))
                print(f'正在启动：{name}', flush=True)
                return proc

            def check_children():
                for name, proc in children:
                    if proc.poll() is not None:
                        raise RuntimeError(f'{name} 已退出（{proc.returncode}），请查看 {logs / (name + ".log")}')

            def wait_ready(port, path=None):
                deadline = time.monotonic() + 25
                while time.monotonic() < deadline:
                    check_children()
                    try:
                        if path is None:
                            with socket.create_connection(('127.0.0.1', port), timeout=.3):
                                return
                        else:
                            with urlopen(f'http://127.0.0.1:{port}{path}', timeout=1) as response:
                                if response.status == 200:
                                    return
                    except OSError:
                        pass
                    time.sleep(.1)
                raise RuntimeError(f'端口 {port} 服务未就绪，请查看日志目录 {logs}')

            try:
                py = [sys.executable, '-u']
                launch('模拟器', py + ['simulator.py', '--port', str(args.modbus_port), '--raw', str(args.raw), '--current-raw', str(args.current_raw), '--speed-raw', str(args.speed_raw), '--running-state-raw', str(args.running_state_raw)])
                wait_ready(args.modbus_port)
                launch('采集器', py + ['collect_temperature.py', '--port', str(args.modbus_port), '--db', str(db)])
                launch('后端API', py + ['serve_api.py', '--port', str(args.api_port), '--db', str(db)])
                wait_ready(args.api_port, '/api/devices/motor-a/latest')
                env = dict(os.environ, API_PROXY_TARGET=f'http://127.0.0.1:{args.api_port}')
                launch('前端', [npm, 'run', 'dev', '--', '--port', str(args.web_port)], ROOT / 'frontend', env)
                wait_ready(args.web_port, '/')
                wait_ready(args.web_port, '/api/devices/motor-a/latest')
                print(f'\n看板已就绪：http://127.0.0.1:{args.web_port}\n保持此终端运行；Ctrl+C 停止本次四个服务，已存历史保留。\n温度当前固定；要改为72.8℃，停止后用 --raw 728 重新启动。', flush=True)
                while True:
                    check_children()
                    time.sleep(.5)
            finally:
                # 每个子服务有自己的进程组；包括 npm 启动的 Vite，仅清理本次创建的进程。
                for _, proc in reversed(children):
                    try:
                        os.killpg(proc.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                for _, proc in reversed(children):
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        try:
                            os.killpg(proc.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        proc.wait()
    except KeyboardInterrupt:
        print('\n已停止本次启动的服务，数据库历史保留。', flush=True)
        return 130
    except (OSError, RuntimeError) as exc:
        print(f'启动或运行失败：{exc}', file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
