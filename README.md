# FastAPI 데이터 분석 파이프라인

요청 데이터를 분석한 뒤 외부 백엔드 API로 결과를 전달하는 실행 가능한
스켈레톤입니다.

## 처리 흐름

1. `POST /api/v1/analysis`가 JSON 레코드를 검증합니다.
2. pandas 분석을 별도 스레드에서 실행해 FastAPI 이벤트 루프를 막지 않습니다.
3. 분석 결과를 설정된 백엔드 엔드포인트로 전송합니다.
4. 일시적인 HTTP 오류는 지수 백오프로 재시도합니다.

## 설치한 패키지와 목적

### 런타임

| 패키지 | 목적 |
|---|---|
| `aiokafka` | FastAPI의 비동기 실행 모델과 연결되는 Kafka producer/consumer |
| `fastapi` | HTTP API, 입력 검증, OpenAPI 문서 생성 |
| `uvicorn[standard]` | FastAPI를 실행하는 ASGI 서버와 성능/개발 부가 기능 |
| `pydantic-settings` | `.env` 및 환경변수 기반 설정 관리 |
| `pandas` | 표 형태 데이터 변환·집계·분석 |
| `numpy` | pandas의 수치 연산 기반 및 향후 분석 확장 |
| `httpx` | 분석 결과를 백엔드로 비동기 HTTP 전송 |
| `tenacity` | 외부 백엔드 호출 실패 시 백오프 재시도 |

`anyio`와 `pydantic`은 FastAPI의 핵심 의존성으로 함께 설치됩니다. 코드에서는
각각 동기 분석의 스레드 실행과 요청/응답 모델 검증에 사용합니다.

### 개발/품질

| 패키지 | 목적 |
|---|---|
| `pytest`, `pytest-asyncio` | 단위·비동기 테스트 |
| `pytest-cov` | 테스트 커버리지 측정 |
| `respx` | `httpx` 백엔드 호출 모킹 |
| `ruff` | 빠른 린트, import 정리, 포맷 |
| `mypy`, `pandas-stubs` | 정적 타입 검사와 pandas 타입 정보 |

## 폴더 구조

```text
.
├── src/app/
│   ├── api/                 # HTTP 라우팅 및 의존성 조립
│   │   └── routes/
│   ├── clients/             # 외부 백엔드 등 outbound 연동
│   ├── core/                # 설정, 로깅 등 공통 기반
│   ├── schemas/             # Pydantic 입출력 계약
│   ├── services/            # 분석 및 파이프라인 비즈니스 로직
│   └── main.py              # 앱 생성과 lifecycle
├── tests/                   # 단위/API 테스트
├── .env.example             # 환경변수 명세
├── Dockerfile               # 운영 이미지
├── Makefile                 # 반복 명령 단축
└── pyproject.toml           # 의존성 및 도구 설정의 단일 진실 공급원
```

이 구조는 transport(API), business logic(service), external I/O(client), data
contract(schema)를 분리합니다. 데이터베이스가 필요해지면 `repositories/`와
`models/`를 추가하고, 대규모 비동기 작업이 필요하면 큐 worker를 별도 프로세스로
분리할 수 있습니다.

## 로컬 실행

Python 3.11 이상이 필요합니다.

```bash
make install
cp .env.example .env
make run
```

- API 문서: <http://localhost:8000/docs>
- 상태 확인: <http://localhost:8000/api/v1/health>

서버를 시작하기 전에 Kafka 브로커가 로컬 `9092` 포트에서 실행 중이어야 합니다.
`KAFKA_ENABLED=true`이면 서버 시작 시 producer가 브로커에 연결되며 health
응답의 `kafka` 값이 `connected`로 표시됩니다.

```json
{"status": "ok", "kafka": "connected"}
```

호출 예시:

```bash
curl -X POST http://localhost:8000/api/v1/analysis \
  -H 'Content-Type: application/json' \
  -d '{"records":[{"score":10,"group":"A"},{"score":20,"group":"B"}]}'
```

실제 백엔드 주소와 인증키는 `.env`의 `BACKEND_BASE_URL`,
`BACKEND_RESULT_PATH`, `BACKEND_API_KEY`에 설정합니다.

## 품질 검사

```bash
make check
```

운영에서는 요청 안에서 오래 걸리는 분석을 끝까지 수행하기보다 Celery, Dramatiq,
ARQ 같은 작업 큐로 분리하는 편이 안전합니다. 이 스켈레톤은 짧은 분석을 위한
동기식 API이며, 긴 작업으로 확장할 때도 `AnalysisPipeline`을 worker에서 그대로
재사용할 수 있도록 분리했습니다.

## 채용 종료 이벤트 consumer

Spring Kafka producer가 발행하는 `project.recruit.ends`,
`study.recruit.ends`, `club.recruit.ends` 토픽은 다음 worker로 소비할 수 있습니다.

```bash
PYTHONPATH=src python3 -m app.clients.kafka_consumer
```

consumer는 이벤트 객체의 양의 정수 `targets` 배열을 받아 토픽별 백엔드 API를
호출하고 지원자 순위를 분석합니다. 결과가 있으면
`POST /api/v1/analytics/results`로 저장한 뒤 offset을 커밋합니다. 조회·분석·저장 중
하나라도 실패하면 offset을 커밋하지 않아 이벤트를 다시 처리합니다.

지원자 평가는 `Agent → Task → Crew` 구조로 수행됩니다.

- `DataQualityAgent`: 지원자 수와 application ID 누락·중복을 검사합니다.
- `ApplicantEvaluationAgent`: 규칙 기반 추천 엔진으로 적합도와 신뢰도를 계산합니다.
- `EvaluationReviewAgent`: 대상 일치, 지원자 누락, 점수 정렬을 최종 검수합니다.
- `RecruitmentEvaluationCrew`: 세 Task를 순서대로 실행하고 검수된 결과만 저장 흐름에
  전달합니다.

`EvaluationReviewAgent`는 각 지원자 결과에 `reviewSummary`를 생성합니다. 요약에는
최종 판정, 점수, 신뢰도, 사람 검토 필요 여부, 주요 강점과 검토사항이 포함되며,
백엔드 저장 시 기존 `reasonSummary` 값으로도 전달됩니다.

평가 항목은 모집 유형별로 다릅니다. 프로젝트는 기술·역할·경험을 중심으로,
스터디는 지원 답변·활동 조건을 중심으로, 동아리는 지원 동기·답변을 중심으로
평가합니다. 신뢰도 역시 각 유형에 적용 가능한 가중치만 분모로 사용하며 지원 상태는
감사 정보로만 취급하고 적합도 판정을 차단하지 않습니다.

```json
{
  "eventId": "a654194d-c1a0-4adc-b1f1-b840b3a4ba11",
  "targets": [10, 20, 30]
}
```

- `project.recruit.ends`: ID별 `/api/v1/analytics/projects/{id}/evaluation-dataset` 호출
- `study.recruit.ends`: ID별 `/api/v1/analytics/studies/{id}/evaluation-dataset` 호출
- `club.recruit.ends`: ID별 `/api/v1/analytics/clubs/{id}/evaluation-dataset` 호출

저장 요청의 `calculationId`에는 원본 Kafka 이벤트의 `eventId`가 사용되며,
`modelVersion`에는 분석기의 `analysisVersion`이 전달됩니다. 지원자가 없거나 유효한
`applicationId`가 없는 결과는 백엔드 DTO의 최소 1건 조건에 맞춰 저장 요청을
생략합니다.

동시에 보내는 요청 수는 `BACKEND_FETCH_CONCURRENCY`로 제한합니다. 하나라도 최종
실패하면 offset을 커밋하지 않아 Kafka가 이벤트를 다시 전달할 수 있습니다.
`KAFKA_CONSUMER_GROUP_ID`로 consumer group을 분리할 수 있습니다.

## Jenkins 배포

`Jenkinsfile`은 테스트를 통과한 단일 Docker 이미지를 빌드한 뒤 애플리케이션 서버에
두 컨테이너로 배포합니다.

- `growp-analysis-api`: FastAPI, host의 `8000` 포트 사용
- `growp-analysis-consumer`: Kafka consumer worker

Jenkins에는 백엔드 배포와 동일한 ID의 Credentials가 필요합니다.

- `nhn-ssh-key`: bastion 접속용 SSH private key
- `kafka-host`: Kafka broker host
- `kafka-port`: Kafka broker port

API와 consumer는 `--network host`로 실행됩니다. 따라서 Python 컨테이너의
`http://127.0.0.1:8080`은 같은 애플리케이션 서버에 배포된 Spring 백엔드를
가리킵니다. 다른 서버에 백엔드가 있다면 `Jenkinsfile`의 `BACKEND_BASE_URL`을 해당
내부 주소로 변경해야 합니다.
# GROWP-DATA-BE
