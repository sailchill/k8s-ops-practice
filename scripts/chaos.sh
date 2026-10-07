#!/usr/bin/env bash
# 장애 연습용 명령 모음.
# 먼저 다른 터미널에서: kubectl port-forward -n practice svc/practice-app 8080:80
# 사용법: ./scripts/chaos.sh <명령> [값]
set -euo pipefail
BASE=${BASE:-http://localhost:8080}
cmd=${1:-help}
case "$cmd" in
  call)    for i in $(seq 1 ${2:-20}); do curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" "$BASE/"; done ;;
  agent)   curl -s -X POST "$BASE/agent/run" -H 'Content-Type: application/json' -d "{\"question\":\"${2:-요금제 변경 방법 알려줘}\"}"; echo ;;
  agentfail) curl -s -X POST "$BASE/agent/run" -H 'Content-Type: application/json' -d "{\"question\":\"요금제 문의\",\"fail_node\":\"${2:-generate}\"}"; echo ;;
  agentslow) curl -s -X POST "$BASE/agent/run" -H 'Content-Type: application/json' -d "{\"question\":\"요금제 문의\",\"slow_node\":\"${2:-retrieve}\"}"; echo ;;
  latency) curl -s -X POST "$BASE/chaos/latency?ms=${2:-2000}"; echo ;;
  error)   curl -s -X POST "$BASE/chaos/error?rate=${2:-0.5}"; echo ;;
  memory)  for i in $(seq 1 ${2:-6}); do curl -s -X POST "$BASE/chaos/memory?mb=50"; echo; done ;;
  unready) curl -s -X POST "$BASE/chaos/unready"; echo ;;
  crash)   curl -s -X POST "$BASE/chaos/crash" || true; echo "crash 요청 보냄" ;;
  reset)   curl -s -X POST "$BASE/chaos/reset"; echo ;;
  *) echo "명령: call [횟수] | agent [질문] | agentfail [노드] | agentslow [노드] | latency [ms] | error [비율] | memory [횟수] | unready | crash | reset" ;;
esac
