💻 ㅇㅎㅊㅊ 기술 아키텍처 및 RAG 구현 명세서## 1. 시스템 아키텍처 (System Architecture)본 서비스는 로컬 메모리/파일 기반의 **ChromaDB**를 Vector DB로 사용하고, 백엔드는 **Django + MariaDB**, AI 프론트엔드 파이프라인은 오픈소스 임베딩 모델과 실시간 RAG(Retrieval-Augmented Generation) 연동 구조를 채택하여 초기 인프라 비용을 극단적으로 최적화합니다.
[클라이언트: HTML + Tailwindcss]
│ ▲
(자연어 쿼리)│ │ (RAG 추천 결과 및 사유)
▼ │
[Django 웹 서버] ── (세션 및 필터 정보) ──> [MariaDB]
│ ▲
(임베딩 쿼리)│ │ (유사도 검색 Top-K)
▼ │
[ChromaDB (로컬)] <── (정제 데이터 적재) ── [오프라인 데이터 전처리 파이프라인]
---
## 2. 오프라인 데이터 전처리 및 임베딩 파이프라인
날것의 리뷰 데이터를 임베딩 영역에 그대로 넣으면 노이즈가 발생하므로, 반드시 **1차 전처리**를 거쳐 의미적 밀도를 높여야 합니다.
### 2.1. 데이터 전처리 (LLM Preprocessing)* 
**소스 데이터:** KMDb API (줄거리 및 메타데이터) + NSMC/네이버 공개 리뷰 데이터셋 (관람객의 실제 맥락)* 
**전처리 파이프라인 스크립트:**  Python 스크립트를 작성하여 수집한 영화 리뷰들을 가볍고 가성비 좋은 LLM API(예: Gemini 1.5 Flash 등)를 거쳐 4-Pillar Taxonomy 양식의 JSON으로 압축 정제합니다.
### 2.2. 청킹(Chunking) 및 임베딩 모델 선정* 
**임베딩 모델:** `BAAI/bge-m3` (다국어 및 한국어 맥락 처리가 우수하며 무료 오픈소스)* 
**청킹 전략 (Semantic Chunking):**  * 글자 수 기준의 무작위 커팅을 배제하고, 리뷰 문장 간의 문맥이 유지되도록 앞뒤 문장을 15% 가량 오버랩하는 **Sentence-Window 청킹**을 적용합니다.  * 영화 1편당 생성되는 정제된 컨텍스트 청크 개수를 **10~20개 내외로 제한**하여, ChromaDB 검색 효율성과 컴퓨팅 RAM 부하를 방지합니다.
### 2.3. 벡터 용량 및 RAM 부하 산정
벡터 데이터베이스가 차지하는 대략적인 메모리 용량은 다음 공식으로 계산됩니다.$$\text{RAM 사용량} \approx N \times D \times 4 \text{ Bytes}$$BGE-m3 모델을 사용하여 1,000편의 영화에 대해 각각 15개의 정제 청크를 생성할 경우 ($N = 15,000$, 차원 수 $D = 1024$):$$15,000 \times 1024 \times 4 \text{ Bytes} \approx 61.44 \text{ MB}$$* 
**결론:** 로컬 메모리 기반 ChromaDB를 구성하더라도 100MB 이하의 극도로 가벼운 스토리지 환경에서 구동이 가능하므로 프리티어 클라우드 인스턴스에서 원활히 동작합니다.
---
## 3. 데이터베이스 스키마 설계
### 3.1. MariaDB (RDBMS - Django Models)
```python
# movies/models.pyfrom django.db import modelsimport uuidclass MovieMaster(models.Model):    movie_id = models.CharField(max_length=50, primary_key=True)  
# TMDB ID    title_kr = models.CharField(max_length=255)    release_year = models.IntegerField()    country = models.CharField(max_length=10)  
# KR, US, GB 등    poster_url = models.URLField(max_length=500, null=True)    ott_links = models.JSONField(default=dict)  
# {"netflix": "url", "tving": "url"}class ChatSession(models.Model):    session_id = models.UUIDField(primary_key=True, default=uuid.uuid4)    user_id = models.CharField(max_length=100, null=True)    created_at = models.DateTimeField(auto_now_add=True)    negative_filters = models.JSONField(default=dict)  
# {"country": ["KR"], "genres": ["Horror"]} ```

3.2. ChromaDB (Vector DB Metadata Payload)
{  "id": "M10284_chunk_01",  "values": [0.012, -0.045, 0.551, "..."],  // bge-m3 임베딩 벡터  "metadata": {    "movie_id": "M10284",    "country": "US",    "release_year": 2006,    "situation": "퇴근, 상사스트레스, 번아웃",    "vibe": "통쾌함, 동기부여, 대리만족",    "sensory": "패셔너블, 세련된 영상미",    "cognitive_load": "Low",    "clean_context": "업무 스트레스가 극에 달해 머리를 비우고 싶을 때, 악독한 상사 아래서 주인공이 성장해나가는 미장센 가득한 영상미를 즐기며 통쾌하게 스트레스를 푸는 영화."  }}

4. 실시간 RAG 피드백 루프 작동 메커니즘
사용자가 추천된 결과를 거절하거나 세부 필터를 적용할 때, 실시간으로 ChromaDB의 검색 쿼리를 튜닝하는 알고리즘 단계입니다.
	•	세션 필터 변경: 유저가 "한국 영화 제외" 클릭 시, Django 서버는 세션(ChatSession)의 negative_filters에 {"country": ["KR"]}를 업데이트합니다.
	•	하이브리드 필터 쿼리 구성: ChromaDB에 벡터 유사도 검색을 요청할 때 메타데이터 필터 옵션을 추가하여 검색 후보군에서 원천 배제합니다.
    # ChromaDB Query Python 의사코드results = collection.query(    query_embeddings=[query_vector],    n_results=3,    where={"country": {"$ne": "KR"}}  # 부정 피드백 실시간 쿼리 주입)
	•	LLM 최종 RAG 추천 사유 생성: 추출된 Top-K 영화 리스트의 clean_context 데이터들을 가져와 LLM(Gemini / OpenAI API)에 컨텍스트로 전달하여 추천 이유 텍스트를 완성한 후 프론트엔드로 전달합니다.