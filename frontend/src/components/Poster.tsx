import Image from "next/image";
import type { Movie, Tone } from "@/lib/types";

const TONES: Record<Tone, { bg: string; ink: string }> = {
  amber:  { bg: "oklch(0.42 0.09 55)",  ink: "oklch(0.93 0.05 70)" },
  rose:   { bg: "oklch(0.42 0.09 18)",  ink: "oklch(0.93 0.05 30)" },
  plum:   { bg: "oklch(0.42 0.09 330)", ink: "oklch(0.93 0.05 340)" },
  indigo: { bg: "oklch(0.42 0.09 270)", ink: "oklch(0.93 0.05 280)" },
  teal:   { bg: "oklch(0.42 0.09 200)", ink: "oklch(0.93 0.05 200)" },
  forest: { bg: "oklch(0.42 0.09 150)", ink: "oklch(0.93 0.05 150)" },
  slate:  { bg: "oklch(0.40 0.03 250)", ink: "oklch(0.92 0.02 250)" },
};

const TMDB_IMG = "https://image.tmdb.org/t/p/w300";

interface Props {
  movie: Pick<Movie, "title" | "title_en" | "year" | "tone" | "poster_path">;
  className?: string;
}

export default function Poster({ movie, className = "" }: Props) {
  const tone = TONES[movie.tone as Tone] ?? TONES.slate;

  if (movie.poster_path) {
    return (
      <div className={"poster " + className} style={{ position: "relative", padding: 0 }}>
        <Image
          src={`${TMDB_IMG}${movie.poster_path}`}
          alt={movie.title}
          fill
          style={{ objectFit: "cover" }}
          sizes="(max-width: 600px) 120px, 200px"
          unoptimized
        />
      </div>
    );
  }

  // 포스터 없을 때 듀오톤 플레이스홀더
  return (
    <div
      className={"poster " + className}
      style={{ background: tone.bg, color: tone.ink }}
    >
      <div className="poster__grain" />
      <div className="poster__top">
        <span className="poster__year">{movie.year}</span>
        <span className="poster__mono">KEY ART</span>
      </div>
      <div className="poster__title">
        <span className="poster__ko">{movie.title}</span>
        <span className="poster__en">{movie.title_en}</span>
      </div>
    </div>
  );
}
