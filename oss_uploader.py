"""阿里云 OSS 上传模块：上传文件并生成公开下载链接。"""

import os
from pathlib import Path

import oss2
from typing import Optional

import requests

def _fallback_upload(file_path: Path) -> str:
    print(f"[Fallback Upload] 正在上传: {file_path.name}")
    try:
        with open(file_path, "rb") as f:
            resp = requests.post("https://tmpfiles.org/api/v1/upload", files={"file": f})
        resp.raise_for_status()
        url = resp.json().get("data", {}).get("url")
        if not url:
            raise RuntimeError(f"未能从 tmpfiles.org 获取有效链接, 返回了: {resp.text}")
        
        # 转换页面 URL 为直接下载 URL：https://tmpfiles.org/123/file.txt -> https://tmpfiles.org/dl/123/file.txt
        download_url = url.replace("https://tmpfiles.org/", "https://tmpfiles.org/dl/")
        print(f"[Fallback Upload] 上传成功，临时下载链接: {download_url}")
        return download_url
    except Exception as e:
        raise RuntimeError(f"使用 tmpfiles.org 临时上传失败: {e}")

def upload_to_oss(
    file_path: str,
    object_key: Optional[str] = None,
    access_key_id: Optional[str] = None,
    access_key_secret: Optional[str] = None,
    bucket_name: Optional[str] = None,
    endpoint: Optional[str] = None,
) -> str:
    """
    上传文件到阿里云 OSS 并返回公开下载链接。

    Args:
        file_path: 本地文件路径
        object_key: OSS 对象键名，为空则使用文件名
        access_key_id: AccessKey ID，为空则从环境变量读取
        access_key_secret: AccessKey Secret，为空则从环境变量读取
        bucket_name: Bucket 名称，为空则从环境变量读取
        endpoint: OSS Endpoint，为空则从环境变量读取

    Returns:
        文件的公开下载 URL
    """
    access_key_id = access_key_id or os.getenv("OSS_ACCESS_KEY_ID")
    access_key_secret = access_key_secret or os.getenv("OSS_ACCESS_KEY_SECRET")
    bucket_name = bucket_name or os.getenv("OSS_BUCKET_NAME")
    endpoint = endpoint or os.getenv("OSS_ENDPOINT", "oss-cn-hangzhou.aliyuncs.com")

    if not all([access_key_id, access_key_secret, bucket_name]) or access_key_id == "your_key_id":
        print("[警告] 尚未配置真实的阿里云 OSS 秘钥！为了能生成手机可扫的二维码，系统会自动将您的音频上传到免费临时托管平台 (file.io)。")
        print("       (注：file.io 链接在下载一次或在固定时长后会自动失效，如果您需要长久保存请配好 .env 中的 OSS 参数)")
        return _fallback_upload(Path(file_path))

    auth = oss2.Auth(access_key_id, access_key_secret)
    bucket = oss2.Bucket(auth, endpoint, bucket_name)

    path = Path(file_path)
    if object_key is None:
        object_key = f"suno_music/{path.name}"

    print(f"[OSS] 正在上传: {path.name} -> {object_key}")
    bucket.put_object_from_file(object_key, str(path))

    # 设置公共读权限
    bucket.put_object_acl(object_key, oss2.OBJECT_ACL_PUBLIC_READ)

    url = f"https://{bucket_name}.{endpoint}/{object_key}"
    print(f"[OSS] 上传完成，下载链接: {url}")
    return url
