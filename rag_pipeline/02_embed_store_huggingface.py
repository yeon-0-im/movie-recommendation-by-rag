"""
[STEP 2-B] 임베딩 + 벡터 스토어 — HuggingFaceEmbeddings 비교 버전

02_embed_store.py (BGE-M3) 와 비교하기 위한 파일.
모델만 다르고 나머지 구조는 동일하다.

  비교 모델: paraphrase-multilingual-MiniLM-L12-v2
  vs 기본 모델: BAAI/bge-m3

  HuggingFaceEmbeddings vs HuggingFaceBgeEmbeddings
  - HuggingFaceEmbeddings    : 범용 래퍼, 어떤 sentence-transformers 모델도 사용 가능
  - HuggingFaceBgeEmbeddings : BGE 계열 특화 래퍼, query_instruction 자동 적용

  paraphrase-multilingual-MiniLM-L12-v2 특징:
  - 50개 이상 언어 지원 (한국어 포함)
  - 벡터 차원: 384 (bge-m3의 1024보다 작음 → 속도 빠름, 표현력 낮음)
  - 모델 크기: ~118MB (bge-m3의 ~570MB보다 가벼움)

  결과 저장 경로를 chroma_db_hf/ 로 분리해
  bge-m3 결과(chroma_db/)를 덮어쓰지 않는다.

실행: python3 pipeline/02_embed_store_huggingface.py
전제: output/movie_chunks.json 존재 (01_chunk.py 먼저 실행)
출력: chroma_db_hf/
"""

import json
import time
import shutil
import torch
from pathlib import Path

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

# --- 설정값 ---
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
CHROMA_PATH = "./chroma_db_hf"
COLLECTION_NAME = "movie_reviews_hf"
CHUNKS_PATH = "output/movie_chunks.json"


def get_device() -> str:
    """Apple Silicon MPS → CUDA → CPU 순으로 가속 디바이스 선택."""
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def load_docs() -> tuple[list[Document], list[str]]:
    """JSON 청크를 LangChain Document 객체로 변환."""
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    docs = [
        Document(
            page_content=c["text"],
            metadata={
                "movie_title": c["movie_title"],
                "chunk_index": c["chunk_index"],
                "total_chunks": c["total_chunks"],
            },
        )
        for c in raw
    ]
    ids = [c["id"] for c in raw]

    print(f"Document 로드: {len(docs):,}개")
    return docs, ids


def main():
    print("=" * 60)
    print("[STEP 2-B] 임베딩 + ChromaDB 저장 (HuggingFaceEmbeddings)")
    print("=" * 60)

    docs, ids = load_docs()
    device = get_device()

    # 1. 임베딩 모델 초기화
    #    HuggingFaceEmbeddings: 범용 래퍼 (BGE 특화 아님)
    print(f"\n임베딩 모델 로드 중...")
    print(f"  모델    : {MODEL_NAME}")
    print(f"  디바이스: {device}")

    embeddings = HuggingFaceEmbeddings(
        model_name=MODEL_NAME,
        model_kwargs={"device": device},
        encode_kwargs={"normalize_embeddings": True},
    )

    dim = len(embeddings.embed_query("test"))
    print(f"  벡터 차원: {dim}  (bge-m3: 1024)")

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
    print(f"\n비교 검색 → python3 pipeline/03_rag_search.py 에서 CHROMA_PATH / COLLECTION_NAME 변경")


if __name__ == "__main__":
    main()
