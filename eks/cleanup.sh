#!/usr/bin/env bash
# EKS 실습 리소스 정리 스크립트. 과금 방지를 위해 실습이 끝나면 꼭 실행하세요.
set -euo pipefail
REGION=ap-northeast-2
CLUSTER=ops-practice

echo "[1/4] ArgoCD Application 삭제 (앱 리소스와 로드밸런서 정리)"
kubectl delete application practice-app -n argocd --ignore-not-found
echo "[2/4] LoadBalancer 서비스 삭제 (AWS 로드밸런서가 남지 않도록 클러스터 삭제 전에 먼저 지움)"
kubectl delete svc practice-app -n practice --ignore-not-found
sleep 30

echo "[3/4] EKS 클러스터 삭제 (노드, VPC, NAT 게이트웨이 포함, 약 10~15분)"
eksctl delete cluster --name "$CLUSTER" --region "$REGION" --wait

echo "[4/4] 남은 과금 리소스 점검"
echo "- 남은 로드밸런서:"
aws elbv2 describe-load-balancers --region "$REGION" --query 'LoadBalancers[].LoadBalancerName' --output text || true
aws elb describe-load-balancers --region "$REGION" --query 'LoadBalancerDescriptions[].LoadBalancerName' --output text || true
echo "- 할당만 되고 연결 안 된 Elastic IP:"
aws ec2 describe-addresses --region "$REGION" --query 'Addresses[?AssociationId==null].PublicIp' --output text || true
echo "- 남은 NAT 게이트웨이:"
aws ec2 describe-nat-gateways --region "$REGION" --filter Name=state,Values=available --query 'NatGateways[].NatGatewayId' --output text || true
echo "위 목록에 남은 항목이 있으면 콘솔에서 직접 삭제하세요."
echo "(ECR 저장소의 이미지는 소액 과금되므로, 다 끝나면 scripts/ecr_delete.sh로 지우세요)"
