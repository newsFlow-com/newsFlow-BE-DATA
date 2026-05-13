# newsFlow-BE-DATA

> NewsFlow 플랫폼의 데이터 수집 및 파이프라인 레포지토리입니다.  
> 외부 뉴스 소스로부터 기사를 수집하고, 정제·분류하여 DB에 적재하는 전 과정을 담당합니다.  
> 수집된 데이터는 `newsFlow-BE-API(Spring Boot)` 및 `newsFlow-BE-AI(Python)`가 소비합니다.

---

## 📌 사용 목적

- 다양한 뉴스 매체(RSS, 웹 크롤링, 뉴스 API)로부터 기사 원천 데이터를 수집
- 수집된 기사에 산업군(카테고리) 자동 분류 처리
- 중복 기사 제거, 본문 정제 등 전처리(Preprocessing) 수행
- 정제된 데이터를 PostgreSQL에 적재하여 API 서버와 AI 서버가 소비할 수 있도록 공급
- DB 스키마 설계 및 Alembic 마이그레이션 버전 관리
- Airflow DAG으로 수집→정제→적재 파이프라인 자동화

---

## 🛠 기술 스택

| 분류 | 기술 | 용도 |
|------|------|------|
| **Language** | Python 3.11 | 크롤링 및 데이터 파이프라인 구성 |
| **웹 크롤링** | Scrapy | 뉴스 사이트 구조화된 크롤링 |
| **RSS 수집** | feedparser | RSS/Atom 피드 기반 기사 자동 수집 |
| **외부 뉴스 API** | httpx | NewsAPI, 네이버 뉴스 API 연동 |
| **HTML 파싱** | BeautifulSoup4 + lxml | 기사 본문 추출 및 태그 정제 |
| **본문 고품질 추출** | newspaper3k | 광고·메뉴 제거 후 순수 기사 본문 추출 |
| **산업군 자동 분류** | scikit-learn + kiwipiepy | 기사 본문 기반 카테고리 분류 |
| **중복 기사 탐지** | datasketch (MinHash / LSH) | 유사 기사 중복 탐지 및 제거 |
| **파이프라인 오케스트레이션** | Apache Airflow | 수집·정제·적재 DAG 관리 및 스케줄링 |
| **DB 적재** | SQLAlchemy + psycopg2 | PostgreSQL 데이터 적재 |
| **DB 마이그레이션** | Alembic | 스키마 버전 관리 |
| **데이터베이스** | PostgreSQL | 기사 데이터 영구 저장 |
| **환경 변수 관리** | python-dotenv | 환경 설정 분리 |
| **테스트** | pytest | 수집·파이프라인 단위 테스트 |
| **컨테이너** | Docker + docker-compose | 수집 환경 통일 및 배포 |

---

## 📁 주요 디렉토리 구조

```
newsFlow-BE-DATA/
├── crawlers/
│   ├── rss/                    # RSS/Atom 피드 수집기
│   ├── scrapy_spiders/         # Scrapy 기반 사이트별 크롤러
│   └── news_api/               # 외부 뉴스 API 클라이언트 (NewsAPI, 네이버)
├── pipelines/
│   ├── preprocessor.py         # HTML 제거, 본문 정제
│   ├── deduplicator.py         # 중복 기사 탐지 및 제거
│   └── classifier.py           # 산업군 자동 분류
├── db/
│   ├── models.py               # SQLAlchemy 테이블 정의
│   └── migrations/             # Alembic 마이그레이션 파일
├── dags/                       # Airflow DAG 정의
│   ├── hourly_collect.py       # 시간별 기사 수집 DAG
│   └── daily_aggregate.py      # 일별 집계 DAG
├── tests/
├── requirements.txt
├── docker-compose.yml
└── .env.example
```

---

## ✅ 핵심 기능 목록

- [ ] RSS 피드 기반 실시간 기사 수집
- [ ] Scrapy 크롤러 — 주요 뉴스 사이트별 스파이더
- [ ] 외부 뉴스 API 연동 (NewsAPI, 네이버 뉴스 등)
- [ ] 기사 본문 HTML 정제 및 텍스트 추출 (newspaper3k)
- [ ] **산업군 자동 분류** (IT, 금융, 정치, 사회 등)
- [ ] 중복 기사 탐지 및 제거 (MinHash 기반)
- [ ] PostgreSQL 적재 및 Alembic 마이그레이션 관리
- [ ] Airflow DAG — 시간별 수집 / 일별 집계 자동화

---

## 🗄 DB 스키마 (초안)

```
articles
├── id              UUID PK
├── title           TEXT
├── content         TEXT
├── summary         TEXT          ← BE-AI가 생성한 요약문 저장
├── source_url      TEXT UNIQUE
├── publisher       VARCHAR
├── category_id     FK → categories
├── published_at    TIMESTAMP
├── collected_at    TIMESTAMP
└── view_count      INT DEFAULT 0  ← BE-API Redis 배치 반영 대상

categories
├── id              UUID PK
├── name            VARCHAR       (예: IT, 금융, 정치, 사회)
└── slug            VARCHAR
```

---

## 🔗 연관 레포지토리

| 레포지토리 | 역할 |
|------------|------|
| `newsFlow-BE-API` | 적재된 기사 데이터 소비 (Spring Boot) |
| `newsFlow-BE-AI` | 기사 원천 데이터 및 메타데이터 활용 |
