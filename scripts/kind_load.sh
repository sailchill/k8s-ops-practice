#!/usr/bin/env bash
# 이미지를 빌드해서 로컬 kind 클러스터에 넣습니다.  사용법: ./scripts/kind_load.sh 1.0.0
set -euo pipefail
VERSION=${1:?"버전을 입력하세요. 예: ./scripts/kind_load.sh 1.0.0"}
docker build --build-arg APP_VERSION="$VERSION" -t practice-app:"$VERSION" app/
kind load docker-image practice-app:"$VERSION" --name ops-practice
echo "완료: practice-app:$VERSION 이미지를 kind 클러스터에 넣었습니다."
