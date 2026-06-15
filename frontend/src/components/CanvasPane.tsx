import type { Movie } from "@/lib/types";
import { MovieCardGrid, MovieCardList } from "./MovieCard";

interface Props {
  movies: Movie[] | null;
  layout: "grid" | "list";
  busy: boolean;
  onOpen: (movie: Movie) => void;
  onSwap: (movie: Movie) => void;
}

export default function CanvasPane({ movies, layout, busy, onOpen, onSwap }: Props) {
  if (!movies) {
    return (
      <aside className="canvas" aria-label="추천 결과">
        <div className="canvas__empty">
          <div className="canvas__mark">ㅇㅎㅊㅊ</div>
          <p className="canvas__emptytitle">
            {busy ? "지금 당신에게 어울리는 영화 찾는 중…" : "대화 몇 번이면 충분해요"}
          </p>
          <p className="canvas__emptysub">
            감정·상황·감각·몰입도까지 읽어
            <br />
            지금 가장 잘 맞는 영화를 여기에 추천해드릴게요.
          </p>
        </div>
      </aside>
    );
  }

  return (
    <aside className="canvas" aria-label="추천 결과">
      <div className="canvas__in">
        <div className="canvas__head">
          <span className="canvas__kicker">오늘의 추천</span>
          <h2 className="canvas__title">지금 당신 타이밍에 딱 맞춘 {movies.length}편</h2>
          <p className="canvas__sub">
            카드의 <b>&#39;다른 영화 추천&#39;</b>를 누르면 다른 영화를 추천해드려요.
          </p>
        </div>
        <div className={layout}>
          {movies.map((mv, i) =>
            layout === "list" ? (
              <MovieCardList key={mv.id} movie={mv} index={i} onOpen={onOpen} onSwap={onSwap} />
            ) : (
              <MovieCardGrid key={mv.id} movie={mv} index={i} onOpen={onOpen} onSwap={onSwap} />
            )
          )}
        </div>
      </div>
    </aside>
  );
}
