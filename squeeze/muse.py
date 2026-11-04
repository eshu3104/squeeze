"""The one place Squeeze talks to Meta's models.

Backends (SQUEEZE_BACKEND):
  meta-api       Muse Spark on the Meta Model API      (META_API_KEY; META_BASE_URL, META_MODEL optional)
  openai-compat  Muse Spark Open on Baseten or Modal   (OPENAI_COMPAT_BASE_URL, OPENAI_COMPAT_API_KEY, OPENAI_COMPAT_MODEL)
  mock           offline stand-in for tests and dry runs; never used for real results

Both real backends speak the OpenAI-style chat-completions format (the Meta Model
API documents an OpenAI-compatible /chat/completions endpoint at api.meta.ai/v1).
shortcut: the image part uses OpenAI's base64 image_url form; confirm with one call.
"""
import base64
import hashlib
import json
import os
import re
from pathlib import Path

import httpx

def _load_dotenv(path=Path(".env")):
    """Read KEY=value lines from ./.env; variables already set in the shell win."""
    if path.is_file():
        for line in path.read_text().splitlines():
            key, sep, value = line.strip().partition("=")
            if sep and not key.startswith("#") and value:
                os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_dotenv()
CACHE = Path(os.environ.get("SQUEEZE_CACHE", ".squeeze-cache"))


class MuseError(RuntimeError):
    pass


def backend() -> str:
    return os.environ.get("SQUEEZE_BACKEND", "meta-api")


def _config():
    if backend() == "openai-compat":
        prefix, default_url, default_model = "OPENAI_COMPAT", None, "meta-models/muse-spark-open-1026"
    else:
        prefix, default_url, default_model = "META", "https://api.meta.ai/v1", "muse-spark-1.3"
    url = os.environ.get(f"{prefix}_BASE_URL") or default_url
    key = os.environ.get(f"{prefix}_API_KEY")
    if not url or not key:
        raise MuseError(f"set {prefix}_API_KEY" + ("" if default_url else f" and {prefix}_BASE_URL") + " in .env (see .env.example)")
    return url.rstrip("/"), key, os.environ.get(f"{prefix}_MODEL", default_model)


def _request(prompt: str, image: bytes | None) -> str:
    url, key, model = _config()
    content = [{"type": "text", "text": prompt}]
    if image:
        b64 = base64.b64encode(image).decode()
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
    try:
        r = httpx.post(f"{url}/chat/completions", timeout=60,
                       headers={"Authorization": f"Bearer {key}"},
                       json={"model": model, "temperature": 0, "messages": [{"role": "user", "content": content}]})
    except httpx.HTTPError as e:
        raise MuseError(f"could not reach {backend()}: {type(e).__name__}") from e
    if r.status_code != 200:
        raise MuseError(f"{backend()} returned {r.status_code}: {r.text[:200]}")
    try:
        return r.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise MuseError(f"unexpected reply shape from {backend()}: {r.text[:200]}") from e


def _mock(prompt: str, image: bytes | None) -> str:
    if image is None:
        return '{"answers": []}'
    from io import BytesIO

    from PIL import Image

    colors = Image.open(BytesIO(image)).convert("RGB").getcolors(maxcolors=16)
    if colors is not None and len(colors) <= 2:
        return '{"class": "decorative", "description": "plain graphic"}'
    return '{"class": "informative", "description": "[mock] chart or figure"}'


def ask_json(prompt: str, image: bytes | None = None) -> tuple[dict, bool]:
    """Send prompt (+ optional PNG) and parse the JSON object in the reply.
    Returns (data, from_cache). Results are cached on disk by content hash, so
    re-runs and the demo cost nothing extra."""
    name = backend()
    key = hashlib.sha256(name.encode() + prompt.encode() + (image or b"")).hexdigest()
    path = CACHE / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text()), True
    reply = _mock(prompt, image) if name == "mock" else _request(prompt, image)
    m = re.search(r"\{.*\}", reply, re.S)
    if not m:
        raise MuseError(f"no JSON in reply: {reply[:200]}")
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise MuseError(f"bad JSON in reply: {e}") from e
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return data, False
