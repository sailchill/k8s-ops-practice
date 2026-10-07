#!/bin/sh
# ENABLE_DDTRACE=true 이면 Datadog APM 트레이싱을 켜고 실행
if [ "$ENABLE_DDTRACE" = "true" ]; then
  exec ddtrace-run uvicorn main:app --host 0.0.0.0 --port 8080
else
  exec uvicorn main:app --host 0.0.0.0 --port 8080
fi
