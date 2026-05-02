"""Local web server for the video hotspot Suno workflow."""

import base64
from io import BytesIO
import os
from pathlib import Path
from typing import Optional
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import qrcode

from mixer import mix_audios
from oss_uploader import upload_to_oss
from qr_gen import generate_qr
from suno_client import download_song, generate_cover, upload_audio, wait_for_results


ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT / "frontend"
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Suno Hotspot Composer")
app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR), html=False), name="output")
app.mount("/music", StaticFiles(directory=str(ROOT / "music"), html=False), name="music")


class SelectedItem(BaseModel):
    id: int
    name: str = Field(min_length=1)
    file: str = Field(min_length=1)


class GenerateRequest(BaseModel):
    items: list[SelectedItem] = Field(min_length=4, max_length=4)
    style: str = "meditative a cappella, serene vocal ensemble, vocal only"
    skip_oss: bool = False


class MixPreviewRequest(BaseModel):
    items: list[SelectedItem] = Field(min_length=4, max_length=4)


AUDIO_WORDS = {
    11: "浮叶",
    12: "晨钟",
    13: "断句",
    14: "倒刺",
    15: "碎镜",
    21: "暗涌",
    22: "苔原",
    23: "软重",
    24: "沉晖",
    25: "未烬",
    31: "侧临",
    32: "无滞",
    33: "静观",
    34: "返听",
    35: "不沾",
    41: "重频",
    42: "余振",
    43: "伏根",
    44: "地脉",
    45: "底鸣",
}


def _safe_audio_path(file_name: str) -> Path:
    path = (ROOT / file_name).resolve()
    if ROOT not in path.parents:
        raise HTTPException(status_code=400, detail=f"非法音频路径: {file_name}")
    if not path.exists():
        raise HTTPException(status_code=400, detail=f"音频不存在: {file_name}")
    return path


def _absolute_url(request: Request, relative_url: str) -> str:
    public_base_url = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    if public_base_url:
        return f"{public_base_url}{relative_url}"
    return str(request.base_url).rstrip("/") + relative_url


def _qr_data_url(url: str) -> str:
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def build_song_metadata(items: list[SelectedItem], style: str) -> tuple[str, str, str, str]:
    names = [AUDIO_WORDS.get(item.id, item.name.strip()) for item in items]
    title = f"{names[0]}·{names[1]}·{names[2]}·{names[3]}"
    lyrics = "\n".join([
        "啊 啊 啊 啊",
        "呜 呜 呜 呜",
        "啦 啦 啦 啦",
        "嗯 嗯 嗯 嗯",
    ])
    prompt = lyrics
    tags = ", ".join([
        style,
        "a cappella",
        "vocal only",
        "no instruments",
        "no lyrics",
        "no words",
        "no meaningful words",
        "no English lyrics",
        "no Chinese lyrics",
        "non-lexical vocals only",
        "vocables only",
        "sing only ah ooh la hum",
        "four-part harmony",
        "all four voices enter together from the beginning",
        "no solo lead vocal intro",
        "choir ensemble from first phrase",
        "tenor",
        "bass",
        "soprano",
        "alto",
        "meditative",
        "deep meditation",
        "serene",
        "calm",
        "slow breathing",
        "soft sustained harmonies",
        "spacious vocal ambience",
        "gentle resonance",
        "minimal",
        "melodious",
        "ancient",
        "slow tempo",
        "less pop",
        "not mainstream pop",
        "no pop beat",
        "no pop lead vocal",
        "no verse chorus pop structure",
    ])
    return title, lyrics, prompt, tags


def _mix_selected_items(items: list[SelectedItem]) -> tuple[str, Path]:
    names = [AUDIO_WORDS.get(item.id, item.name.strip()) for item in items]
    title = f"{names[0]}·{names[1]}·{names[2]}·{names[3]}"
    audio_paths = [_safe_audio_path(item.file) for item in items]
    mixed_path = OUTPUT_DIR / f"reference_{title}_{uuid4().hex[:8]}.mp3"
    mix_audios([str(path) for path in audio_paths], str(mixed_path))
    return title, mixed_path


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.post("/api/mix-preview")
def mix_preview(payload: MixPreviewRequest) -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    title, mixed_path = _mix_selected_items(payload.items)
    return {
        "title": title,
        "mixed_path": str(mixed_path),
        "mixed_url": f"/output/{mixed_path.name}",
    }


@app.post("/api/generate")
def generate_song(payload: GenerateRequest, request: Request) -> dict:
    load_dotenv()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    title, lyrics, prompt, style = build_song_metadata(payload.items, payload.style)
    _, mixed_path = _mix_selected_items(payload.items)

    cover_clip_id = upload_audio(str(mixed_path))
    task = generate_cover(
        cover_clip_id=cover_clip_id,
        prompt=prompt,
        style=style,
        title=title,
    )
    results = wait_for_results(task["clip_ids"], min_ready=1)
    first = results[0]
    song_filename = f"{first.get('title', title)}_{first['id']}.mp3"
    local_song_path = OUTPUT_DIR / song_filename
    download_song(first["audio_url"], str(local_song_path))

    download_url: Optional[str] = None
    qr_path: Optional[str] = None
    if not payload.skip_oss:
        try:
            download_url = upload_to_oss(str(local_song_path), object_key=f"suno_music/output/{song_filename}")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"OSS 上传失败，二维码未生成: {exc}") from exc
        qr_path = str(OUTPUT_DIR / "download_qr.png")
        generate_qr(download_url, qr_path)

    song_url = f"/output/{song_filename}"
    mixed_url = f"/output/{mixed_path.name}"
    if not download_url and not payload.skip_oss:
        raise HTTPException(status_code=500, detail="OSS 上传没有返回下载链接，已停止生成二维码")

    qr_target_url = download_url or _absolute_url(request, song_url)
    qr_data_url = _qr_data_url(qr_target_url)

    return {
        "title": title,
        "lyrics": lyrics,
        "style": style,
        "mixed_path": str(mixed_path),
        "mixed_url": mixed_url,
        "song_path": str(local_song_path),
        "song_url": song_url,
        "qr_url": qr_target_url,
        "qr_data_url": qr_data_url,
        "download_url": download_url,
        "qr_path": qr_path,
    }
