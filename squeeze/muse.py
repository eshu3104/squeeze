"""The one place Squeeze talks to Meta's models.

Backends (SQUEEZE_BACKEND):
  meta-api       Muse Spark on the Meta Model API      (META_BASE_URL, META_API_KEY, META_MODEL)
  openai-compat  Muse Spark Open on Baseten or Modal   (OPENAI_COMPAT_BASE_URL, OPENAI_COMPAT_API_KEY, OPENAI_COMPAT_MODEL)
  mock           offline stand-in for tests and dry runs; never used for real results

Both real backends speak the OpenAI-style chat-completions format.
shortcut: assumes the Meta Model API accepts that format with base64 image URLs;
confirm with one call against Meta's quickstart and adjust _request() if not.
"""
import base64
import hashlib
import json
import os
import re
from pathlib import Path

import httpx

CACHE = Path(os.environ.get("SQUEEZE_CACHE", ".squeeze-cache"))


class MuseError(RuntimeError):
    pass


def backend() -> str:
    return os.environ.get("SQUEEZE_BACKEND", "meta-api")


def _config():
    if backend() == "openai-compat":
        prefix, default_model = "OPENAI_COMPAT", "meta-models/muse-spark-open-1026"
    else:
        prefix, default_model = "META", "muse-spark"
    url, key = os.environ.get(f"{prefix}_BASE_URL"), os.environ.get(f"{prefix}_API_KEY")
    if not url or not key:
        raise MuseError(f"set {prefix}_BASE_URL and {prefix}_API_KEY (see .env.example)")
    return url.rstrip("/"), key, os.environ.get(f"{prefix}_MODEL", default_model)


def _request(prompt: str, image: bytes | None) -> str:
    url, key, model = _config()
    content = [{"type": "text", "text": prompt}]
    if image:
        b64 = base64.b64encode(image).decode()
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
    r = httpx.post(f"{url}/chat/completions", timeout=60,
                   headers={"Authorization": f"Bearer {key}"},
                   json={"model": model, "temperature": 0, "messages": [{"role": "user", "content": content}]})
    if r.status_code != 200:
        raise MuseError(f"{backend()} returned {r.status_code}: {r.text[:200]}")
    return r.json()["choices"][0]["message"]["content"]


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
