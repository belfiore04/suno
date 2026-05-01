"""Read button selections from an Arduino Mega over serial."""

from pathlib import Path
import re
import time


RELAY_ID_RE = re.compile(r"\b([1-4][1-5])\b")


def relay_id_to_music_path(relay_id: int, music_dir: str = "music") -> str:
    """Map Arduino relay id XY to music/Y.X_1.mp3."""
    group = relay_id // 10
    option = relay_id % 10
    if group < 1 or group > 4 or option < 1 or option > 5:
        raise ValueError(f"Arduino 编号不在有效范围 11~45: {relay_id}")

    path = Path(music_dir) / f"{option}.{group}_1.mp3"
    if not path.exists():
        raise FileNotFoundError(f"Arduino 编号 {relay_id} 对应的音频不存在: {path}")
    return str(path)


def parse_relay_ids(line: str) -> list[int]:
    """Extract relay ids from a serial line."""
    return [int(match) for match in RELAY_ID_RE.findall(line)]


def read_relay_ids(
    port: str,
    baud: int = 9600,
    count: int = 4,
    timeout: float = 1.0,
) -> list[int]:
    """Block until count relay ids have been read from the Arduino serial port."""
    try:
        import serial
    except ImportError as exc:
        raise RuntimeError("缺少 pyserial，请先运行: pip install -r requirements.txt") from exc

    selected: list[int] = []
    print(f"[Arduino] 正在监听 {port}，波特率 {baud}。请按 {count} 个组内按钮...")

    with serial.Serial(port, baudrate=baud, timeout=timeout) as ser:
        time.sleep(2)
        ser.reset_input_buffer()
        while len(selected) < count:
            raw = ser.readline()
            if not raw:
                continue

            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue

            print(f"[Arduino] {line}")
            for relay_id in parse_relay_ids(line):
                if len(selected) >= count:
                    break
                selected.append(relay_id)
                print(f"[Arduino] 已记录按钮编号: {relay_id}")

    return selected
