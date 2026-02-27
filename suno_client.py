"""Suno 网页自动化模块：通过 Playwright 控制本地浏览器上传音频并生成。"""

import os
import time
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright

def generate_cover_playwright(
    local_audio_path: str,
    prompt: str = "",
    style: str = "pop",
    title: str = "AI Generated Song",
    instrumental: bool = False,
    max_wait: int = 600,
) -> dict:
    """
    使用 Playwright 控制已启动并登录 Suno 的 Chrome 浏览器生成歌曲。
    
    依赖前置条件:
    关闭所有处于常规模式的 Chrome 窗口，通过以下命令启动调试模式:
    chrome.exe --remote-debugging-port=9222
    """
    debug_port = os.getenv("CHROME_DEBUG_PORT", "9222")
    ws_endpoint = f"http://127.0.0.1:{debug_port}"

    print(f"[Suno] 尝试连接本地 Chrome 浏览器 (端口 {debug_port})...")
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(ws_endpoint)
        except Exception as e:
            raise RuntimeError(f"无法连接到 Chrome，请确保已通过 --remote-debugging-port={debug_port} 启动并且未处于无头模式。详细错误: {e}")

        # 使用已有的上下文
        context = browser.contexts[0]
        page = context.new_page()

        try:
            print("[Suno] 访问 Suno Create 页面...")
            page.goto("https://suno.com/create", timeout=60000)
            page.wait_for_load_state("networkidle")

            # 1. 尝试触发上传音频 (Suno 的 Audio Upload)
            print("[Suno] 查找并点击上传音频入口...")
            # 注意: Web UI 经常变化，这里使用粗略的文本定位或通用输入框寻找
            # 方案A: 找到明确的 input type=file (如果有)
            # 方案B: 找到 Upload Audio 按钮点击后弹出文件选择
            try:
                # 给 Suno 一点时间渲染复杂组件
                time.sleep(3)
                
                # 在通常的 Create 面板寻找 Upload 按钮
                upload_btn = page.get_by_role("button", name="Upload Audio")
                if upload_btn.is_visible():
                    upload_btn.click()
                elif page.get_by_text("Upload Audio").is_visible():
                    page.get_by_text("Upload Audio").click()
                
                time.sleep(1)
                
                # 寻找文件上传 input 并填充路径
                file_input = page.locator('input[type="file"]')
                file_input.set_input_files(local_audio_path)
                print(f"[Suno] 已选择音频文件: {local_audio_path}")
                
                # 等待音频上传并处理完成 (进度条或 Uploading 消失)
                print("[Suno] 等待音频上传到 Suno 服务器...")
                time.sleep(5) # 具体要看文件大小，这里给个基础的等待，实际可能要更长时间
                # 可以尝试等待特定的 "Audio uploaded" 标志，这里先粗略等待
                # 假设需要最多 60 秒
                for _ in range(12):
                    if page.get_by_text("Uploaded").is_visible() or page.locator("audio").is_visible():
                        break
                    time.sleep(5)
                print("[Suno] 音频初步处理完成。")
            except Exception as e:
                print(f"[Suno] 警告：未能用常规方式上传音频，尝试其他途径。({e})")
                # 如果找不到，可以尝试截屏供用户调试
                page.screenshot(path="suno_upload_error.png")

            # 2. 填写提示词等表单信息
            print("[Suno] 填写创作参数...")
            # 若不是纯乐器，填写歌词/Prompt
            if not instrumental:
                lyrics_box = page.locator('textarea[placeholder*="lyrics" i]')
                if lyrics_box.is_visible():
                    lyrics_box.fill(prompt)
                else:
                    try:
                        page.get_by_placeholder("Enter your lyrics").fill(prompt)
                    except:
                        pass
            else:
                instr_toggle = page.get_by_text("Instrumental", exact=True)
                if instr_toggle.is_visible():
                    instr_toggle.click()

            # 填写风格 (Style)
            style_box = page.locator('input[placeholder*="style" i]')
            if style_box.is_visible():
                style_box.fill(style)
            else:
                try:
                    page.get_by_placeholder("Enter style of music").fill(style)
                except:
                    pass

            # 填写标题 (Title)
            title_box = page.locator('input[placeholder*="title" i]')
            if title_box.is_visible():
                title_box.fill(title)

            # 3. 提交生成
            print("[Suno] 点击 Generate 生成...")
            # 寻找类似 "Create" 或 "Extend" 或 "Generate" 的主要按钮
            generate_btn = page.get_by_role("button", name="Create")
            if not generate_btn.is_visible():
                generate_btn = page.get_by_role("button", name="Generate")
            generate_btn.click()

            print(f"[Suno] 任务已提交，等待生成结果（可能需要几分钟）...")

            # 4. 监听网络请求或 DOM 树寻找新出炉的音乐
            # 由于这部分比较看 UI，我尝试轮询查找第一首生成出来的包含下载链接的项。
            elapsed = 0
            poll_interval = 5
            found_audio_url = None
            song_id = str(int(time.time())) # 后备用的 ID

            while elapsed < max_wait:
                time.sleep(poll_interval)
                elapsed += poll_interval

                # 寻找下载按钮或 audio 标签中的 src
                # 此处极度依赖 DOM 结构，这是一个探测范例
                # 比如寻找页面中新出现的带有 blob: 或者 /api/ 的 .mp3 链接
                
                # 尝试点击生成结果列表的第一项
                # play_buttons = page.get_by_role("button", name="Play")
                # if play_buttons.count() > 0: ...

                # 最保险的做法：拦截包含 /audio/ 或者 .mp3 的网络请求，或者在控制台查找
                audio_tags = page.locator("audio")
                if audio_tags.count() > 0:
                    src = audio_tags.first.get_attribute("src")
                    if src and ("suno" in src or "cdn" in src or ".mp3" in src):
                        found_audio_url = src
                        break
                
                # 若能从 DOM 下载菜单找到按钮获取链接
                download_menu = page.get_by_text("Download Audio")
                if download_menu.is_visible():
                    # 说明可能已经生成完了并且用户/脚本点开了菜单
                    pass
                    
                if elapsed % 30 == 0:
                    print(f"[Suno] 仍在生成中... ({elapsed}s)")

            if found_audio_url:
                print(f"[Suno] 生成完成！捕获到音频 URL: {found_audio_url}")
                return {
                    "audio_url": found_audio_url,
                    "id": song_id,
                    "title": title
                }
            else:
                page.screenshot(path="suno_timeout_error.png")
                raise TimeoutError(f"Suno 生成超时或未能抓取到音频链接，截图已保存。")
                
        finally:
            page.close()
            browser.disconnect()

def download_song(audio_url: str, output_path: str) -> str:
    """下载生成的歌曲到本地。"""
    print(f"[Suno] 正在下载: {audio_url}")
    
    # 因为有可能是经过 Cloudflare 保护的，如果 requests 失败，也可以考虑用 playwright 下载。
    # 这里先尝试普通 requests
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}
    resp = requests.get(audio_url, stream=True, headers=headers)
    resp.raise_for_status()

    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    print(f"[Suno] 歌曲已下载: {output_path}")
    return output_path
