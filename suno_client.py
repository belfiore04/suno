"""Suno API 模块：通过 REST API 上传音频并生成 Cover。"""

import os
import time
import requests
from pathlib import Path


def _base_url() -> str:
    return os.getenv("SUNO_BASE_URL", "https://api.bltcy.ai")


def _headers() -> dict:
    api_key = os.getenv("SUNO_API_KEY")
    if not api_key:
        raise ValueError("请设置环境变量 SUNO_API_KEY")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "*/*",
    }


def upload_audio(local_path: str) -> str:
    """上传本地音频文件到 Suno，返回 clip_id。"""
    base = _base_url()

    # 1. 申请 S3 上传 URL
    print("[Upload] 申请上传 URL...")
    resp = requests.post(
        f"{base}/suno/uploads/audio",
        headers=_headers(),
        json={"extension": "mp3"},
    )
    resp.raise_for_status()
    info = resp.json()
    upload_id = info["id"]
    s3_url = info["url"]
    fields = info["fields"]
    print(f"[Upload] upload_id: {upload_id}")

    # 2. 直接 POST 到 S3（multipart/form-data）
    print("[Upload] 上传文件到 S3...")
    with open(local_path, "rb") as f:
        form = {k: (None, v) for k, v in fields.items()}
        form["file"] = (Path(local_path).name, f, "audio/mpeg")
        s3_resp = requests.post(s3_url, files=form)
    if s3_resp.status_code not in (200, 204):
        raise RuntimeError(f"S3 上传失败: {s3_resp.status_code} {s3_resp.text[:200]}")
    print("[Upload] S3 上传成功")

    # 3. 通知 Suno 上传完毕
    print("[Upload] 通知上传完毕...")
    finish_resp = requests.post(
        f"{base}/suno/uploads/audio/{upload_id}/upload-finish",
        headers=_headers(),
        json={
            "upload_type": "file_upload",
            "upload_filename": Path(local_path).name,
        },
    )
    finish_resp.raise_for_status()
    print(f"[Upload] finish 响应: {finish_resp.text[:200]}")

    # 4. 轮询等待处理完成，拿到 clip_id
    print("[Upload] 等待音频处理...")
    for i in range(40):
        time.sleep(3)
        status_resp = requests.get(
            f"{base}/suno/uploads/audio/{upload_id}",
            headers=_headers(),
        )
        status_resp.raise_for_status()
        data = status_resp.json()
        print(f"[Upload] 第{i+1}次轮询: {data}")
        clip_id = data.get("clip_id") or data.get("s3_id")
        if clip_id and data.get("status") == "complete":
            print(f"[Upload] 处理完成，clip_id: {clip_id}")
            return clip_id
    raise TimeoutError("音频上传处理超时（>120s）")


def generate_cover(
    cover_clip_id: str,
    prompt: str = "",
    style: str = "pop",
    title: str = "AI Cover",
    mv: str = "chirp-v4-tau",
) -> dict:
    """提交 Cover 生成任务，返回包含 clip_ids 和 task_id 的 dict。"""
    print(f"[Generate] 提交 Cover 任务，cover_clip_id={cover_clip_id}")
    body = {
        "prompt": prompt,
        "generation_type": "TEXT",
        "tags": style,
        "negative_tags": "",
        "mv": mv,
        "title": title,
        "continue_clip_id": None,
        "continue_at": None,
        "continued_aligned_prompt": None,
        "infill_start_s": None,
        "infill_end_s": None,
        "task": "cover",
        "cover_clip_id": cover_clip_id,
    }
    resp = requests.post(
        f"{_base_url()}/suno/generate",
        headers=_headers(),
        json=body,
    )
    resp.raise_for_status()
    data = resp.json()
    clips = data.get("clips", [])
    if not clips:
        raise RuntimeError(f"生成任务提交失败，响应: {data}")
    clip_ids = [c["id"] for c in clips]
    print(f"[Generate] 任务已提交，clip_ids: {clip_ids}")
    return {"clip_ids": clip_ids, "task_id": data.get("id"), "title": title}


def wait_for_results(clip_ids: list, max_wait: int = 600) -> list:
    """轮询直到所有 clip 的 audio_url 填充完毕，返回结果列表。"""
    ids_str = ",".join(clip_ids)
    print(f"[Fetch] 等待生成结果，轮询 clip_ids: {ids_str}")
    elapsed = 0
    while elapsed < max_wait:
        time.sleep(10)
        elapsed += 10
        resp = requests.get(
            f"{_base_url()}/suno/feed/{ids_str}",
            headers=_headers(),
        )
        resp.raise_for_status()
        clips = resp.json()
        if not isinstance(clips, list):
            clips = [clips]
        ready = [c for c in clips if c.get("audio_url")]
        if elapsed % 30 == 0 or ready:
            print(f"[Fetch] {elapsed}s，已就绪 {len(ready)}/{len(clip_ids)}")
        if len(ready) >= len(clip_ids):
            print("[Fetch] 全部生成完成！")
            return ready
    raise TimeoutError(f"Suno 生成超时（>{max_wait}s）")


def download_song(audio_url: str, output_path: str) -> str:
    """下载生成的歌曲到本地。"""
    print(f"[Download] 正在下载: {audio_url}")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}
    resp = requests.get(audio_url, stream=True, headers=headers)
    resp.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"[Download] 已保存: {output_path}")
    return output_path
