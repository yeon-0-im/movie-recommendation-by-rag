# 영화 리스트 수집 기준

## 개요

| 항목 | 내용 |
|------|------|
| 목표 편수 | 2,000편 |
| 타깃 사용자 | 한국 사용자 위주 (한국 영화 비중 강화, 외국 영화 포함) |
| 수집 연도 범위 | 제한 없음 ~ 2026년 |
| 메이저 : 마이너 | 60% : 40% (1,200편 : 800편) |

---

## 전제 조건 (모든 영화 공통)

왓챠피디아에 등록되어 있고 아래 두 조건을 모두 충족해야 한다.

- **왓챠피디아 리뷰 50개 이상** — RAG 데이터 확보 가능한 최소 기준
- **왓챠피디아 또는 IMDb 평점 6.0 (3.0/5.0) 이상** — 극단적 저품질 필터링

---

## 구성 비율

### 메이저 (1,500편 · 60%)

잘 알려진 영화. 사용자가 추천 시스템을 신뢰하게 만드는 "닻" 역할.

| 카테고리 | 편수 | 비율 | 선정 기준 |
|----------|------|------|-----------|
| 한국 흥행작 | 300 | 12% | 박스오피스 관객 100만 이상, 청룡·백상·대종 수상작 |
| 영미권 정통 명작 | 550 | 22% | IMDb Top 500, 아카데미 작품상 수상·노미네이션 |
| 아시아·유럽 대표작 | 250 | 10% | 칸·베를린·베네치아 수상, 지브리·신카이 등 |
| OTT 인기 오리지널 | 250 | 10% | 넷플릭스·왓챠 오리지널 중 국내 반응 좋은 작품 |
| 클래식 명작 (~1990s) | 150 | 6% | 시대별 필수 명작, 영화사적으로 중요한 작품 |

### 마이너 (1,000편 · 40%)

소수가 알고 강하게 좋아하는 영화. 추천의 신선함과 차별점을 담당.

| 카테고리 | 편수 | 비율 | 선정 기준 |
|----------|------|------|-----------|
| 한국 독립·마이너 | 280 | 11% | 관객 50만 미만, 독립영화, 전주·부산·인디포럼 출품작 |
| 영미권 컬트·장르 B급 | 300 | 12% | 컬트 클래식, 저예산 공포·SF·스릴러, 재평가된 B급 |
| 아시아·유럽 아트하우스 | 220 | 9% | 유럽 아트하우스, 아시아 독립영화, 비주류 감독 작품 |
| 장르 특화 마이너 | 200 | 8% | 호러·SF·애니메이션 서브장르 마이너 위주 |

---

## 마이너 선정 기준 상세

### 조작적 정의

"마이너하지만 코어팬층이 있는 영화" = **낮은 대중 인지도 + 본 사람들의 높은 만족도**

```
왓챠피디아 리뷰 수  :  50개 이상 ~ 500개 미만
왓챠피디아 평균 평점:  3.7 이상 (5점 만점)
박스오피스 관객 수  :  한국 영화 기준 50만 미만
                      해외 영화 기준 IMDb votes 5만 미만
```

세 조건을 모두 충족하면 마이너로 분류한다.

### 왓챠피디아 리뷰 수 기준표

| 리뷰 수 | 인지도 해석 | 분류 |
|---------|------------|------|
| 5,000개 이상 | 대중 메이저 (기생충·어벤져스급) | 메이저 |
| 500 ~ 5,000개 | 알 만한 사람은 아는 | 메이저 |
| **50 ~ 500개** | **소수가 알고 좋아하는** | **마이너 타깃** |
| 50개 미만 | 너무 마이너 → RAG 데이터 부족 | 제외 |

### 코어팬층 판별 보조 지표

리뷰 수와 평점 외에 별점 분포로 코어팬층 존재 여부를 파악할 수 있다.

- **5점 비율이 유독 높은 경우** — 강하게 좋아하는 팬층 존재
- **1점-5점 양극화 분포** — 호불호가 갈리지만 팬덤이 형성된 영화
- 단, 별점 분포 수집은 추가 크롤링 필요

---

## 마이너 발굴 소스

| 소스 | 활용 방법 |
|------|-----------|
| 왓챠피디아 장르별 인기순 | 흥행 필터 없이 리뷰 수 기준으로 탐색 |
| 레터박스드(Letterboxd) | 평균 평점 높은데 시청자 수 적은 영화 필터 |
| 부산·전주·인디포럼 | 역대 상영작 목록 |
| 씨네21 독자 추천 | 비평가·관객 엇갈리는 재평가 영화 |
| DC인사이드 영화 갤러리 | 장르 팬덤 기반 마이너 추천 |

---

## 메이저 발굴 소스

| 소스 | 커버 범위 |
|------|-----------|
| IMDb Top 1000 | 영미권 + 클래식 |
| 아카데미 수상·노미네이션 목록 | 영미권 정통 명작 |
| 칸·베를린·베네치아 수상 목록 | 유럽·아시아 대표작 |
| 한국 역대 박스오피스 TOP (2000~2026) | 한국 흥행작 |
| 넷플릭스·왓챠 오리지널 인기 순위 | OTT 인기작 |

---

## 다양성 체크리스트

리스트 완성 후 아래 항목을 점검한다.

- [ ] 한국 영화 비율 20~25% 이상
- [ ] 2020년 이후 신작 20% 이상 (최신성 확보)
- [ ] 1990년 이전 클래식 5~8%
- [ ] 공포·SF·애니메이션 각 장르 50편 이상
- [ ] 아시아권 (한국 제외) 영화 10% 이상
- [ ] 마이너 중 왓챠피디아 평점 3.7 이상 비율 확인

---

## 제외 기준

- 왓챠피디아 등록 없음
- 왓챠피디아 리뷰 50개 미만
- 평점 3.0/5.0 미만 (단순 저품질)
- 성인물·극단적 혐오 표현 포함작
- 팬심으로 찾아보는 공연 라이브 영화, 팬무비

---

## 영화 DB 스키마

### Django 모델 (`movies.Movie`)

컬럼은 두 그룹으로 나뉜다.

- **수집 필드** — `build_movie_db.py`가 채우는 값. `movie_db.csv`와 1:1 대응.
- **서비스 필드** — RAG 파이프라인·UI가 채우는 값. CSV에 없음.

#### 수집 필드

| 필드 | Django 타입 | 설명 | 한국 영화 | 외국 영화 |
|------|-------------|------|-----------|-----------|
| `tmdb_id` | IntegerField | TMDB 고유 ID — 글로벌 기준 키 | ✓ | ✓ |
| `title_ko` | TextField | 한국어 제목 (KMDb 우선 → TMDB ko-KR fallback) | ✓ | ✓ |
| `title_original` | TextField | 원어 제목 | ✓ | ✓ |
| `year` | IntegerField | 개봉연도 | ✓ | ✓ |
| `genres` | CharField | 장르 (쉼표 구분) | ✓ | ✓ |
| `director` | TextField | 감독 | ✓ | ✓ |
| `cast` | TextField | 주연 배우 상위 5명 (쉼표 구분) | ✓ | ✓ |
| `runtime` | IntegerField | 상영시간 (분) | ✓ | ✓ |
| `country` | CharField | 제작국가 ISO 코드 (쉼표 구분) | ✓ | ✓ |
| `language` | CharField | 원본 언어 ISO 639-1 | ✓ | ✓ |
| `overview_ko` | TextField | 한국어 줄거리 (KMDb 우선 → TMDB fallback) | ✓ | ✓ |
| `tmdb_rating` | FloatField | TMDB 평점 (0~10) | ✓ | ✓ |
| `tmdb_votes` | IntegerField | TMDB 투표 수 | ✓ | ✓ |
| `tmdb_popularity` | FloatField | TMDB 인기도 점수 | ✓ | ✓ |
| `audience_kr` | IntegerField | 국내 누적 관객 수 (KOBIS) | ✓ | null |
| `source_lists` | TextField | 출처 큐레이션 리스트명 (쉼표 구분) | ✓ | ✓ |
| `list_count` | IntegerField | 등장한 리스트 수 | ✓ | ✓ |
| `category` | CharField | 수집 카테고리 | ✓ | ✓ |
| `is_major` | BooleanField | 메이저(True) / 마이너(False) | ✓ | ✓ |
| `ott` | CharField | 한국 구독형 OTT (쉼표 구분, 정규화된 소문자) | ✓ | ✓ |
| `watcha_url` | URLField | 왓챠피디아 콘텐츠 URL (Step 2 이후 채워짐) | ✓ | ✓ |
| `collected_at` | DateTimeField | 수집 일시 (UTC) | ✓ | ✓ |

#### 서비스 필드

| 필드 | Django 타입 | 설명 | 채우는 주체 |
|------|-------------|------|-------------|
| `poster_path` | CharField | TMDB 포스터 경로 (`/xxxx.jpg`) | `build_movie_db.py` |
| `tone` | CharField | UI 포스터 색상 테마 (amber/rose/plum 등) | 수동 또는 자동 분류 |
| `combined_reviews` | TextField | 왓챠피디아 수집 리뷰 합본 | `watcha_crawl.py` (Step 3) |
| `llm_4pillar` | TextField | LLM이 생성한 4-Pillar 설명 | RAG 파이프라인 (Step 4) |
| `ott` | CharField | 한국 구독형 OTT — 향후 별도 테이블 분리 예정 (→ 향후 처리 사항 참고) | `build_movie_db.py` |
| `created_at` | DateTimeField | 레코드 생성 일시 (자동) | Django |
| `updated_at` | DateTimeField | 레코드 수정 일시 (자동) | Django |

### is_major 판정 기준

큐레이션 기반 수집이므로 TMDB 투표 수 대신 리스트 성격과 `list_count`로 판정한다.

| 조건 | 판정 |
|------|------|
| AFI·BFI·Sight&Sound·Empire·한국영화100선 등 권위 리스트 등재 | 메이저 |
| list_count ≥ 3 (복수 리스트 선정) | 메이저 |
| 독립영화제·아트하우스·장르 마이너 리스트 단독 등재 | 마이너 |
| TMDB vote_count 또는 audience_kr로 보조 검증 | 보조 지표 |

---

## 입력 파일 형식

두 개의 입력 파일을 별도로 사용한다.

### `data/foreign_movie_list.csv` — TMDB 기반 수집 (`crawl/build_foreign_list.py` 출력)

```csv
title,year,source_list,tmdb_id
Parasite,2019,TMDB_상위평점,496243
The Shawshank Redemption,1994,영미권_고평점,278
올드보이,2003,한국영화_상위평점,6217
```

- `tmdb_id` 컬럼 포함 → `build_movie_db.py`에서 TMDB 검색 스킵, 직접 상세조회
- 동일 영화가 여러 소스에 있으면 여러 행으로 저장 → `list_count` 자동 집계

### `data/korean_movie_list.csv` — KMDb 큐레이션 기반 수집

```csv
title,director,year,source_list
기생충,봉준호,2019,한국영화100선
하녀,김기영,1960,죽기 전에 꼭 봐야 할 영화 1001
달세계 여행(Voyage Dans la Lune),조르쥬 멜리에스,1902,죽기 전에 꼭 봐야 할 영화 1001
```

- `tmdb_id` 없음 → `build_movie_db.py`에서 TMDB 검색 수행
- `"한글(원어)"` 형식 제목은 괄호 안 원어를 추출해 검색 (예: `"Voyage Dans la Lune"`)
- 제목만 있는 TXT 파일 (줄당 1편)도 지원

---

## 진행 순서

### 스크립트 실행 순서 요약

```
[수집 단계] ─────────────────────────────────────────────────── 전체 3,826편 대상

  crawl/build_foreign_list.py       해외 영화 목록 수집
    └─ data/foreign_movie_list.csv 생성

  crawl/build_movie_db.py           영화 상세 정보 수집 (TMDB + KMDb + OTT)
    ├─ --from-list foreign_movie_list.csv  (1차, tmdb_id 있음 → 빠름)
    └─ --from-list korean_movie_list.csv   (2차, 검색 필요)
    └─ data/movie_db.csv 생성 / data/movie_db_unmatched.csv 생성

  crawl/enrich_ott.py               OTT 보강 + 미매칭 수동 보완분 추가
    └─ data/movie_db.csv 업데이트 (kmdb_id 제거, ott 컬럼 추가)

  python manage.py import_movies    CSV → Django DB import
    └─ movies.Movie 테이블 upsert (tmdb_id 기준)

[OTT 필터] ───────────────────────────────────── 이후 단계는 ott != '' 인 1,946편만

  crawl/map_watcha_url.py           왓챠피디아 URL 매핑  ⚠️ 미구현
    └─ data/movie_db.csv watcha_url 컬럼 업데이트

  crawl/watcha_crawl.py             왓챠피디아 리뷰 수집
    └─ data/review_db.csv / review_db.jsonl 생성

  rag_pipeline/                     임베딩 & 벡터 DB 구축
    └─ ChromaDB 인덱스 생성
```

| 스크립트 | 입력 | 출력 | 비고 |
|---|---|---|---|
| `crawl/build_foreign_list.py` | TMDB API | `foreign_movie_list.csv` | 재실행 가능 (append) |
| `crawl/build_movie_db.py` | `foreign/korean_movie_list.csv` | `movie_db.csv` | tmdb_id 기준 skip |
| `crawl/enrich_ott.py` | `movie_db.csv` | `movie_db.csv` (업데이트) | OTT 보강 + unmatched 추가 |
| `manage.py import_movies` | `movie_db.csv` | Django DB | tmdb_id 기준 upsert |
| `crawl/map_watcha_url.py` | `movie_db.csv` | `movie_db.csv` (업데이트) | **미구현** |
| `crawl/watcha_crawl.py` | `movie_db.csv` | `review_db.csv/.jsonl` | watcha_url 필요 |
| `rag_pipeline/` | `review_db.csv` | ChromaDB 인덱스 | — |

---

### Step 0 — 영화 리스트 수집 (`crawl/build_foreign_list.py`)

TMDB API로 카테고리별 영화 목록을 수집해 `data/foreign_movie_list.csv`를 생성한다.

**소스 구성 (2026-06 기준)**

| 소스 | 성격 | max_pages |
|------|------|-----------|
| TMDB_상위평점 | 메이저 | 25 |
| 영미권_고평점 | 메이저 | 20 |
| 클래식_명작 (~1990) | 메이저 | 10 |
| 아시아유럽_대표작 | 메이저 | 15 |
| 넷플릭스_인기 | 메이저 | 12 |
| 장르_공포 | 마이너 | 20 |
| 장르_SF | 마이너 | 20 |
| 장르_스릴러 | 마이너 | 18 |
| 장르_범죄 | 마이너 | 15 |
| 장르_드라마 (비영어권) | 마이너 | 15 |
| 아트하우스 (비영어권) | 마이너 | 20 |
| 애니메이션 | 마이너 | 18 |
| 한국영화_상위평점 | 한국 | 15 |
| 한국영화_인기작 | 한국 | 15 |

- 한국 영화 언어 제외 조건 없음 (모든 소스에서 `original_language=ko` 포함)
- `tmdb_id` + `source_list` 쌍 기준 중복 제거, append 방식으로 재실행 지원

### Step 1 — 영화 DB 구축 (`crawl/build_movie_db.py`)

두 입력 파일을 순서대로 실행해 `data/movie_db.csv`를 생성한다.

```
tmdb_id 있음 → TMDB 상세조회 직접 (검색 스킵)
tmdb_id 없음 → TMDB 검색 ("한글(원어)" 형식이면 원어 추출 후 검색) → 상세조회
언어 판단   → TMDB original_language 기준 (제목 기반 감지 없음)
한국 영화   → KMDB 보강 (title_ko, director, cast, overview_ko, audience_kr)
```

```bash
# 1차: tmdb_id 보유 → 검색 없이 직접 조회 (빠름)
python crawl/build_movie_db.py --from-list data/foreign_movie_list.csv

# 2차: tmdb_id 없음 → TMDB 검색 필요, 미매칭 확인 권장
python crawl/build_movie_db.py --from-list data/korean_movie_list.csv --report-unmatched
```

- TMDB 미매칭 시 `data/movie_db_unmatched.csv`에 별도 저장 → 수동 보완
- 중단 후 재실행 → 기존 `movie_db.csv`의 `tmdb_id` 기준으로 skip
- `.env`에 `KMDB_API_KEY` 없으면 한국 영화도 TMDB만 사용

### OTT 필터 기준

**Step 2부터는 `ott` 컬럼이 비어있지 않은 영화만 처리한다.**

서비스 타겟 페르소나는 OTT를 통해 영화를 보는 것이 루틴이므로, 당장 볼 수 없는 영화를 추천하는 것은 의미가 없다. OTT 계약이 추가되면 해당 영화는 자동으로 파이프라인에 포함된다.

| 구분 | 편수 | 비고 |
|------|------|------|
| 전체 수집 | 3,826편 | `movie_db.csv` 전체 |
| **OTT 있음 → 파이프라인 진행** | **1,946편** | Step 2~4 대상 |
| OTT 없음 → 보류 | 1,880편 | DB에는 존재, 추후 OTT 추가 시 자동 포함 |

카테고리별 통과율: 한국\_흥행작 69% / 영미권\_정통명작 47% / 영미권\_컬트장르 46% / 한국\_독립마이너 48% / 아시아유럽\_대표작 39%

---

### Step 2 — 왓챠피디아 URL 매핑 (`crawl/map_watcha_url.py`) *(미구현)*

`movie_db.csv`에서 **`ott != ''`인 영화만** 대상으로 왓챠피디아 URL을 자동 매핑한다.

1. 왓챠피디아 검색 자동화: `https://pedia.watcha.com/ko/search?query={title_ko}`
2. 제목 + 연도 일치 여부로 최적 결과 선택
3. `watcha_url` 컬럼 업데이트 후 저장

### Step 3 — 리뷰 DB 구축 (`crawl/watcha_crawl.py`)

`movie_db.csv`에서 **`ott != ''`인 영화**를 대상으로 왓챠피디아 리뷰를 수집한다.

```bash
# 쿠키 저장 (최초 1회)
python crawl/watcha_crawl.py --save-cookie

# 전체 수집 (OTT 보유 1,946편)
python crawl/watcha_crawl.py --from-csv

# 앞 N개만 테스트
python crawl/watcha_crawl.py --from-csv --limit 10
```

- 영화당 positive(평점 높은 순) 5개 + negative(평점 낮은 순) 5개 = 최대 10개
- `tmdb_id` 기준으로 resume 지원 (중단 후 재실행 시 이어서 수집)
- 결과: `data/review_db.csv`, `data/review_db.jsonl`

#### 영화 URL 매핑 로직 (2026-06-03 개선)

**문제: 제목 단독 검색의 한계**

초기 구현은 왓챠피디아 검색 결과에서 **첫 번째 `/ko/contents/` 링크를 무조건 사용**했다.
이로 인해 두 가지 오매핑이 발생했다.

1. **시리즈 오매핑** — "범죄도시 2"를 검색해도 검색 결과 1위는 "범죄도시 (2017)"이므로, 시리즈 전편이 항상 잡힌다.
2. **동명이제 오매핑** — 같은 제목의 다른 영화(한국/외국 리메이크, 연도 다른 동명작)가 먼저 노출될 경우 잘못된 URL 사용.

연도 단독 검증은 DB(TMDB)와 왓챠피디아 간에 1~2년 오차가 존재해 신뢰하기 어렵다.
감독명이 가장 정확하지만, 모든 영화에 감독명 검증용 추가 페이지 로드를 걸면 비효율적이다.

**해결: 3단계 검증 로직**

```
1. title_ko 로 검색 → 검색 결과 카드에서 연도 파싱
       ↓
2. 연도(±1) 필터로 후보 좁히기
   - 연도 매칭 결과 있음 → 그것만 남김
   - 연도 매칭 없음(파싱 실패 or 전부 불일치) → 전체 유지
       ↓
3. 후보 수에 따라 분기
   - 0개 → title_original 로 재검색 후 동일 연도 필터 재적용
   - 1개 → 바로 사용 (추가 페이지 로드 없음)
   - 2개 이상 → 각 후보 상세 페이지에서 감독명 파싱 → 일치하는 것 사용
               → 감독 매칭도 실패 시 첫 번째 후보 사용
```

**핵심 아이디어**

- 시리즈("범죄도시 1/2/3")는 연도가 다르므로 연도 필터만으로 해결된다.
- 진짜 동명 영화(같은 제목, 같은 연도)는 극히 드물고, 그때만 감독 검증 비용이 발생한다.
- 외국 영화는 `title_original`(영어 원제)로 재검색하면 히트율이 높아진다.
- `movie_db.csv`에 `year`, `director`, `title_original`이 모두 있으므로 추가 API 호출 불필요.

**미해결 버그 — 콘텐츠 타입 미구분 (2026-06-06 발견)**

왓챠피디아 URL의 콘텐츠 ID 첫 글자가 타입을 구분한다.

| 접두어 | 타입 |
|--------|------|
| `m` | 영화 |
| `t` | TV 시리즈·예능 |

`_parse_search_results`는 `/ko/contents/[A-Za-z0-9]+` 패턴으로 모든 링크를 수집하므로 예능·시리즈도 후보에 포함된다. 이후 연도 파싱 실패 → 연도 필터 무력화 → 감독 필드 없음 → 감독 매칭 실패 → 첫 번째 후보 채택 순으로 폴백이 연속 통과되어 오매핑이 발생한다.

`verify_result.csv` 기준 `t` 접두어 오매핑 확인된 8편:

| tmdb_id | 제목 | 잘못 매핑된 watcha_id |
|---------|------|----------------------|
| 524 | 카지노 | tEqZBoD |
| 745 | 식스 센스 | tE3A2v5 |
| 787 | 미스터 & 미세스 스미스 | tPeWKb6 |
| 832 | 엠 | tRX5mMx |
| 2671 | 링 | tPDOyq1 |
| 2756 | 어비스 | tE0memx |
| 14160 | 업 | tPJZXK9 |
| 14638 | 살인자들 | tPy8pap |

**수정 방법:**
- `_parse_search_results`에서 `m`으로 시작하는 콘텐츠 ID만 수집하도록 필터 추가
- `review_db.csv`에서 위 8개 tmdb_id 행 삭제 후 재크롤링 필요
- `verify_result.csv` 검증 범위에 포함되지 않은 영화도 동일 버그 영향을 받았을 가능성 있음 (watcha_url=NaN 상태로 검색 경로를 탄 영화들)

#### `review_db.csv` 스키마

| 필드 | 타입 | 설명 |
|------|------|------|
| `tmdb_id` | int | **PK** — `movie_db.csv`와의 JOIN 기준 |
| `title_ko` | str | 한국어 제목 (`movie_db.csv`와 동일 컬럼명) |
| `watcha_id` | str | 왓챠피디아 콘텐츠 ID (URL 마지막 segment, 예: `mdRL4eL`) |
| `reviewer` | str | 리뷰어 닉네임 |
| `rating` | float | 별점 (0.5 ~ 5.0) |
| `raw_text` | str | 리뷰 원문 (LLM 프롬프트용) |
| `clean_text` | str | 전처리된 텍스트 (임베딩용) |
| `likes` | int | 좋아요 수 |
| `has_spoiler` | bool | 스포일러 포함 여부 |
| `sentiment` | str | `"positive"` / `"negative"` |
| `rank` | int | sentiment 내 순위 (1-based) |
| `crawled_at` | str | 수집 일시 (UTC ISO 8601) |

### Step 4 — RAG 인덱스 구축 (`rag_pipeline/`)

---

## 향후 처리 사항

### OTT 스키마 개선

현재 `Movie.ott` 컬럼에 `"Netflix, wavve, TVING"` 형태의 텍스트로 저장 중 (1,594편 데이터 보유).
OTT 기반 필터링 기능 구현 시점에 별도 `OttAvailability` 테이블로 분리한다.

```
OttAvailability
  movie     FK → Movie
  provider  CharField  # "netflix", "watcha", "tving", "wavve", "disney", "amazon"
  region    CharField  # 기본 "KR"
  checked_at DateTimeField
  unique_together: (movie, provider, region)
```

- 기존 `ott` 문자열 파싱 → 행 단위로 변환하는 데이터 마이그레이션 필요
- provider 정규화: `Netflix Standard with Ads` → `netflix`, `Disney Plus` → `disney`, `Watcha` → `watcha` 등

---

### Step 4 — RAG 인덱스 구축 (`rag_pipeline/`)

수집된 리뷰를 임베딩해 벡터 DB에 저장한다.

1. `review_db.csv`의 `clean_text` 임베딩 (sentence-transformers)
2. ChromaDB에 저장 — metadata에 `tmdb_id`, `title_ko`, `genres`, `is_major` 포함
3. 검색 및 추천 쿼리 테스트

---

## 데이터 현황 (2026-06-05 기준)

### movie_db.csv

| 항목 | 수치 |
|------|------|
| 전체 영화 | 3,836편 |
| OTT 보유 (파이프라인 대상) | 1,946편 (50.7%) |
| 메이저 | 1,623편 (42.3%) |
| 마이너 | 2,193편 (57.1%) |
| `overview_ko` 보유 | 3,505편 (91.4%) |
| `origin_country` 컬럼 | ❌ 없음 — `country` 컬럼 사용 중 |

**제작국가 상위 5**

| 국가 | 편수 |
|------|------|
| US | 1,751 |
| KR | 953 |
| GB | 348 |
| FR | 329 |
| JP | 289 |

**장르 상위 5** (중복 허용)

| 장르 | 편수 |
|------|------|
| 드라마 | 2,044 |
| 코미디 | 870 |
| 스릴러 | 845 |
| 액션 | 767 |
| 범죄 | 624 |

**OTT 플랫폼별 편수** (중복 허용)

| 플랫폼 | 편수 |
|--------|------|
| watcha | 936 |
| netflix | 729 |
| wavve | 603 |
| tving | 582 |
| disney | 294 |

---

### review_db.csv

| 항목 | 수치 |
|------|------|
| 총 리뷰 수 | 19,012개 |
| 커버 영화 수 | 1,934편 |
| 미수집 (OTT 보유 기준) | 12편 — 왓챠피디아 미등록 또는 리뷰 0개 |
| 스포일러 포함 리뷰 | 555개 (2.9%) |
| 빈 `clean_text` | 39개 (0.2%) — 전처리 후 텍스트가 사라진 케이스 |

**sentiment별 통계**

| 구분 | 평점 평균 | 리뷰 길이 평균 | 리뷰 길이 중앙값 | 최장 리뷰 |
|------|-----------|----------------|-----------------|-----------|
| positive | 4.79★ | 150자 | 51자 | 9,989자 |
| negative | 0.96★ | 91자 | 33자 | 6,907자 |

- positive 리뷰가 negative보다 평균 1.6배 더 길게 작성됨
- 좋아요 최다 리뷰: 라라랜드 10,514 / 헤어질 결심 6,856 (모두 positive 5.0★)

---

### 데이터 품질 주의사항

1. ~~**`review_db.csv` NUL 바이트 포함**~~ — ✅ **2026-06-05 완료** (4개 제거, `pd.read_csv()` 정상 동작 확인)

2. ~~**왓챠피디아 URL 오매핑 SUSPECT 66편**~~ — ✅ **2026-06-05 완료**
   - `verify_watcha_mapping.py` 로 391편 검증 → SUSPECT 66편 식별
   - `watcha_crawl.py --from-verify data/verify_result.csv` 로 기존 리뷰 삭제 후 재수집
   - `--from-verify` 옵션은 `_remove_reviews()` 로 old 데이터 삭제 → fresh 재검색 순서로 동작 (중복 없음)
   - `movie_db.csv` 파싱 오류(`ParserError: Buffer overflow`) → `engine='python', on_bad_lines='skip'` 추가로 해결

3. **`t` 접두어 오매핑 8편** — `watcha_crawl.py`의 `_parse_search_results`가 영화(`m`)·예능/시리즈(`t`) 구분 없이 모든 `/ko/contents/` URL을 수집한다. 연도 파싱 실패 + 감독 필드 없음으로 폴백이 연속 통과돼 예능 페이지가 영화로 오매핑됨. → **미완료**: `review_db.csv` 8편 삭제 + 크롤러 수정(`m` 접두어 필터 추가) 필요.

4. **`clean_text` 빈 행 39개** — 이모지·해시태그만 있던 리뷰가 전처리 후 빈 문자열이 된 케이스. 임베딩 전 필터 필요.

5. ~~**`overview_ko` 누락 8.6%`**~~ — ✅ **2026-06-05 대응 완료**
   - `crawl/fetch_watcha_overview.py` 로 왓챠피디아 콘텐츠 페이지에서 줄거리 스크래핑 → `movie_db.csv` 업데이트
   - `og:description` 메타 태그 우선, hashed class(`_synopsis_` 등) 순으로 시도
   - watcha_url 없는 경우 `review_db.csv`의 `watcha_id`로 URL 재구성

6. ~~**`movie_db.csv` 스키마 불일치**~~ — ✅ **2026-06-05 완료**
   - `rag_pipeline/00_enrich_tmdb.py` 완전 재작성: TMDB API 재호출 없이 `movie_db.csv + review_db.csv` 병합
   - 컬럼 매핑: `title_ko→movie_title`, `genres→tmdb_genres`, `overview_ko→tmdb_overview` 등
   - 출력: `data/movie_enriched.csv`

7. **리뷰 없는 영화 인덱스 제외** — ✅ **2026-06-05 완료**
   - `00_enrich_tmdb.py`에서 `combined_reviews == ''` 영화를 명시 출력 후 제외 (약 12편)

---

## 다음 스텝 — Step 4: RAG 파이프라인 구축

### 실행 순서

```
[전처리] ✅ 완료
  data/review_db.csv  NUL 바이트 제거 (2026-06-05)
  verify_result.csv   SUSPECT 66편 재수집 (2026-06-05)

[Step 4-A] enriched_text 생성
  crawl/fetch_watcha_overview.py     overview_ko 없는 OTT 영화 왓챠에서 보강
    └─ data/movie_db.csv 업데이트

  rag_pipeline/00_enrich_tmdb.py    movie_db.csv + review_db.csv 병합
    └─ data/movie_enriched.csv 생성
    └─ 리뷰 없는 영화(~12편) 자동 제외

[Step 4-B] 4-Pillar LLM 설명 생성
  rag_pipeline/00b_4pillar.py
    - Ollama + EXAONE 3.5:2.4b 로컬 추론
    - 감성/무드 · 소재/테마 · 관람 상황 · 스타일 2문장 생성
    - 체크포인트: output/4pillar_cache.json (중단 후 재실행 지원)
    └─ data/movie_enriched.csv (llm_4pillar + enriched_text 갱신)

[Step 4-C] 리뷰 LLM 요약 — 구조화된 5개 필드 생성  ← 개선 예정 (아래 참조)
  rag_pipeline/00c_summarize_reviews.py
    - Gemini 2.0 Flash, 영화 1편당 API 1회
    - 체크포인트: output/review_summary_cache.json
    └─ data/movie_enriched.csv (5개 컬럼 추가 + enriched_text 재구성)

[Step 4-D] 임베딩 + ChromaDB 저장
  rag_pipeline/01_chunk.py → 02_embed_store.py
    - 모델: BAAI/bge-m3 (영화 1편 = 벡터 1개)
    └─ chroma_db/

[Step 4-E] 검색 테스트
  rag_pipeline/03_query_parser.py → 04_rag_search.py
```

### 우선 해결해야 할 것

| 항목 | 내용 |
|------|------|
| ~~① NUL 바이트 제거~~ | ✅ 완료 (2026-06-05) |
| ~~② `00_enrich_tmdb.py` 입력 수정~~ | ✅ 완료 (2026-06-05) — `movie_db.csv + review_db.csv` 기반으로 재작성 |
| ~~③ `overview_ko` fallback~~ | ✅ 완료 (2026-06-05) — `fetch_watcha_overview.py` 로 왓챠에서 보강 |
| ~~④ `clean_text` 빈 행 필터~~ | ✅ 완료 (2026-06-05) — 리뷰 없는 영화 인덱스 제외 처리 |
| ⑤ `fetch_watcha_overview.py` 실행 | CSS 셀렉터 실제 페이지 확인 필요 (`--no-headless` 권장) |

---

## 00c_summarize_reviews.py 개선 방향 (2026-06-05)

### 문제 — 기존 2필드 요약의 한계

초기 설계(`pros_summary` + `cons_summary` 각 2문장)는 "이 영화가 어떤 영화인가"는 담지만, 사용자의 실제 쿼리 패턴과 맞지 않는다.

실제 쿼리 예시:
- "혼자 볼 때 좋은 영화 추천해줘"
- "데이트할 때 볼 만한 거 없을까"
- "울고 싶을 때 보는 영화"
- "가볍게 웃으면서 볼 수 있는 영화"
- "몰입해서 볼 수 있는 긴장감 있는 영화"

이런 쿼리는 **상황 + 감성 + 동반자** 정보가 핵심인데, 기존 요약에서는 이 정보가 산발적으로 녹아있거나 빠져있다.

### 개선 방향 — 5개 구조화 필드

LLM 1회 호출에서 아래 5개 필드를 JSON으로 받는다.

| 필드 | 용도 | 형식 |
|------|------|------|
| `mood_keywords` | enriched_text 포함 (임베딩) | 키워드 3-5개, 쉼표 구분 |
| `target_audience` | enriched_text 포함 (임베딩) | 1문장 |
| `viewing_context` | enriched_text 포함 (임베딩) | 1문장 |
| `pros_summary` | enriched_text 포함 (임베딩) | 2문장 |
| `cons_summary` | ChromaDB metadata만 저장 (리랭킹용) | 2문장 |

**`mood_keywords`** — 감성·분위기를 나타내는 한국어 키워드
- 예: `"감동적, 따뜻한, 잔잔한, 힐링, 가족애"`
- 쿼리 "힐링 영화", "따뜻한 영화"의 임베딩 매칭 정확도를 높임

**`target_audience`** — 어떤 취향/성향의 사람에게 맞는지 1문장
- 예: `"감성적인 멜로를 좋아하는 분, 잔잔한 여운을 원하는 분에게 잘 맞습니다"`
- 쿼리 "나한테 맞는 영화" 등 취향 기반 쿼리 매칭

**`viewing_context`** — 언제, 누구와 보면 좋은지 1문장
- 예: `"혼자 조용한 밤에, 또는 연인과 함께 감성적인 분위기에서 보기 좋습니다"`
- 쿼리 "혼자 볼 때", "데이트 영화" 등 상황 기반 쿼리 매칭

**`pros_summary`** — 영화의 구체적 매력 포인트 2문장 (기존 동일)

**`cons_summary`** — 아쉬운 점 + 맞지 않는 관객 2문장 → **임베딩 제외, 메타데이터에만 저장**
- 부정 신호가 임베딩에 섞이면 코사인 유사도를 희석시키기 때문
- 리랭킹 노드에서 필터링 기준으로 활용

### 개선된 enriched_text 구성

```
장르: {tmdb_genres}
추천설명: {llm_4pillar}
줄거리: {tmdb_overview}
분위기: {mood_keywords}
추천대상: {target_audience}
시청상황: {viewing_context}
리뷰: {pros_summary}
```

기존 대비 변경:
- `리뷰: combined_reviews` → `리뷰: pros_summary` (이전 개선분)
- `분위기: mood_keywords` 신규 추가
- `추천대상: target_audience` 신규 추가
- `시청상황: viewing_context` 신규 추가

### 개선된 프롬프트 설계

```
[영화 정보]
- 장르: {genres}
- 줄거리: {overview}

[관람객 긍정 리뷰]
{positive_reviews}

[관람객 부정 리뷰]
{negative_reviews}

위 리뷰와 영화 정보를 바탕으로 아래 JSON만 출력하세요.

{
  "mood_keywords": "이 영화의 분위기·감성을 나타내는 키워드 3-5개 (쉼표 구분). 예: 감동적, 잔잔한, 따뜻한",
  "target_audience": "어떤 취향과 성향의 사람에게 잘 맞는지 1문장",
  "viewing_context": "언제 누구와 보기 좋은지 구체적인 상황 1문장",
  "pros_summary": "이 영화만의 구체적인 매력을 2문장으로. 장르 클리셰 말고 리뷰에서 드러난 실제 강점 위주로.",
  "cons_summary": "이 영화의 아쉬운 점과 맞지 않는 관객을 2문장으로."
}
```

장르·줄거리를 추가로 제공하는 이유: 리뷰만으로는 배경 맥락이 부족해 LLM이 장르 중립적인 표현만 생성하는 경향이 있음. 영화 정보를 함께 넘기면 로맨스 영화의 "설레는", 공포 영화의 "긴장감", SF의 "스케일" 같은 장르별 감성 표현이 자연스럽게 나옴.

### 스키마 변경 요약

#### `output/review_summary_cache.json` (캐시 구조)

```json
{
  "12345": {
    "mood_keywords": "감동적, 따뜻한, 잔잔한",
    "target_audience": "...",
    "viewing_context": "...",
    "pros_summary": "...",
    "cons_summary": "..."
  }
}
```

기존 `pros_summary` + `cons_summary` 2개 → 5개 필드로 확장.

#### `data/movie_enriched.csv` 신규 컬럼

| 컬럼 | 기존 | 변경 |
|------|------|------|
| `pros_summary` | ✅ 있음 | 유지 |
| `cons_summary` | ✅ 있음 | 유지 |
| `mood_keywords` | ❌ 없음 | **신규 추가** |
| `target_audience` | ❌ 없음 | **신규 추가** |
| `viewing_context` | ❌ 없음 | **신규 추가** |
| `enriched_text` | 있음 | 재구성 (위 5개 반영) |

#### ChromaDB Document 메타데이터

| 필드 | 기존 | 변경 |
|------|------|------|
| `cons_summary` | ✅ 저장 | 유지 |
| `mood_keywords` | ❌ | **신규** — 필터 및 디버깅용 |
| `target_audience` | ❌ | 저장 불필요 (enriched_text에 포함) |
| `viewing_context` | ❌ | 저장 불필요 (enriched_text에 포함) |

### 파이프라인 영향 범위

변경이 필요한 스크립트:

| 스크립트 | 변경 내용 |
|----------|-----------|
| `rag_pipeline/00c_summarize_reviews.py` | 프롬프트 + JSON 필드 5개, `rebuild_enriched_text()` 재구성 |
| `rag_pipeline/01_chunk.py` | `META_EXTRA`에 `mood_keywords` 추가 |
| `rag_pipeline/02_embed_store.py` | Document 메타데이터에 `mood_keywords` 추가 |

변경 불필요:
- `00_enrich_tmdb.py` — 리뷰 병합까지만 담당, 요약 컬럼은 00c가 추가
- `00b_4pillar.py` — 독립 실행, 영향 없음
- `03_query_parser.py`, `04_rag_search.py` — 검색 로직 변경 없음 (메타데이터 필드 추가만)
