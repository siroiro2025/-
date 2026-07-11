"""ローカル Qwen-Image-Edit-2511 を簡易 HTTP API として公開するサーバー。

tomari-auto の Node バックエンド (src/qwen.js) から呼び出される。

  POST /edit
    { "prompt": str, "images": [base64, ...], "width": int, "height": int,
      "steps": int, "seed": int }
    -> { "mimeType": "image/png", "data": base64 }

  GET /health -> { "status": "ok", "model": ... }

起動:
  pip install -r tools/requirements.txt
  python tools/qwen_server.py --port 8000

環境変数:
  QWEN_MODEL    モデルID (既定: Qwen/Qwen-Image-Edit-2511)
  QWEN_OFFLOAD  "1" で CPU オフロード有効 (VRAM が足りない場合)
"""

import argparse
import base64
import io
import os

import torch
from fastapi import FastAPI, HTTPException
from PIL import Image
from pydantic import BaseModel

MODEL_ID = os.environ.get("QWEN_MODEL", "Qwen/Qwen-Image-Edit-2511")

app = FastAPI(title="qwen-image-edit-server")
pipe = None


def load_pipeline():
    global pipe
    if pipe is not None:
        return pipe
    try:
        from diffusers import QwenImageEditPlusPipeline as Pipeline
    except ImportError:
        # 古い diffusers 向けフォールバック
        from diffusers import QwenImageEditPipeline as Pipeline

    print(f"loading {MODEL_ID} ...")
    pipe = Pipeline.from_pretrained(MODEL_ID, torch_dtype=torch.bfloat16)
    if os.environ.get("QWEN_OFFLOAD") == "1":
        pipe.enable_model_cpu_offload()
    else:
        pipe.to("cuda")
    pipe.set_progress_bar_config(disable=True)
    print("model ready")
    return pipe


class EditRequest(BaseModel):
    prompt: str
    images: list[str] = []
    width: int = 1024
    height: int = 1024
    steps: int = 40
    seed: int | None = None


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_ID, "loaded": pipe is not None}


@app.post("/edit")
def edit(req: EditRequest):
    p = load_pipeline()

    try:
        inputs = [
            Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
            for b64 in req.images
        ]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid image data: {e}")

    generator = None
    if req.seed is not None:
        generator = torch.Generator(device="cpu").manual_seed(req.seed)

    kwargs = dict(
        prompt=req.prompt,
        negative_prompt=" ",
        num_inference_steps=req.steps,
        true_cfg_scale=4.0,
        guidance_scale=1.0,
        num_images_per_prompt=1,
        generator=generator,
        height=req.height,
        width=req.width,
    )
    if inputs:
        kwargs["image"] = inputs

    with torch.inference_mode():
        result = p(**kwargs)

    out = result.images[0]
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return {
        "mimeType": "image/png",
        "data": base64.b64encode(buf.getvalue()).decode("ascii"),
    }


if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--preload", action="store_true", help="起動時にモデルを読み込む")
    args = parser.parse_args()

    if args.preload:
        load_pipeline()

    uvicorn.run(app, host=args.host, port=args.port)
