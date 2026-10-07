#!/usr/bin/env bash
# 이미지를 빌드해서 ECR에 올립니다.  사용법: ./scripts/ecr_push.sh 1.0.0
set -euo pipefail
VERSION=${1:?"버전을 입력하세요. 예: ./scripts/ecr_push.sh 1.0.0"}
REGION=ap-northeast-2
REPO=practice-app
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGISTRY="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

aws ecr describe-repositories --repository-names "$REPO" --region "$REGION" >/dev/null 2>&1 \
  || aws ecr create-repository --repository-name "$REPO" --region "$REGION" >/dev/null

aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REGISTRY"
docker build --build-arg APP_VERSION="$VERSION" -t "$REGISTRY/$REPO:$VERSION" app/
docker push "$REGISTRY/$REPO:$VERSION"
echo "완료: $REGISTRY/$REPO:$VERSION"
echo "k8s/overlays/eks/kustomization.yaml 의 ACCOUNT_ID를 $ACCOUNT_ID 로 바꿨는지 확인하세요."
