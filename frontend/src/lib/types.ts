export type Tone = "amber" | "rose" | "plum" | "indigo" | "teal" | "forest" | "slate";

export interface Movie {
  id: number;
  title: string;
  title_en: string;
  year: number | null;
  genres: string;
  director: string;
  cast: string;
  runtime: string;
  language: string;
  country: string;
  ott: string;
  tone: Tone;
  llm_4pillar: string;
  poster_path: string;
  // detail only
  tmdb_id?: number | null;
  overview?: string;
  combined_reviews?: string;
  // 실시간 생성 맥락 pitch (클라이언트 전용)
  custom_pitch?: string;
}

export interface SearchResult {
  movie: Movie;
  similarity: number | null;
  pitch?: string;
}

export interface ChatOption {
  label: string;
  index: number;
}

export interface ChatConverseResponse {
  type: "question" | "result" | "chat";
  ai_message: string;
  suggestions: string[];
  results: SearchResult[];
  session_filters?: Record<string, Record<string, string>>;
}

export interface ChatPickResponse {
  ai_message: string;
  results: SearchResult[];
}

// ── chat UI message types ──────────────────────────────────

export type ChatMessagePayload =
  | { kind: "typing" }
  | { kind: "bubble"; role: "ai" | "user"; text: string }
  | { kind: "quick"; options: ChatOption[]; active: boolean }
  | { kind: "result"; movies: Movie[]; pool: Movie[] };

export type ChatMessage = ChatMessagePayload & { id: string };
