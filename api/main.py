"""HTTP API for the playground.

POST /api/run     run a scenario on both agents at once; streams NDJSON events
POST /api/check   run every guard layer on a piece of text, layer by layer
GET  /api/scenarios, /api/stats, /api/events, /api/health
"""

import json
import logging
import time

import anyio
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from demo.run import run_protected, run_unprotected
from demo.scenarios import BY_ID, SCENARIOS, custom_scenario
from dwarpal import config, embeddings
from dwarpal.cache import get_cache
from dwarpal.checks import guards
from dwarpal.store import get_store


logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("uvicorn.error")

app = FastAPI(title="Dwarpal API", version="0.1.0",
              description="Security gateway for MCP agents: live attack playground.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["content-type"],
)

STARTED = time.time()


def client_ip(request: Request):
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")


def rate_limit(request: Request, bucket, limit):
    if not get_cache().hit_window(f"{bucket}:{client_ip(request)}", limit, 60):
        raise HTTPException(429, "Too many runs in a minute. The demo runs on free tiers, please wait a moment.")


# ---------------------------------------------------------

@app.get("/api/health")
def health():
    store = get_store()
    return {
        "status": "ok",
        "uptime_s": round(time.time() - STARTED),
        "agent_model": config.GROQ_MODEL,
        "live_models": guards.groq_available(),
        "store": store.backend,
        "cache": get_cache().name,
        "embeddings": embeddings.backend_name(),
    }


@app.get("/api/scenarios")
def scenarios():
    return [
        {"id": s.id, "title": s.title, "language": s.language, "attack_type": s.attack_type,
         "explain": s.explain, "meaning": s.meaning, "user_request": s.user_request,
         "attack_text": s.weather_description if s.weather_description != BY_ID["clean"].weather_description
         else s.result_suffix, "where": "tool description" if s.result_suffix == "" else "tool result",
         "rug_pull": s.rug_pull}
        for s in SCENARIOS
    ]


class RunRequest(BaseModel):
    scenario: str = Field(default="clean", max_length=40)
    custom_attack: str | None = Field(default=None, max_length=1500)


@app.post("/api/run")
async def run(payload: RunRequest, request: Request):
    """Both agents run concurrently; each line is {"side", "type", ...}."""
    if not guards.groq_available():
        raise HTTPException(503, "Live mode needs GROQ_API_KEY on the server. Recorded runs still work.")

    rate_limit(request, "run", config.RUNS_PER_MINUTE)

    if payload.custom_attack:
        scenario = custom_scenario(payload.custom_attack)
    elif payload.scenario in BY_ID:
        scenario = BY_ID[payload.scenario]
    else:
        raise HTTPException(404, "Unknown scenario.")

    send, receive = anyio.create_memory_object_stream(500)
    global_store = get_store()

    def emitter(side, kind):
        def emit(item):
            if kind == "event":
                global_store.log_event({key: value for key, value in item.items() if key not in ("id", "ts")})

            try:
                send.send_nowait({"side": side, "type": kind, "data": item})
            except anyio.WouldBlock:
                pass

        return emit

    async def side(name, runner, **callbacks):
        try:
            outcome = await runner(scenario, **callbacks)
            summary = {key: value for key, value in outcome.items() if key not in ("steps", "events")}
            await send.send({"side": name, "type": "done", "data": summary})
        except Exception as error:  # report, don't kill the other side
            logger.exception("run failed", exc_info=error)
            await send.send({"side": name, "type": "error",
                             "data": {"message": f"{type(error).__name__}: {str(error)[:200]}"}})

    async def produce():
        async with send:
            async with anyio.create_task_group() as group:
                group.start_soon(side, "unprotected", run_unprotected, on_step=emitter("unprotected", "step"))
                group.start_soon(side, "protected", run_protected, on_step=emitter("protected", "step"),
                                 on_event=emitter("protected", "event"))

    async def stream():
        async with anyio.create_task_group() as group:
            group.start_soon(produce)

            async with receive:
                async for item in receive:
                    yield json.dumps(item, ensure_ascii=False, default=str) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class CheckRequest(BaseModel):
    text: str = Field(min_length=1, max_length=3000)
    where: str = Field(default="result returned by tool get_weather on server weather", max_length=120)


@app.post("/api/check")
async def check(payload: CheckRequest, request: Request):
    """Every layer's opinion on one text, so visitors can compare them."""
    rate_limit(request, "check", config.CHECKS_PER_MINUTE)
    layers = {}

    for layer in ("rules", "prompt_guard", "judge"):
        findings, info = await anyio.to_thread.run_sync(lambda: guards.run_layer(layer, payload.text, payload.where))
        layers[layer] = {"flagged": bool(findings), "findings": [f.to_dict() for f in findings], **info}

    similar = await anyio.to_thread.run_sync(lambda: get_store().similar_attacks(payload.text, k=3))
    return {"layers": layers, "similar_attacks": similar,
            "blocked": any(layer["flagged"] and any(f["severity"] in ("high", "critical") for f in layer["findings"])
                           for layer in layers.values())}


@app.get("/api/stats")
def stats():
    return {**get_store().stats(), "cache": get_cache().stats()}


@app.get("/api/events")
def events(limit: int = 30):
    return get_store().recent_events(min(limit, 100))
