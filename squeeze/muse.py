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


def _settings():
    """(env prefix, base URL, model) for the current backend; the key is read separately."""
    if backend() == "openai-compat":
        prefix, url, model = "OPENAI_COMPAT", None, "meta-models/muse-spark-open-1026"
    else:
        prefix, url, model = "META", "https://api.meta.ai/v1", "muse-spark-1.3"
    return prefix, os.environ.get(f"{prefix}_BASE_URL") or url, os.environ.get(f"{prefix}_MODEL", model)


def _config():
    prefix, url, model = _settings()
    key = os.environ.get(f"{prefix}_API_KEY")
    if not url or not key:
        hint = f"set {prefix}_API_KEY" + ("" if prefix == "META" else f" and {prefix}_BASE_URL")
        raise MuseError(hint + " in .env (see .env.example)")
    return url.rstrip("/"), key, model


def _request(prompt: str, image: bytes | None) -> str:
    url, key, model = _config()
    content = [{"type": "text", "text": prompt}]
    if image:
        b64 = base64.b64encode(image).decode()
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    try:
        r = httpx.post(f"{url}/chat/completions", timeout=60,
                       headers={"Authorization": f"Bearer {key}"},
                       json={"model": model, "temperature": 0, "messages": [{"role": "user", "content": content}]})
    except httpx.HTTPError as e:
        raise MuseError(f"could not reach {backend()}: {type(e).__name__}") from e
    body = r.text[:200].replace(key, "***")  # some servers echo the key back in error text
    if r.status_code != 200:
        raise MuseError(f"{backend()} returned {r.status_code}: {body}")
    try:
        text = r.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise MuseError(f"unexpected reply shape from {backend()}: {body}") from e
    if not isinstance(text, str):  # null on a refusal or an exhausted reasoning budget
        raise MuseError(f"no text in reply from {backend()}")
    return text


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
    """Send prompt (+ optional JPEG) and parse the JSON object in the reply.
    Returns (data, from_cache). Results are cached on disk by backend, model and
    content, so re-runs and the demo cost nothing extra."""
    name = backend()
    model = _settings()[2]
    key = hashlib.sha256(f"{name}\0{model}\0{prompt}".encode() + (image or b"")).hexdigest()
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
    if not isinstance(data, dict):
        raise MuseError("reply JSON is not an object")
    CACHE.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    os.replace(tmp, path)  # a run killed mid-write never leaves a broken cache file
    return data, False
