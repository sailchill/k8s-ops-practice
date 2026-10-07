# Git 실습 (이 저장소로 GitOps 배포 흐름 익히기)

운영 업무에서 Git은 주로 **배포 설정을 바꾸고, 이력을 확인하고, 되돌리는** 데 씁니다.
ArgoCD 환경에서는 "Git에 커밋 = 배포"입니다.

## 1단계: 저장소 만들고 올리기

GitHub에서 `k8s-ops-practice` 이름으로 **Public** 저장소를 만든 뒤 (README 추가 없이):

```bash
cd k8s-ops-practice
git init
git branch -M main
git add .
git commit -m "init: practice kit"
git remote add origin https://github.com/sailchill/k8s-ops-practice.git
git push -u origin main
```

> 처음 push할 때 비밀번호 대신 **Personal Access Token**을 입력해야 합니다.
> GitHub → Settings → Developer settings → Personal access tokens에서 발급합니다.
> 2단계 인증(2FA)도 이번 기회에 켜두세요.

## 2단계: 새 버전 배포 (브랜치 → PR → 머지 → Sync)

```bash
./scripts/kind_load.sh 1.1.0              # 새 버전 이미지 준비

git switch -c release/1.1.0
# k8s/overlays/local/kustomization.yaml 의 newTag를 "1.1.0"으로 수정
git diff                                  # 바뀐 내용 확인
git add k8s/overlays/local/kustomization.yaml
git commit -m "deploy: practice-app 1.1.0"
git push -u origin release/1.1.0
```

GitHub에서 **Pull Request** 생성 → 변경 내용 확인 → **Merge**
ArgoCD UI에서 `OutOfSync` 표시 확인 → **Sync** → 새 파드로 교체되는 과정 관찰

```bash
git switch main && git pull               # 로컬도 최신으로
kubectl rollout status -n practice deploy/practice-app
curl -s localhost:8080/                   # version이 1.1.0인지 확인
```

## 3단계: 이력 확인

```bash
git log --oneline -n 10
git show HEAD                             # 마지막 변경 내용
git log -p -- k8s/overlays/local/kustomization.yaml   # 이 파일의 변경 이력
```

ArgoCD UI의 **History and Rollback**에서도 배포 이력을 볼 수 있습니다.

## 4단계: 롤백 두 가지 방법

**방법 A. Git으로 되돌리기 (권장, GitOps 원칙)**
```bash
git revert HEAD                           # 마지막 커밋을 취소하는 새 커밋 생성
git push
```
→ ArgoCD가 Git 상태(1.0.0)에 맞춰 다시 배포

**방법 B. ArgoCD UI에서 이전 버전으로 Rollback**
→ 빠르지만 Git과 실제 상태가 달라지므로, 자동 Sync를 켜둔 환경에서는 Git이 다시 덮어씁니다.
→ 실무에서는 긴급 시 B로 먼저 복구하고, 바로 A로 Git도 맞추는 경우가 많습니다.

## 자주 쓰는 명령 요약

| 상황 | 명령 |
|---|---|
| 최신 받아오기 | `git pull` |
| 상태 확인 | `git status`, `git diff` |
| 브랜치 만들고 이동 | `git switch -c <이름>` |
| 커밋 | `git add <파일>` → `git commit -m "메시지"` |
| 올리기 | `git push` |
| 되돌리기 | `git revert <커밋>` |
| 이력 | `git log --oneline` |
