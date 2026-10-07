"""
LangGraph 기반 실습용 AI 에이전트 워크플로우.

실제 LLM API 대신 가짜(mock) 응답을 사용하므로 API 비용이 들지 않습니다.
운영 관점에서 '어느 단계(노드)에서 느려지거나 실패했는지'를 추적하는 연습용입니다.

흐름:
  START -> classify -> (in_scope) -> retrieve -> generate -> validate -> END
                    -> (out_of_scope) -> fallback -> END
  validate 실패 시 -> fallback -> END
"""
import logging
import random
import time
from typing import List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

logger = logging.getLogger("agent")


class NodeError(Exception):
    """특정 노드에서 발생한 실패. 어느 노드에서 실패했는지 기록하기 위해 사용."""

    def __init__(self, node: str, message: str):
        super().__init__(message)
        self.node = node


class AgentState(TypedDict, total=False):
    question: str
    category: str
    documents: List[str]
    answer: str
    valid: bool
    steps: List[dict]
    fail_node: Optional[str]  # 실패를 주입할 노드 이름
    slow_node: Optional[str]  # 지연을 주입할 노드 이름


def _chaos(state: AgentState, node: str) -> None:
    """요청에 따라 특정 노드에 지연 또는 실패를 주입."""
    if state.get("slow_node") == node:
        time.sleep(3.0)
    if state.get("fail_node") == node:
        raise NodeError(node, f"injected failure at node '{node}'")


def _record(state: AgentState, node: str, started: float, detail: str = "") -> List[dict]:
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    steps = list(state.get("steps", []))
    steps.append({"node": node, "elapsed_ms": elapsed_ms, "detail": detail})
    logger.info("agent node done", extra={"node": node, "elapsed_ms": elapsed_ms})
    return steps


def _mock_llm(prompt: str) -> str:
    """LLM 호출 흉내. 100~500ms 지연 후 고정 형식의 답을 돌려줌."""
    time.sleep(random.uniform(0.1, 0.5))
    return f"[mock-llm] '{prompt[:40]}'에 대한 답변입니다."


def classify(state: AgentState) -> dict:
    started = time.perf_counter()
    _chaos(state, "classify")
    question = state.get("question", "")
    category = "out_of_scope" if ("날씨" in question or "weather" in question.lower()) else "in_scope"
    return {"category": category, "steps": _record(state, "classify", started, category)}


def retrieve(state: AgentState) -> dict:
    started = time.perf_counter()
    _chaos(state, "retrieve")
    time.sleep(random.uniform(0.05, 0.2))
    docs = ["요금제 안내 문서", "고객센터 FAQ", "장애 공지 이력"]
    return {"documents": docs, "steps": _record(state, "retrieve", started, f"{len(docs)} docs")}


def generate(state: AgentState) -> dict:
    started = time.perf_counter()
    _chaos(state, "generate")
    answer = _mock_llm(state.get("question", ""))
    return {"answer": answer, "steps": _record(state, "generate", started)}


def validate(state: AgentState) -> dict:
    started = time.perf_counter()
    _chaos(state, "validate")
    valid = bool(state.get("answer"))
    return {"valid": valid, "steps": _record(state, "validate", started, str(valid))}


def fallback(state: AgentState) -> dict:
    started = time.perf_counter()
    answer = "죄송합니다. 해당 질문은 지금 답변드리기 어렵습니다. 상담원에게 연결해 드릴게요."
    return {"answer": answer, "steps": _record(state, "fallback", started)}


def _route_after_classify(state: AgentState) -> str:
    return state.get("category", "out_of_scope")


def _route_after_validate(state: AgentState) -> str:
    return "ok" if state.get("valid") else "retry_fallback"


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("classify", classify)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)
    graph.add_node("validate", validate)
    graph.add_node("fallback", fallback)

    graph.add_edge(START, "classify")
    graph.add_conditional_edges(
        "classify", _route_after_classify, {"in_scope": "retrieve", "out_of_scope": "fallback"}
    )
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", "validate")
    graph.add_conditional_edges(
        "validate", _route_after_validate, {"ok": END, "retry_fallback": "fallback"}
    )
    graph.add_edge("fallback", END)
    return graph.compile()


AGENT = build_graph()


def run_agent(question: str, fail_node: Optional[str] = None, slow_node: Optional[str] = None) -> dict:
    state: AgentState = {"question": question, "steps": [], "fail_node": fail_node, "slow_node": slow_node}
    result = AGENT.invoke(state)
    return {
        "question": question,
        "category": result.get("category"),
        "answer": result.get("answer"),
        "steps": result.get("steps", []),
    }
