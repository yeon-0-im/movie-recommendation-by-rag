import type { ChatConverseResponse, ChatPickResponse, Movie, SearchResult } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} ${res.status}`);
  return res.json();
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${path} ${res.status}`);
  return res.json();
}

export const api = {
  chatConverse: (
    messages: { role: string; content: string }[],
    excludeIds: number[] = [],
    currentMovieTitles: string[] = [],
    sessionFilters: Record<string, Record<string, string>> = {},
  ) =>
    post<ChatConverseResponse>("/chat/converse/", {
      messages,
      exclude_ids: excludeIds,
      current_movie_titles: currentMovieTitles,
      session_filters: sessionFilters,
    }),

  chatFollowup: (query: string, excludeIds: number[] = []) =>
    post<ChatPickResponse>("/chat/followup/", { query, exclude_ids: excludeIds }),

  movieDetail: (id: number) =>
    get<Movie>(`/movies/${id}/`),

  movieRandom: (excludeIds: number[]) =>
    get<Movie>(`/movies/random/?exclude=${excludeIds.join(",")}`),

  search: (query: string) =>
    post<{ query: string; filters: Record<string, unknown>; semantic_query: string; results: SearchResult[] }>(
      "/search/",
      { query }
    ),
};
