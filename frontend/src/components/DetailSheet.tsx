"use client";

import { useEffect, useState } from "react";
import type { Movie } from "@/lib/types";
import Poster from "./Poster";
import { api } from "@/lib/api";

interface Props {
  movieId: number | null;
  customPitch?: string;
  onClose: () => void;
}

interface InfoRowProps {
  label: string;
  value?: string | number | null;
}

function InfoRow({ label, value }: InfoRowProps) {
  if (!value) return null;
  return (
    <div className="detail__row">
      <span className="detail__row-label">{label}</span>
      <span className="detail__row-value">{value}</span>
    </div>
  );
}

export default function DetailSheet({ movieId, customPitch, onClose }: Props) {
  const [movie, setMovie] = useState<Movie | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (movieId == null) {
      setOpen(false);
      const t = setTimeout(() => setMovie(null), 320);
      return () => clearTimeout(t);
    }
    api.movieDetail(movieId).then((m) => {
      setMovie(m);
      setTimeout(() => setOpen(true), 20);
    });
  }, [movieId]);

  const handleClose = () => {
    setOpen(false);
    setTimeout(onClose, 320);
  };

  if (!movie && !open) return null;

  const hasInfo = movie && (
    movie.director || movie.cast || movie.genres ||
    movie.runtime || movie.language || movie.country || movie.ott
  );

  return (
    <div className={"detail " + (open ? "detail--open" : "")}>
      <div className="detail__scrim" onClick={handleClose} />
      <div className="detail__sheet">
        <button className="detail__close" onClick={handleClose} aria-label="닫기">✕</button>

        {movie && (
          <>
            {/* 헤더: 포스터 + 제목/연도 */}
            <div className="detail__hero">
              <Poster movie={movie} className="poster--detail" />
              <div className="detail__head">
                <h2 className="detail__title">{movie.title}</h2>
                {movie.title_en && (
                  <p className="detail__meta">{movie.title_en}</p>
                )}
                {movie.year && (
                  <p className="detail__meta2">{movie.year}년 개봉</p>
                )}
              </div>
            </div>

            {/* 상세 정보 그리드 */}
            {hasInfo && (
              <div className="detail__info">
                <InfoRow label="감독" value={movie.director} />
                <InfoRow label="출연" value={movie.cast} />
                <InfoRow label="장르" value={movie.genres} />
                <InfoRow label="런타임" value={movie.runtime} />
                <InfoRow label="언어" value={movie.language} />
                <InfoRow label="국가" value={movie.country} />
                <InfoRow label="OTT" value={movie.ott} />
              </div>
            )}

            {/* 추천 이유 */}
            {(customPitch || movie.llm_4pillar) && (
              <div className="detail__pitchcard">
                <span className="detail__pitchtag">왜 지금, 이 영화냐면</span>
                <p className="detail__pitch">{customPitch || movie.llm_4pillar}</p>
              </div>
            )}

            {/* 줄거리 */}
            {movie.overview && (
              <p className="detail__synopsis">{movie.overview}</p>
            )}

            <div className="detail__cta">
              <button className="bigbtn bigbtn--ghost" onClick={handleClose}>
                다른 추천 볼게요
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
