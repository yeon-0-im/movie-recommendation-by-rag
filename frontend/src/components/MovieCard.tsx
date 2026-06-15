import type { Movie } from "@/lib/types";
import Poster from "./Poster";

interface CardProps {
  movie: Movie;
  index: number;
  onOpen: (movie: Movie) => void;
  onSwap: (movie: Movie) => void;
}

export function MovieCardList({ movie, index, onOpen, onSwap }: CardProps) {
  return (
    <div className="mcard mcard--list">
      {/* 상단: 번호 + 제목 + 썸네일 포스터 */}
      <div className="mcard__header">
        <span className="mcard__rank">{String(index + 1).padStart(2, "0")}</span>
        <button className="mcard__titles" onClick={() => onOpen(movie)}>
          <h3 className="mcard__title">{movie.title}</h3>
          <p className="mcard__meta">
            {[movie.year, movie.genres].filter(Boolean).join(" · ")}
          </p>
        </button>
        <button className="mcard__poster-btn" onClick={() => onOpen(movie)} aria-label={movie.title + " 상세"}>
          <Poster movie={movie} className="poster--thumb" />
        </button>
      </div>

      {/* 추천 이유 — 카드의 핵심 컨텐츠 */}
      {(movie.custom_pitch || movie.llm_4pillar) && (
        <p className="mcard__pitch" onClick={() => onOpen(movie)}>
          {movie.custom_pitch || movie.llm_4pillar}
        </p>
      )}

      <div className="mcard__actions">
        <button className="ghostbtn" onClick={() => onSwap(movie)}>다른 거 보여줘</button>
        <button className="linkbtn" onClick={() => onOpen(movie)}>자세히 →</button>
      </div>
    </div>
  );
}

export function MovieCardGrid({ movie, index, onOpen, onSwap }: CardProps) {
  return (
    <div className="mcard mcard--grid">
      <button className="mcard__hit" onClick={() => onOpen(movie)} aria-label={movie.title + " 상세"}>
        <Poster movie={movie} className="poster--grid" />
        <span className="mcard__rank mcard__rank--float">{String(index + 1).padStart(2, "0")}</span>
      </button>
      <div className="mcard__body">
        <h3 className="mcard__title" onClick={() => onOpen(movie)}>{movie.title}</h3>
        <p className="mcard__meta">{movie.year}{movie.genres ? ` · ${movie.genres}` : ""}</p>
        {(movie.custom_pitch || movie.llm_4pillar) && (
          <p className="mcard__pitch mcard__pitch--clamp">{movie.custom_pitch || movie.llm_4pillar}</p>
        )}
        <div className="mcard__actions">
          <button className="ghostbtn ghostbtn--sm" onClick={() => onSwap(movie)}>다른 거</button>
          <button className="linkbtn" onClick={() => onOpen(movie)}>자세히 →</button>
        </div>
      </div>
    </div>
  );
}
