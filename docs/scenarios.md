# 장애 시나리오 8종

준비: 다른 터미널에서 `kubectl port-forward -n practice svc/practice-app 8080:80` 실행
각 시나리오가 끝나면 `./scripts/chaos.sh reset` (또는 파드 재시작)으로 원상복구합니다.

> 참고: 파드가 재시작되는 시나리오(4, 5번)에서는 port-forward 연결이 끊깁니다. 끊기면 port-forward를 다시 실행하세요.
>
> 참고: chaos 설정은 **파드마다 따로** 적용됩니다. port-forward는 파드 하나에만 연결되므로,
> 여러 파드 중 하나에만 장애가 난 상황을 관찰하기 좋습니다.

모든 시나리오는 아래 틀로 정리해 보세요. 실제 장애 보고서의 기본 구조입니다.

```
[현상] 무엇이 보였나 (사용자 영향 기준)
[영향 범위] 어떤 기능, 몇 개 파드, 언제부터
[확인] 어떤 명령/화면으로 확인했나
[원인] 왜 발생했나
[조치] 무엇을 했나 (임시 조치 / 근본 조치)
[재발 방지] 모니터링, 설정, 절차 개선
```

---

## 1. 배포 실패: 존재하지 않는 이미지 버전
- **방법**: `newTag`를 `"9.9.9"`로 바꿔 커밋·Sync
- **확인**: `kubectl get pods -n practice` → `ErrImagePull` / `ImagePullBackOff`, ArgoCD `Degraded`
- **조치**: `git revert`로 되돌리기
- **생각해 볼 점**: 기존 파드는 왜 계속 살아 있었을까? (RollingUpdate 전략)

## 2. 응답 지연
- **방법**: `./scripts/chaos.sh latency 3000` → `./scripts/chaos.sh call 10`
- **확인**: 응답 시간 증가, Datadog 로그의 `duration_ms`, APM 지연 그래프
- **생각해 볼 점**: 지연 알림 기준을 몇 ms로 잡아야 고객 경험 훼손을 먼저 알아챌까?

## 3. 에러율 증가
- **방법**: `./scripts/chaos.sh error 0.5` → `./scripts/chaos.sh call 20`
- **확인**: 500 응답 비율, Datadog Logs에서 `status:error`
- **실습**: "에러 로그 5분간 N건 이상" 모니터를 만들고 알림이 오는지 확인

## 4. 메모리 부족 (OOMKilled)
- **방법**: `./scripts/chaos.sh memory 6`
- **확인**: `kubectl get pods -n practice` → RESTARTS 증가
  `kubectl describe pod -n practice <파드>` → Last State: `OOMKilled`
- **생각해 볼 점**: limits를 늘리는 게 답일까, 메모리 누수를 찾는 게 답일까?

## 5. 프로세스 비정상 종료 (CrashLoop)
- **방법**: `./scripts/chaos.sh crash`를 여러 번
- **확인**: RESTARTS 증가, 반복되면 `CrashLoopBackOff`
  `kubectl logs -n practice <파드> --previous` → 죽기 직전 로그
- **포인트**: `--previous` 옵션은 재시작 장애 분석의 핵심 명령

## 6. Readiness 실패 (트래픽 제외)
- **방법**: `./scripts/chaos.sh unready`
- **확인**: `kubectl get pods -n practice` → READY `0/1`
  `kubectl get endpoints -n practice practice-app` → 해당 파드 IP가 빠짐
- **생각해 볼 점**: liveness와 readiness가 실패했을 때 쿠버네티스의 동작은 어떻게 다른가?

## 7. 설정 변경 감지 (Drift)와 selfHeal
- **방법**: `kubectl scale -n practice deploy/practice-app --replicas=5`
- **확인**: ArgoCD에서 `OutOfSync` 표시
  자동 Sync + selfHeal이 켜져 있으면 다시 2개로 돌아감 (`argocd/app-local.yaml` 주석 해제 후 실습)
- **포인트**: GitOps 환경에서 `kubectl`로 직접 바꾼 설정은 유지되지 않는다

## 8. AI 에이전트 단계별 장애
- **방법**:
  - `./scripts/chaos.sh agentfail generate` → 생성 단계 실패
  - `./scripts/chaos.sh agentslow retrieve` → 검색 단계 3초 지연
  - `./scripts/chaos.sh agent "내일 날씨 알려줘"` → 범위 밖 질문 → fallback 경로
- **확인**: 응답의 `steps`(노드별 소요시간), Datadog Logs에서 `failed_node` 필드
- **생각해 볼 점**: 실제 LLM이라면 어떤 원인이 많을까? (API 타임아웃, 호출 한도 초과, 응답 형식 오류)
  어느 단계가 실패하면 사용자에게 fallback을 보여주는 게 맞을까?
