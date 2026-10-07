#!/usr/bin/env bash
# ECR 저장소와 이미지를 모두 삭제합니다 (실습 완전 종료 시).
set -euo pipefail
aws ecr delete-repository --repository-name practice-app --region ap-northeast-2 --force
echo "ECR 저장소 삭제 완료"
