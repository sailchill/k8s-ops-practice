"""
실습용 샘플 서비스 (FastAPI).

정상 API, 헬스체크, LangGraph 에이전트 실행, 그리고 장애를 일부러 일으키는
chaos 엔드포인트를 제공합니다. 로그는 Datadog이 수집하기 좋도록 JSON 한 줄 형식입니다.
"""
import json
import logging
import os
import random
import sys
import time
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agent import NodeError, run_agent

APP_VERSION = os.getenv("APP_VERSION", "dev")
SERVICE_NAME = os.getenv("DD_SERVICE", "practice-app")


class JsonFormatter(logging.Formatter):
    RESERVED = set(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime"}

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": SERVICE_NAME,
            "version": APP_VERSION,
        }
        for key, value in vars(record).items():
            if key not in self.RESERVED:
                payload[key] = value
        if record.exc_info:
            payload["error"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
logger = logging.getLogger("app")

app = FastAPI(title="practice-app", version=APP_VERSION)

# chaos 상태 (파드마다 따로 가짐)
STATE = {"ready": True, "error_rate": 0.0, "latency_ms": 0}
MEMORY_HOG: List[bytearray] = []


@app.middleware("http")
async def access_log(request: Request, call_next):
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        if request.url.path not in ("/health", "/ready"):
            logger.info(
                "request",
                extra={"method": request.method, "path": request.url.path,
                       "status": status, "duration_ms": duration_ms},
            )


def _apply_global_chaos() -> None:
    if STATE["latency_ms"] > 0:
        time.sleep(STATE["latency_ms"] / 1000)
    if STATE["error_rate"] > 0 and random.random() < STATE["error_rate"]:
        logger.error("injected error", extra={"error_rate": STATE["error_rate"]})
        raise HTTPException(status_code=500, detail="injected error")


# ---------- 정상 엔드포인트 ----------
@app.get("/")
def root():
    _apply_global_chaos()
    return {"service": SERVICE_NAME, "version": APP_VERSION, "pod": os.getenv("HOSTNAME", "local")}


@app.get("/health")
def health():
    """liveness: 프로세스가 살아 있는지."""
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """readiness: 트래픽을 받을 준비가 됐는지. /chaos/unready로 끌 수 있음."""
    if not STATE["ready"]:
        return JSONResponse(status_code=503, content={"status": "not ready"})
    return {"status": "ready"}


class AgentRequest(BaseModel):
    question: str
    fail_node: Optional[str] = None
    slow_node: Optional[str] = None


@app.post("/agent/run")
def agent_run(req: AgentRequest):
    _apply_global_chaos()
    started = time.perf_counter()
    try:
        result = run_agent(req.question, req.fail_node, req.slow_node)
    except NodeError as e:
        logger.error("agent failed", extra={"failed_node": e.node, "reason": str(e)})
        raise HTTPException(status_code=500, detail={"failed_node": e.node, "reason": str(e)})
    result["total_ms"] = round((time.perf_counter() - started) * 1000, 1)
    return result


# ---------- chaos 엔드포인트 (장애 연습용) ----------
@app.post("/chaos/latency")
def chaos_latency(ms: int = 2000):
    """이후 / 와 /agent/run 응답을 ms만큼 느리게 만듦."""
    STATE["latency_ms"] = max(0, ms)
    logger.warning("chaos latency set", extra={"latency_ms": ms})
    return STATE


@app.post("/chaos/error")
def chaos_error(rate: float = 0.5):
    """이후 요청 중 rate 비율만큼 500 에러를 냄 (0.0~1.0)."""
    STATE["error_rate"] = min(max(rate, 0.0), 1.0)
    logger.warning("chaos error rate set", extra={"error_rate": STATE["error_rate"]})
    return STATE


@app.post("/chaos/memory")
def chaos_memory(mb: int = 50):
    """메모리를 mb만큼 점유. 반복 호출하면 컨테이너 메모리 한도 초과로 OOMKilled 발생."""
    buf = bytearray(mb * 1024 * 1024)
    buf[::4096] = b"\x01" * len(range(0, len(buf), 4096))  # 실제로 페이지를 사용하게 만듦
    MEMORY_HOG.append(buf)
    total = sum(len(b) for b in MEMORY_HOG) // (1024 * 1024)
    logger.warning("chaos memory allocated", extra={"total_mb": total})
    return {"total_mb": total}


@app.post("/chaos/unready")
def chaos_unready():
    """readiness를 실패시켜 이 파드로 트래픽이 가지 않게 함."""
    STATE["ready"] = False
    logger.warning("chaos unready")
    return STATE


@app.post("/chaos/crash")
def chaos_crash():
    """프로세스를 즉시 종료. 쿠버네티스가 컨테이너를 재시작함."""
    logger.critical("chaos crash requested, exiting")
    os._exit(1)


@app.post("/chaos/reset")
def chaos_reset():
    STATE.update({"ready": True, "error_rate": 0.0, "latency_ms": 0})
    MEMORY_HOG.clear()
    logger.info("chaos reset")
    return STATE
