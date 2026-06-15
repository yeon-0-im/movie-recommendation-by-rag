"""
[STEP 2] 임베딩(Embedding) + 벡터 스토어(Vector Store) — LangChain 버전

LangChain의 HuggingFaceBgeEmbeddings와 Chroma를 사용합니다.
이전 버전에서 직접 작성했던 배치 루프가 Chroma.from_documents() 한 줄로 대체됩니다.

  HuggingFaceBgeEmbeddings란?
  - sentence-transformers 위에 올린 LangChain 래퍼
  - embed_documents(texts) / embed_query(text) 인터페이스를 제공
  - LangChain 내부에서 이 인터페이스를 통해 임베딩을 호출한다.
  - encode_kwargs={"normalize_embeddings": True}: 코사인 유사도를 위한 정규화

  Chroma.from_documents()란?
  - Document 리스트를 받아 임베딩 + ChromaDB 저장을 한 번에 처리
  - 내부적으로 배치 분할 및 저장을 자동 관리
  - 반환값: 검색에 바로 쓸 수 있는 Chroma vectorstore 객체

실행: python3 pipeline/02_embed_store.py
전제: output/movie_chunks.json 존재 (01_chunk.py 먼저 실행)
출력: chroma_db/
"""

import json
import time
import shutil
import torch
from pathlib import Path

from langchain_huggingface import HuggingFaceEmbeddings as HuggingFaceBgeEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

# --- 설정값 ---
MODEL_NAME = "BAAI/bge-m3"
CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "movie_reviews"
CHUNKS_PATH = "output/movie_chunks.json"


def get_device() -> str:
    """CUDA → CPU 순으로 선택. MPS는 긴 시퀀스 attention 시 버퍼 오버플로 발생."""
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def load_docs() -> tuple[list[Document], list[str]]:
    """JSON 청크를 LangChain Document 객체로 변환."""
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    TMDB_COLS = [
        "tmdb_director", "tmdb_genres", "tmdb_cast", "tmdb_country",
        "tmdb_release_year", "tmdb_runtime", "tmdb_language", "tmdb_ott",
    ]
    META_EXTRA = [
        "pos_property_tags", "pos_tones",
        "neg_property_tags", "neg_tones",
        "focused_summary_neg",
    ]

    docs = [
        Document(
            page_content=c["text"],
            metadata={
                "tmdb_id":     c.get("tmdb_id", 0),
                "movie_title": c["movie_title"],
                **{col: c[col] for col in TMDB_COLS if col in c},
                **{col: c[col] for col in META_EXTRA if col in c},
            },
        )
        for c in raw
    ]
    ids = [c["id"] for c in raw]

    print(f"Document 로드: {len(docs):,}개")
    return docs, ids


def main():
    print("=" * 60)
    print("[STEP 2] 임베딩 + ChromaDB 저장 (LangChain 버전)")
    print("=" * 60)

    docs, ids = load_docs()
    device = get_device()

    # 1. 임베딩 모델 초기화
    #    HuggingFaceBgeEmbeddings: sentence-transformers의 LangChain 래퍼
    print(f"\n임베딩 모델 로드 중...")
    print(f"  모델    : {MODEL_NAME}")
    print(f"  디바이스: {device}")

    embeddings = HuggingFaceBgeEmbeddings(
        model_name=MODEL_NAME,
        model_kwargs={"device": device},
        encode_kwargs={"normalize_embeddings": True, "batch_size": 16},
    )

    # 2. 기존 DB 초기화
    if Path(CHROMA_PATH).exists():
        shutil.rmtree(CHROMA_PATH)
        print(f"\n  기존 DB 삭제 후 재생성: {CHROMA_PATH}")

    # 3. 임베딩 + ChromaDB 저장 (한 번에 처리)
    print(f"\nChroma.from_documents() 실행 중...")
    print(f"  문서 {len(docs):,}개 임베딩 + 저장 (자동 배치 처리)")

    start = time.time()
    vectorstore = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        ids=ids,
        persist_directory=CHROMA_PATH,
        collection_name=COLLECTION_NAME,
        collection_metadata={"hnsw:space": "cosine"},
    )
    elapsed = time.time() - start

    count = vectorstore._collection.count()
    print(f"\n완료: {count:,}개 벡터 ({elapsed:.1f}초, {elapsed/len(docs)*1000:.1f}ms/청크)")
    print(f"저장 경로: {CHROMA_PATH}/")
    print(f"\n다음 단계 → python3 pipeline/04_rag_search.py")


if __name__ == "__main__":
    main()
