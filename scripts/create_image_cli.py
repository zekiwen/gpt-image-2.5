import argparse
import base64
import json
import mimetypes
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path


# 支持的模型及其质量档位（gpt-image-2 官方支持 high；2.5 系列新增 xhigh/max）
MODEL_QUALITY = {
    "gpt-image-2": ["auto", "low", "medium", "high"],
    "gpt-image-2.5-sunburst": ["auto", "low", "medium", "high", "xhigh", "max"],
    "gpt-image-2.5-flare": ["auto", "low", "medium", "high", "xhigh", "max"],
}

# 单价(美元, 每 1M tokens) — 与 image_api.py 一致
PRICING = {
    "input_image":  8.00,
    "input_text":   5.00,
    "output_image": 30.00,
}


class ExchangeRate:
    """USD→CNY 汇率：每日拉取 open.er-api.com 更新 .env；失败回退 .env 旧值，再兜底 fallback。

    resolve() 优先级：环境变量 USD_TO_CNY > .env 当日缓存 > 实时拉取(回写 .env) > .env 旧值 > fallback
    """

    def __init__(self, env_path=None, api_url="https://open.er-api.com/v6/latest/USD", fallback=7.0):
        self.env_path = Path(env_path) if env_path else Path(__file__).with_name(".env")
        self.api_url = api_url
        self.fallback = fallback

    def read_env(self) -> dict:
        """解析 .env（简单 key=value 行，# 注释）"""
        cfg = {}
        if self.env_path.exists():
            for line in self.env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    cfg[k.strip()] = v.strip()
        return cfg

    def write_env(self, rate: float, date_str: str):
        self.env_path.write_text(
            "# USD→CNY 汇率：每日首次运行自动拉取 open.er-api.com 并更新此文件；\n"
            "# 拉取失败时回退使用这里的值。要固定汇率请设置环境变量 USD_TO_CNY。\n"
            f"USD_TO_CNY={rate}\n"
            f"RATE_UPDATED={date_str}\n",
            encoding="utf-8")

    def fetch(self):
        """拉取实时汇率，失败返回 None（汇率查询失败不应影响出图，静默降级）"""
        try:
            with urllib.request.urlopen(self.api_url, timeout=10) as resp:
                return float(json.loads(resp.read().decode("utf-8"))["rates"]["CNY"])
        except Exception:
            return None

    def resolve(self) -> tuple:
        """返回 (汇率, 来源描述)"""
        override = os.getenv("USD_TO_CNY")
        if override:
            try:
                return float(override), "环境变量"
            except ValueError:
                pass
        cfg = self.read_env()
        today = datetime.now().strftime("%Y-%m-%d")
        if cfg.get("RATE_UPDATED") == today:
            try:
                return float(cfg["USD_TO_CNY"]), ".env 当日缓存"
            except (KeyError, ValueError):
                pass
        rate = self.fetch()
        if rate:
            self.write_env(rate, today)
            return rate, "实时拉取"
        if cfg.get("USD_TO_CNY"):
            try:
                return float(cfg["USD_TO_CNY"]), ".env 回退"
            except ValueError:
                pass
        return self.fallback, "内置默认"


class GPTImageClient:
    """OpenAI Images API 客户端：文生图 generate（JSON）/ 图生图 edit（multipart image[]）"""

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", timeout: float = 600.0):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ---- HTTP ----

    def _http(self, url, method="GET", headers=None, data=None, timeout=None) -> bytes:
        """标准库 HTTP 请求，返回响应体；HTTP 错误时抛出带 API 错误信息的 RuntimeError"""
        req = urllib.request.Request(url, data=data, method=method)
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            try:
                msg = json.loads(body).get("error", {}).get("message", body)
            except Exception:
                msg = body
            raise RuntimeError(f"HTTP {e.code}: {msg}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"网络错误: {e.reason}") from e

    def _encode_multipart(self, fields: dict, files: list) -> tuple:
        """手工构造 multipart/form-data。files: [(字段名, 文件名, 内容, mime)]"""
        boundary = "----zc" + uuid.uuid4().hex
        parts = []
        for name, value in fields.items():
            parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'
                .encode("utf-8"))
        for name, filename, content, mime in files:
            parts.append(
                (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
                 f'filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n').encode("utf-8")
                + content + b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode("utf-8"))
        return b"".join(parts), f"multipart/form-data; boundary={boundary}"

    # ---- API ----

    def generate(self, payload: dict) -> dict:
        """POST /images/generations（JSON body），返回解析后的 JSON"""
        raw = self._http(self.base_url + "/images/generations", method="POST", headers={
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }, data=json.dumps(payload).encode("utf-8"))
        return json.loads(raw.decode("utf-8"))

    def edit(self, payload: dict, files: list) -> dict:
        """POST /images/edits（multipart：普通字段 + 文件，官方统一文件字段名 image[]）"""
        body, content_type = self._encode_multipart(payload, files)
        raw = self._http(self.base_url + "/images/edits", method="POST", headers={
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": content_type,
        }, data=body)
        return json.loads(raw.decode("utf-8"))

    # ---- 图片 IO ----

    @staticmethod
    def load_image_bytes(uri: str) -> tuple:
        """从本地文件或 URL 加载图片，返回 (bytes, ext, mime)"""
        if uri.startswith(("http://", "https://")):
            try:
                with urllib.request.urlopen(uri, timeout=30) as resp:
                    content = resp.read()
                    ctype = resp.headers.get("content-type")
            except urllib.error.URLError as e:
                raise RuntimeError(f"下载参考图失败 {uri}: {e}") from e
            ext = Path(uri).suffix.lstrip(".") or "png"
            mime = ctype or f"image/{ext}"
            if ext.lower() in ("jpg", "jpeg"):
                mime = "image/jpeg"
            return content, ext, mime
        else:
            path = Path(uri)
            if not path.exists():
                raise FileNotFoundError(f"文件不存在: {uri}")
            with open(path, "rb") as f:
                content = f.read()
            ext = path.suffix.lstrip(".") or "png"
            mime = mimetypes.guess_type(path)[0] or f"image/{ext}"
            return content, ext, mime

    @staticmethod
    def save_image(image_data, output_path: str):
        """保存 data URI 格式的图片（GPT image 模型固定返回 base64）"""
        if not (isinstance(image_data, str) and image_data.startswith("data:image/")):
            raise ValueError("无法识别的图片数据格式（GPT image 模型应返回 base64）")
        header, b64 = image_data.split(",", 1)
        mime = header.split(";")[0].split(":")[1]
        ext = mimetypes.guess_extension(mime) or ".png"
        output_path = Path(output_path)
        if not output_path.suffix:
            output_path = output_path.with_suffix(ext)
        with open(output_path, "wb") as f:
            f.write(base64.b64decode(b64))
        print(f"✅ 图片已保存: {output_path}")


def auto_filename(fmt: str = "png"):
    ext = "jpg" if fmt == "jpeg" else fmt
    return f"output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"


def calc_cost_cny(usage: dict, rate: float) -> float:
    """按真实 usage 算人民币, 精度到分。input 拆 image/text 两档, output 全按 image 单价。"""
    details_in  = (usage or {}).get("input_tokens_details")  or {}
    details_out = (usage or {}).get("output_tokens_details") or {}
    img_in  = details_in.get("image_tokens", 0)
    txt_in  = details_in.get("text_tokens",  0)
    img_out = details_out.get("image_tokens", 0)
    usd = (
        img_in  / 1_000_000 * PRICING["input_image"]
        + txt_in  / 1_000_000 * PRICING["input_text"]
        + img_out / 1_000_000 * PRICING["output_image"]
    )
    return round(usd * rate, 2)


def main():
    parser = argparse.ArgumentParser(description="调用 OpenAI 图像生成 API")
    parser.add_argument("--prompt", required=True, help="提示词（必填）")
    parser.add_argument("--image", action="append", help="参考图（本地路径或 URL），可多次使用，最多16张")
    parser.add_argument("--size", default="auto", help="尺寸，如 1024x1024 或 auto")
    parser.add_argument("--model", default="gpt-image-2.5-sunburst", choices=sorted(MODEL_QUALITY),
                        help="模型，默认 gpt-image-2.5-sunburst")
    parser.add_argument("--quality", default="medium",
                        choices=["auto", "low", "medium", "high", "xhigh", "max"],
                        help="质量，默认 medium；high 及以上档位仅在用户明确要求时使用")
    parser.add_argument("--format", choices=["png", "jpeg", "webp"],
                        help="输出格式 png/jpeg/webp，默认不传（API 默认 png）")
    parser.add_argument("--compression", type=int,
                        help="jpeg/webp 压缩率 0-100，需配合 --format jpeg/webp")
    parser.add_argument("--background", choices=["transparent", "opaque", "auto"],
                        help="背景，transparent 需 png/webp 格式")
    parser.add_argument("--save", help="保存路径，默认自动生成")
    args = parser.parse_args()

    # 参数校验
    if not args.prompt.strip():
        print("❌ prompt 不能为空", file=sys.stderr)
        sys.exit(1)
    if args.size != "auto" and not re.fullmatch(r"\d{3,4}x\d{3,4}", args.size):
        print(f"❌ size 格式应为 'auto' 或像素值如 1024x1024, 收到 {args.size!r}", file=sys.stderr)
        sys.exit(1)
    if args.image and len(args.image) > 16:
        print("❌ 参考图最多 16 张, 收到 %d 张" % len(args.image), file=sys.stderr)
        sys.exit(1)
    allowed_quality = MODEL_QUALITY[args.model]
    if args.quality not in allowed_quality:
        print(f"❌ 模型 {args.model} 的 quality 仅支持 {'/'.join(allowed_quality)}, 收到 {args.quality!r}",
              file=sys.stderr)
        sys.exit(1)
    if args.background == "transparent" and args.format == "jpeg":
        print("❌ background=transparent 需要 png 或 webp 格式", file=sys.stderr)
        sys.exit(1)
    if args.compression is not None and args.format not in ("jpeg", "webp"):
        print("❌ --compression 仅在 --format jpeg/webp 时有效", file=sys.stderr)
        sys.exit(1)
    if args.compression is not None and not 0 <= args.compression <= 100:
        print(f"❌ --compression 取值 0-100, 收到 {args.compression}", file=sys.stderr)
        sys.exit(1)
    quality = args.quality

    # 环境变量
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ 请设置环境变量 OPENAI_API_KEY", file=sys.stderr)
        sys.exit(1)
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    client = GPTImageClient(api_key, base_url)

    t0 = time.time()
    print(f"⏱ 开始请求: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 构建请求参数（与 image_api 一致；output_format/output_compression/background 仅在显式传入时下发）
    payload = {
        "prompt": args.prompt,
        "size": args.size,
        "quality": quality,
        "n": 1,
        "model": args.model,
    }
    if args.format:
        payload["output_format"] = args.format
    if args.compression is not None:
        payload["output_compression"] = args.compression
    if args.background:
        payload["background"] = args.background

    try:
        if args.image:
            # 图生图：支持多张图片，multipart 上传
            if len(args.image) > 16:
                print("⚠️ 最多 16 张参考图，将只取前 16 张", file=sys.stderr)
                args.image = args.image[:16]

            image_list = []
            for img_path in args.image:
                content, ext, mime = GPTImageClient.load_image_bytes(img_path)
                image_list.append((f"image.{ext}", content, mime))
            # 官方 API 参考 multipart 文件字段统一为 image[]（单图/多图相同）
            files = [("image[]", fname, content, mime) for fname, content, mime in image_list]
            response = client.edit(payload, files)
        else:
            # 文生图
            response = client.generate(payload)

    except Exception as e:
        print(f"❌ API 调用失败: {e}", file=sys.stderr)
        sys.exit(1)

    if not response.get("data"):
        print("❌ 服务端未返回图片", file=sys.stderr)
        sys.exit(1)

    elapsed = time.time() - t0
    print(f"⏱ 结束请求: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (耗时 {elapsed:.1f}s)")

    # 费用: 按响应 usage 实算人民币 (中转站没返回 usage 时显示 0.0)；汇率来源见输出标注
    usage = response.get("usage") or {}
    rate, rate_src = ExchangeRate().resolve()
    print(f"💰 本次费用: ¥{calc_cost_cny(usage, rate)}（汇率 {rate}，{rate_src}）")

    img = response["data"][0]
    if not img.get("b64_json"):
        print("❌ 响应中没有 b64_json（GPT image 模型固定返回 base64）", file=sys.stderr)
        sys.exit(1)
    image_content = f"data:image/{args.format or 'png'};base64,{img['b64_json']}"

    save_path = args.save or os.path.join("GPT-Image", auto_filename(args.format or "png"))
    # 确保保存目录存在（默认 GPT-Image/ 在当前工作目录；画板交付队列在 GPT-Image/sketch_io/）
    save_dir = os.path.dirname(save_path)
    if save_dir and not os.path.exists(save_dir):
        os.makedirs(save_dir, exist_ok=True)
    try:
        GPTImageClient.save_image(image_content, save_path)
    except Exception as e:
        print(f"❌ 保存图片失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
