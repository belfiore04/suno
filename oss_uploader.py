"""阿里云 OSS 上传模块：上传文件并生成公开下载链接。"""

import os
from pathlib import Path

import oss2


def upload_to_oss(
    file_path: str,
    object_key: str | None = None,
    access_key_id: str | None = None,
    access_key_secret: str | None = None,
    bucket_name: str | None = None,
    endpoint: str | None = None,
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

    if not all([access_key_id, access_key_secret, bucket_name]):
        raise ValueError("缺少 OSS 配置，请设置环境变量或传入参数")

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
