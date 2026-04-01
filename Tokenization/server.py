import os
from typing import List, Optional

import torch
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_ID = os.getenv("MODEL_ID", "google/gemma-3-1b-it")
HF_TOKEN = os.getenv("HF_TOKEN")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def pick_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def pick_dtype(device: torch.device) -> torch.dtype:
    if device.type == "cuda":
        return torch.bfloat16
    return torch.float32


device = pick_device()


tokenizer = AutoTokenizer.from_pretrained(
    MODEL_ID,
    token=HF_TOKEN,
    use_fast=True,
)

model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    token=HF_TOKEN,
    dtype=pick_dtype(device),
)
model.to(device)
model.eval()


class TokenizeRequest(BaseModel):
    prompt: str


class StepRequest(BaseModel):
    prompt: str
    generated_text: str = ""
    temperature: float = 0.9
    top_k: int = 8


class TokenizeResponse(BaseModel):
    tokens: List[str]
    token_ids: List[int]


class StepResponse(BaseModel):
    next_token: str
    generated_text: str
    generated_tokens: List[str]
    top_probs: List[dict]
    eos: bool


@app.get("/info")
async def info():
    num_params = sum(p.numel() for p in model.parameters())
    special_tokens = {k: str(v) for k, v in tokenizer.special_tokens_map.items()}
    return {
        "model": {
            "id": MODEL_ID,
            "architecture": type(model).__name__,
            "device": str(device),
            "dtype": str(model.dtype).replace("torch.", ""),
            "num_parameters": num_params,
        },
        "tokenizer": {
            "class": type(tokenizer).__name__,
            "vocab_size": tokenizer.vocab_size,
            "model_max_length": tokenizer.model_max_length,
            "special_tokens": special_tokens,
        },
    }


@app.get("/vocab")
async def vocab_endpoint():
    vocab = tokenizer.get_vocab()
    entries = sorted(vocab.items(), key=lambda x: x[1])
    return {"vocab": [{"token": t, "id": i} for t, i in entries]}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": MODEL_ID,
        "device": str(device),
    }


@app.get("/")
async def root():
    return {
        "message": "LLM inference API is running.",
        "endpoints": ["/health", "/tokenize", "/step"],
    }


@app.post("/tokenize", response_model=TokenizeResponse)
async def tokenize_endpoint(payload: TokenizeRequest):
    encoded = tokenizer(
        payload.prompt,
        add_special_tokens=False,
        return_tensors=None,
    )
    token_ids = encoded["input_ids"]
    tokens = tokenizer.convert_ids_to_tokens(token_ids)
    return TokenizeResponse(tokens=tokens, token_ids=token_ids)


@app.post("/step", response_model=StepResponse)
async def step_endpoint(payload: StepRequest):
    prompt = payload.prompt
    generated_text = payload.generated_text or ""
    temperature = max(payload.temperature, 0.0)
    top_k = max(1, min(payload.top_k, 20))
    greedy = temperature == 0.0

    prompt_ids = tokenizer(
        prompt,
        add_special_tokens=False,
        return_tensors=None,
    )["input_ids"]
    gen_ids = tokenizer(
        generated_text,
        add_special_tokens=False,
        return_tensors=None,
    )["input_ids"]

    input_ids = torch.tensor([prompt_ids + gen_ids], device=device)

    if tokenizer.bos_token_id is not None:
        bos = torch.tensor([[tokenizer.bos_token_id]], device=device)
        input_ids = torch.cat([bos, input_ids], dim=1)

    with torch.no_grad():
        outputs = model(input_ids=input_ids)
        logits = outputs.logits[:, -1, :]
        if greedy:
            probs = torch.softmax(logits, dim=-1)
            next_id = torch.argmax(logits, dim=-1, keepdim=True)
        else:
            logits = logits / temperature
            probs = torch.softmax(logits, dim=-1)
            next_id = torch.multinomial(probs, num_samples=1)
    next_id_int = next_id.item()
    next_token = tokenizer.convert_ids_to_tokens([next_id_int])[0]

    eos = False
    if tokenizer.eos_token_id is not None and next_id_int == tokenizer.eos_token_id:
        eos = True
    if next_token == "<end_of_turn>":
        eos = True

    updated_gen_ids = gen_ids + [next_id_int]
    generated_only = tokenizer.decode(updated_gen_ids, skip_special_tokens=True)
    generated_tokens = tokenizer.convert_ids_to_tokens(updated_gen_ids)

    top_probs = []
    top_vals, top_ids = torch.topk(probs, k=top_k, dim=-1)
    for val, idx in zip(top_vals[0], top_ids[0]):
        token = tokenizer.convert_ids_to_tokens([idx.item()])[0]
        top_probs.append({"token": token, "prob": float(val)})

    return StepResponse(
        next_token=next_token,
        generated_text=generated_only,
        generated_tokens=generated_tokens,
        top_probs=top_probs,
        eos=eos,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
