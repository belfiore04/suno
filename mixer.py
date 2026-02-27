"""音频混音模块：将多个音频文件叠加混合为一个文件。"""

from pathlib import Path
from pydub import AudioSegment


def load_audio(file_path: str) -> AudioSegment:
    """根据文件扩展名加载音频文件。"""
    path = Path(file_path)
    suffix = path.suffix.lower().lstrip(".")
    fmt = {"mp3": "mp3", "wav": "wav", "flac": "flac", "ogg": "ogg", "m4a": "m4a"}
    return AudioSegment.from_file(str(path), format=fmt.get(suffix, suffix))


def mix_audios(file_paths: list[str], output_path: str) -> str:
    """
    将多个音频文件混音叠加为一个文件。

    短音频会循环补齐到最长音频的长度，然后叠加在一起。
    """
    segments = [load_audio(f) for f in file_paths]
    max_len = max(len(s) for s in segments)

    # 将所有音频补齐到最长长度（循环填充）
    padded = []
    for seg in segments:
        if len(seg) < max_len:
            repeats = (max_len // len(seg)) + 1
            seg = (seg * repeats)[:max_len]
        padded.append(seg)

    # 逐个叠加
    mixed = padded[0]
    for seg in padded[1:]:
        mixed = mixed.overlay(seg)

    mixed.export(output_path, format="mp3")
    print(f"[混音] 完成，输出文件: {output_path}")
    return output_path
