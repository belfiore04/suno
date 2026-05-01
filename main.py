"""
Suno 音乐生成工作流：混音 → 上传 → Cover 生成 → 下载 → OSS 上传 → 二维码

用法:
    python main.py audio1.mp3 audio2.mp3 --prompt "歌词内容" --style "pop, upbeat"
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from arduino_reader import read_relay_ids, relay_id_to_music_path
from mixer import mix_audios
from suno_client import upload_audio, generate_cover, wait_for_results, download_song
from oss_uploader import upload_to_oss
from qr_gen import generate_qr


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="音频混音 + Suno Cover API + OSS 上传 + 二维码")
    parser.add_argument("audio_files", nargs="*", help="输入音频文件路径；也可用 --arduino-port 从 Arduino 读取")
    parser.add_argument("--prompt", default="", help="歌词内容（留空则为纯器乐）")
    parser.add_argument("--style", default="pop", help="音乐风格标签，如 'pop, upbeat'")
    parser.add_argument("--title", default="AI Generated Song", help="歌曲标题")
    parser.add_argument("--model", default="chirp-v4-tau",
                        choices=["chirp-v3-5-tau", "chirp-v4-tau", "chirp-auk", "chirp-bluejay"],
                        help="Suno 模型版本")
    parser.add_argument("--output-dir", default="output", help="输出目录")
    parser.add_argument("--skip-oss", action="store_true", help="跳过 OSS 上传和二维码步骤")
    parser.add_argument("--arduino-port", help="Arduino 串口，如 COM3、/dev/ttyACM0、/dev/ttyUSB0")
    parser.add_argument("--arduino-baud", type=int, default=9600, help="Arduino 串口波特率")
    parser.add_argument("--arduino-count", type=int, default=4, help="读取几个 Arduino 按钮编号")
    parser.add_argument("--arduino-only", action="store_true", help="只读取 Arduino 并打印映射结果，不调用 Suno")
    parser.add_argument("--music-dir", default="music", help="Arduino 编号映射使用的音乐目录")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    audio_files = list(args.audio_files)
    if args.arduino_port:
        relay_ids = read_relay_ids(args.arduino_port, args.arduino_baud, args.arduino_count)
        audio_files = [relay_id_to_music_path(relay_id, args.music_dir) for relay_id in relay_ids]
        print("[Arduino] 映射到音频文件:")
        for relay_id, audio_file in zip(relay_ids, audio_files):
            print(f"  {relay_id} -> {audio_file}")
        if args.arduino_only:
            return
    elif args.arduino_only:
        print("错误: --arduino-only 需要同时指定 --arduino-port", file=sys.stderr)
        sys.exit(1)

    if not audio_files:
        print("错误: 请传入音频文件，或使用 --arduino-port 从 Arduino 读取按钮编号", file=sys.stderr)
        sys.exit(1)

    for f in audio_files:
        if not Path(f).exists():
            print(f"错误: 文件不存在: {f}", file=sys.stderr)
            sys.exit(1)

    # 步骤 1: 混音
    print("\n=== 步骤 1/4: 音频混音 ===")
    mixed_path = str(output_dir / "mixed.mp3")
    mix_audios(audio_files, mixed_path)

    # 步骤 2: 上传到 Suno + Cover 生成
    print("\n=== 步骤 2/4: 上传音频 + Suno Cover 生成 ===")
    cover_clip_id = upload_audio(mixed_path)
    task = generate_cover(
        cover_clip_id=cover_clip_id,
        prompt=args.prompt,
        style=args.style,
        title=args.title,
        mv=args.model,
    )
    results = wait_for_results(task["clip_ids"])

    # 步骤 3: 下载第一首生成结果
    print("\n=== 步骤 3/4: 下载生成的歌曲 ===")
    first = results[0]
    song_filename = f"{first.get('title', 'song')}_{first['id']}.mp3"
    local_song_path = str(output_dir / song_filename)
    download_song(first["audio_url"], local_song_path)

    if args.skip_oss:
        print(f"\n=== 完成 ===")
        print(f"生成的 AI 歌曲: {local_song_path}")
        return

    # 步骤 4: 上传 OSS + 生成二维码
    print("\n=== 步骤 4/4: OSS 上传 + 生成二维码 ===")
    download_url = upload_to_oss(local_song_path, object_key=f"suno_music/output/{song_filename}")
    qr_path = str(output_dir / "download_qr.png")
    generate_qr(download_url, qr_path)

    print("\n=== 全部完成 ===")
    print(f"生成的 AI 歌曲:   {local_song_path}")
    print(f"OSS 下载链接:     {download_url}")
    print(f"二维码图片路径:   {qr_path}")


if __name__ == "__main__":
    main()
