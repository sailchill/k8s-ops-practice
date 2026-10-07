# k8s-ops-practice

AWS · Kubernetes · ArgoCD · Datadog · LangGraph 운영 실습 키트입니다.
샘플 서비스를 직접 배포하고, 일부러 장애를 일으켜 보면서 **운영자 관점**(상태 확인, 배포 추적, 모니터링, 1차 트러블슈팅)을 익히는 것이 목표입니다.

## 구성

```
k8s-ops-practice/
├── app/                  # 샘플 서비스 (FastAPI + LangGraph 에이전트)
│   ├── main.py           # API, 헬스체크, 장애 주입(chaos) 엔드포인트
│   ├── agent.py          # LangGraph 워크플로우 (LLM은 가짜 응답, 비용 없음)
│   └── Dockerfile
├── k8s/
│   ├── base/             # Deployment, Service, Namespace
│   └── overlays/
│       ├── local/        # 로컬 kind 클러스터용
│       └── eks/          # AWS EKS용 (LoadBalancer, ECR 이미지)
├── argocd/               # ArgoCD Application 정의
├── datadog/values.yaml   # Datadog Agent Helm 설정
├── eks/                  # eksctl 클러스터 설정, 정리 스크립트
├── kind/cluster.yaml     # 로컬 클러스터 설정
├── scripts/              # 이미지 빌드/업로드, 장애 연습 명령
└── docs/
    ├── git_basics.md     # 이 저장소로 하는 Git 실습
    └── scenarios.md      # 장애 시나리오 8종
```

## 서비스 엔드포인트

| 경로 | 설명 |
|---|---|
| `GET /` | 서비스 이름, 버전, 파드 이름 |
| `GET /health`, `GET /ready` | liveness / readiness 프로브 |
| `POST /agent/run` | LangGraph 에이전트 실행 (`fail_node`, `slow_node`로 특정 단계에 실패·지연 주입 가능) |
| `POST /chaos/latency?ms=2000` | 응답 지연 |
| `POST /chaos/error?rate=0.5` | 에러율 주입 |
| `POST /chaos/memory?mb=50` | 메모리 점유 (반복 시 OOMKilled) |
| `POST /chaos/unready` | readiness 실패 |
| `POST /chaos/crash` | 프로세스 강제 종료 |
| `POST /chaos/reset` | 장애 주입 해제 |

---

## 0. 준비 (Windows 기준)

Windows에서는 **WSL2(Ubuntu) + Docker Desktop** 조합을 권장합니다. 아래 명령은 모두 WSL2 Ubuntu 터미널에서 실행합니다.

1. Docker Desktop 설치 → Settings → Resources → WSL Integration에서 Ubuntu 체크
2. 도구 설치

```bash
# kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -m 0755 kubectl /usr/local/bin/kubectl && rm kubectl

# kind (최신 버전은 https://kind.sigs.k8s.io/docs/user/quick-start/ 에서 확인)
# 예시: curl -Lo ./kind https://kind.sigs.k8s.io/dl/<버전>/kind-linux-amd64 && sudo install -m 0755 kind /usr/local/bin/kind

# helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
unzip awscliv2.zip && sudo ./aws/install && rm -rf aws awscliv2.zip

# eksctl
curl -sLO "https://github.com/eksctl-io/eksctl/releases/latest/download/eksctl_Linux_amd64.tar.gz"
tar -xzf eksctl_Linux_amd64.tar.gz && sudo install -m 0755 eksctl /usr/local/bin/eksctl && rm eksctl*

# 설치 확인
docker version && kubectl version --client && kind version && helm version && aws --version && eksctl version
```

3. GitHub에 **Public** 저장소 `k8s-ops-practice`를 만들고 이 폴더를 올립니다. (방법은 `docs/git_basics.md` 1단계)
   ArgoCD가 이 저장소를 읽어서 배포하므로 저장소 이름과 계정(`sailchill`)이 `argocd/*.yaml`의 `repoURL`과 같아야 합니다.

---

## 1일차: 로컬 쿠버네티스 기본

```bash
kind create cluster --config kind/cluster.yaml
kubectl get nodes

./scripts/kind_load.sh 1.0.0            # 이미지 빌드 후 클러스터에 넣기
kubectl apply -k k8s/overlays/local     # 직접 배포 (2일차부터는 ArgoCD가 대신함)

kubectl get all -n practice
kubectl describe pod -n practice <파드이름>
kubectl logs -n practice deploy/practice-app

kubectl port-forward -n practice svc/practice-app 8080:80   # 다른 터미널에서 실행
./scripts/chaos.sh call 5
./scripts/chaos.sh agent
```

손에 익힐 명령: `get`, `describe`, `logs`, `exec`, `rollout status`, `rollout history`, `rollout undo`, `scale`

1일차 마지막에 직접 배포한 리소스를 지웁니다. 2일차부터 ArgoCD에 맡기기 위해서입니다.
```bash
kubectl delete -k k8s/overlays/local
```

## 2일차: ArgoCD (GitOps 배포와 롤백)

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
# "metadata.annotations: Too long" 에러가 나면 위 명령에 --server-side 를 붙여 다시 실행

kubectl get pods -n argocd -w            # 모두 Running 될 때까지 대기

# 관리자 비밀번호 확인 (아이디: admin)
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d; echo

kubectl port-forward svc/argocd-server -n argocd 8443:443   # 브라우저: https://localhost:8443
kubectl apply -f argocd/app-local.yaml
```

UI에서 `practice-app`을 열고 **Sync** → 상태가 `Synced / Healthy`가 되는지 확인합니다.
이후 `docs/git_basics.md`의 2~4단계(버전 올려 배포, 롤백)를 진행합니다.

## 3일차: Datadog 모니터링

1. https://www.datadoghq.com 에서 14일 무료 체험 가입 → Organization Settings → API Keys에서 키 복사
2. 가입한 사이트 주소(예: `datadoghq.com`, `ap1.datadoghq.com`)를 `datadog/values.yaml`의 `site`에 맞게 수정

```bash
helm repo add datadog https://helm.datadoghq.com && helm repo update
kubectl create namespace datadog
kubectl create secret generic datadog-secret -n datadog --from-literal api-key=<API_KEY>
helm install datadog-agent datadog/datadog -n datadog -f datadog/values.yaml
kubectl get pods -n datadog
```

Datadog 화면에서 확인할 것
- **Infrastructure → Kubernetes**: 노드, 파드 상태
- **Logs**: `service:practice-app` 검색, `status:error` 필터
- **Monitors**: "에러 로그가 5분간 10건 이상이면 알림" 같은 모니터 직접 만들기
- **APM (선택)**: `k8s/base/deployment.yaml`의 `ENABLE_DDTRACE`를 `"true"`로 바꿔 커밋 → ArgoCD 배포 → APM → Services에서 응답시간, 에러율 확인

## 4일차: 장애 시나리오 연습

`docs/scenarios.md`의 시나리오 8종을 순서대로 진행합니다. 각 시나리오마다 **현상 → 확인 → 원인 → 조치 → 보고** 순서로 정리해 보세요.

## 5일차: AWS EKS에서 같은 흐름 반복 (과금 발생, 당일 삭제 권장)

```bash
aws configure                                  # 액세스 키, 리전 ap-northeast-2
eksctl create cluster -f eks/cluster.yaml      # 약 15~20분
kubectl get nodes

./scripts/ecr_push.sh 1.0.0                    # ECR에 이미지 업로드
# k8s/overlays/eks/kustomization.yaml 의 ACCOUNT_ID를 실제 계정 번호로 바꿔 커밋/푸시

# ArgoCD 설치 (2일차와 동일) 후
kubectl apply -f argocd/app-eks.yaml           # 자동 Sync + selfHeal
kubectl get svc -n practice                    # EXTERNAL-IP(로드밸런서 주소)로 접속
```

실습이 끝나면 **반드시** 정리합니다.
```bash
./eks/cleanup.sh
```

## 비용 메모 (서울 리전, 대략)

| 항목 | 하루(24시간) |
|---|---|
| EKS 클러스터 | 약 $2.4 |
| t3.medium 노드 2대 | 약 $2.5 |
| NAT 게이트웨이 | 약 $1.5 + 전송량 |
| 로드밸런서 | 약 $0.6 |

- 1~4일차는 로컬(kind)이라 AWS 비용이 없습니다.
- 5일차는 하루 안에 만들고 지우면 몇 달러 수준입니다.
- AWS Budgets에서 $30 / $60 알림을 미리 걸어두세요.
