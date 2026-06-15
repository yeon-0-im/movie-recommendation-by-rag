import type { Movie } from "@/lib/types";
import { MovieCardGrid, MovieCardList } from "./MovieCard";

interface Props {
  movies: Movie[];
  layout: "grid" | "list";
  onOpen: (movie: Movie) => void;
  onSwap: (movie: Movie) => void;
}

export default function ResultBlock({ movies, layout, onOpen, onSwap }: Props) {
  return (
    <div className="resultblock">
      <div className={layout}>
        {movies.map((mv, i) =>
          layout === "grid" ? (
            <MovieCardGrid key={mv.id} movie={mv} index={i} onOpen={onOpen} onSwap={onSwap} />
          ) : (
            <MovieCardList key={mv.id} movie={mv} index={i} onOpen={onOpen} onSwap={onSwap} />
          )
        )}
      </div>
      <p className="result__foot">
        마음에 드는 게 없으면 카드의 <b>&#39;다른 거&#39;</b>를 눌러요. 변명 없이 바로 바꿔드려요.
      </p>
    </div>
  );
}
