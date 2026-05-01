"""Local web server for the video hotspot Suno workflow."""

from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

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


class SelectedItem(BaseModel):
    id: int
    name: str = Field(min_length=1)
    file: str = Field(min_length=1)


class GenerateRequest(BaseModel):
    items: list[SelectedItem] = Field(min_length=4, max_length=4)
    style: str = "pop, cinematic, Mandarin vocal"
    skip_oss: bool = True


def _safe_audio_path(file_name: str) -> Path:
    path = (ROOT / file_name).resolve()
    if ROOT not in path.parents:
        raise HTTPException(status_code=400, detail=f"非法音频路径: {file_name}")
    if not path.exists():
        raise HTTPException(status_code=400, detail=f"音频不存在: {file_name}")
    return path


def build_song_metadata(items: list[SelectedItem], style: str) -> tuple[str, str, str]:
    names = [item.name.strip() for item in items]
    title = f"{names[0]}与{names[-1]}之间"
    theme = "、".join(names)
    lyrics = "\n".join([
        f"[Verse 1]",
        f"{names[0]}在第一束光里醒来",
        f"{names[1]}把回声推向人海",
        f"我听见{names[2]}穿过墙外",
        f"也看见{names[3]}慢慢靠近舞台",
        "",
        "[Pre-Chorus]",
        f"把{theme}都写进节拍",
        "让每一次选择都变成现在",
        "",
        "[Chorus]",
        f"{names[0]}，{names[1]}，一起落下来",
        f"{names[2]}，{names[3]}，把夜晚点燃",
        "如果声音会替我们记载",
        "这一刻就不用再重来",
        "",
        "[Bridge]",
        f"四段旋律排成一片海",
        "我沿着按钮找到答案",
        "",
        "[Final Chorus]",
        f"{theme}",
        "在同一首歌里盛开",
    ])
    prompt = f"中文流行歌词，主题来自这些声音名字：{theme}。\n\n{lyrics}"
    return title, lyrics, f"{style}, Chinese lyrics, emotional chorus"


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.post("/api/generate")
def generate_song(request: GenerateRequest) -> dict:
    load_dotenv()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    audio_paths = [_safe_audio_path(item.file) for item in request.items]
    title, lyrics, style = build_song_metadata(request.items, request.style)

    mixed_path = OUTPUT_DIR / "mixed.mp3"
    mix_audios([str(path) for path in audio_paths], str(mixed_path))

    cover_clip_id = upload_audio(str(mixed_path))
    task = generate_cover(
        cover_clip_id=cover_clip_id,
        prompt=lyrics,
        style=style,
        title=title,
    )
    results = wait_for_results(task["clip_ids"])
    first = results[0]
    song_filename = f"{first.get('title', title)}_{first['id']}.mp3"
    local_song_path = OUTPUT_DIR / song_filename
    download_song(first["audio_url"], str(local_song_path))

    download_url: Optional[str] = None
    qr_path: Optional[str] = None
    if not request.skip_oss:
        download_url = upload_to_oss(str(local_song_path), object_key=f"suno_music/output/{song_filename}")
        qr_path = str(OUTPUT_DIR / "download_qr.png")
        generate_qr(download_url, qr_path)

    return {
        "title": title,
        "lyrics": lyrics,
        "style": style,
        "mixed_path": str(mixed_path),
        "song_path": str(local_song_path),
        "song_url": f"/output/{song_filename}",
        "download_url": download_url,
        "qr_path": qr_path,
    }
