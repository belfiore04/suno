"""二维码生成模块：将 URL 编码为二维码图片并在终端显示。"""

from pathlib import Path

import qrcode


def generate_qr(url: str, output_path: str = "qrcode.png") -> str:
    """
    生成二维码图片并在终端打印 ASCII 版本。

    Args:
        url: 要编码的 URL
        output_path: 二维码图片保存路径

    Returns:
        二维码图片文件路径
    """
    # 生成二维码图片
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img.save(output_path)
    print(f"[QR] 二维码已保存: {output_path}")

    # 终端打印 ASCII 二维码
    print("\n[QR] 扫描以下二维码下载音频:")
    qr.print_ascii(invert=True)

    return output_path
