"""Local web app: one page, one endpoint. Run with `uvicorn squeeze.app:app`."""
import tempfile
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from squeeze.core import compress

app = FastAPI(title="Squeeze")
PAGE = Path(__file__).parent / "static" / "index.html"


@app.get("/")
def index():
    return FileResponse(PAGE)


@app.post("/compress")
def compress_endpoint(file: UploadFile | None = File(None), url: str = Form(""),
                      images: str = Form("describe"), fidelity: str = Form("")):
    if images not in ("describe", "none"):
        raise HTTPException(400, "images must be describe or none")
    with tempfile.TemporaryDirectory() as tmp:
        if file and file.filename:
            source = str(Path(tmp) / Path(file.filename).name)
            Path(source).write_bytes(file.file.read())
            shown = file.filename
        elif url.startswith(("http://", "https://")):
            source = shown = url
        else:
            raise HTTPException(400, "send a file or an http(s) URL")
        try:
            result = compress(source, images=images, fidelity=bool(fidelity))
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
    result.stats["source"] = shown
    return asdict(result)
