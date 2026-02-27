"""
Suno 音乐生成工作流：混音 → OSS 上传混音 → Suno upload-cover → 下载 → OSS 上传 → 二维码

用法:
    python main.py audio1.mp3 audio2.mp3 audio3.mp3 audio4.mp3 --prompt "歌词内容" --style "pop, upbeat"
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from mixer import mix_audios
from suno_client import generate_cover_playwright, download_song
from oss_uploader import upload_to_oss
from qr_gen import generate_qr


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="音频混音 + Suno upload-cover + OSS 上传 + 二维码下载")
    parser.add_argument("audio_files", nargs="+", help="输入音频文件路径（至少 1 个）")
    parser.add_argument("--prompt", default="", help="歌词内容（custom 模式下非纯器乐时必填）")
    parser.add_argument("--style", default="pop", help="音乐风格标签，如 'pop, upbeat'")
    parser.add_argument("--title", default="AI Generated Song", help="歌曲标题")
    parser.add_argument("--instrumental", action="store_true", help="生成纯器乐版")
    parser.add_argument("--model", default="V4_5", choices=["V4", "V4_5", "V4_5PLUS", "V4_5ALL", "V5"], help="Suno 模型版本")
    parser.add_argument("--audio-weight", type=float, default=0.7, help="原始音频影响权重 0.00-1.00")
    parser.add_argument("--style-weight", type=float, default=0.5, help="风格引导权重 0.00-1.00")
    parser.add_argument("--output-dir", default="output", help="输出目录")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 验证输入文件
    for f in args.audio_files:
        if not Path(f).exists():
            print(f"错误: 文件不存在: {f}", file=sys.stderr)
            sys.exit(1)

    # 步骤 1: 混音
    print("\n=== 步骤 1/4: 音频混音 ===")
    mixed_path = str(output_dir / "mixed.mp3")
    mix_audios(args.audio_files, mixed_path)

    # 步骤 2: Suno Playwright 自动化生成
    print("\n=== 步骤 2/4: Suno 网页自动化生成歌曲 ===")
    print("注意: 执行此步骤前，请确保您已经通过 --remote-debugging-port 启动了已登录 Suno 的 Chrome！")
    try:
        song_info = generate_cover_playwright(
            local_audio_path=mixed_path,
            prompt=args.prompt,
            style=args.style,
            title=args.title,
            instrumental=args.instrumental
        )
    except Exception as e:
        print(f"\n[错误] Suno 自动化过程失败: {e}", file=sys.stderr)
        sys.exit(1)

    # 步骤 3: 下载生成的歌曲并上传到 OSS 
    # (注意：包含云端备份原始混音音频可选功能)
    print("\n=== 步骤 3/4: 下载并上传生成的歌曲 ===")
    audio_url = song_info["audio_url"]
    song_filename = f"{song_info.get('title', 'song')}_{song_info['id']}.mp3"
    local_song_path = str(output_dir / song_filename)
    download_song(audio_url, local_song_path)

    print("上传生成的 AI 音乐到 OSS...")
    download_url = upload_to_oss(local_song_path, object_key=f"suno_music/output/{song_filename}")

    # 上传原始混音 (可选供参考)
    print("上传原始混音版本到 OSS (备份)...")
    mixed_url = upload_to_oss(mixed_path, object_key="suno_music/source/mixed.mp3")

    # 步骤 4: 生成二维码
    print("\n=== 步骤 4/4: 生成下载二维码 ===")
    qr_path = str(output_dir / "download_qr.png")
    generate_qr(download_url, qr_path)

    print("\n=== 全部完成 ===")
    print(f"原始混音云端备份: {mixed_url}")
    print(f"生成的 AI 歌曲:   {local_song_path}")
    print(f"OSS 直接下载链接: {download_url}")
    print(f"二维码图片路径:   {qr_path}")


if __name__ == "__main__":
    main()
