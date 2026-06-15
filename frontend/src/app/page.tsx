"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatMessage, ChatMessagePayload, ChatOption, Movie } from "@/lib/types";
import { api } from "@/lib/api";
import HomeScreen from "@/components/HomeScreen";
import { Bubble, Typing } from "@/components/ChatBubble";
import QuickRow from "@/components/QuickRow";
import ResultBlock from "@/components/ResultBlock";
import CanvasPane from "@/components/CanvasPane";
import DetailSheet from "@/components/DetailSheet";

let _uid = 0;
const uid = () => "m" + ++_uid;

export default function App() {
  const [view, setView]         = useState<"home" | "chat">("home");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [detailId, setDetailId] = useState<number | null>(null);
  const [detailPitch, setDetailPitch] = useState<string | null>(null);
  const [draft, setDraft]       = useState("");
  const [busy, setBusy]         = useState(false);
  const layout: "grid" | "list" = "list";

  const threadRef   = useRef<HTMLDivElement>(null);
  const timers      = useRef<ReturnType<typeof setTimeout>[]>([]);
  const retryFn     = useRef<(() => void) | null>(null);
  const messagesRef = useRef<ChatMessage[]>([]);
  // Gemini에 넘길 대화 히스토리
  const convoRef    = useRef<{ role: string; content: string }[]>([]);
  // 대화 전반 누적 필터 (한국영화 빼고 등)
  const sessionFiltersRef = useRef<Record<string, Record<string, string>>>({});

  useEffect(() => { messagesRef.current = messages; }, [messages]);
  useEffect(() => () => timers.current.forEach(clearTimeout), []);
  useEffect(() => {
    const el = threadRef.current;
    if (el) el.scrollTop = el.scrollHeight + 400;
  }, [messages]);

  const wait = (ms: number) =>
    new Promise<void>((res) => {
      const id = setTimeout(res, ms);
      timers.current.push(id);
    });

  const push = (m: ChatMessagePayload) =>
    setMessages((prev) => [...prev, { id: uid(), ...m } as ChatMessage]);

  const deactivateQuicks = () =>
    setMessages((prev) =>
      prev.map((m) => (m.kind === "quick" ? { ...m, active: false } : m))
    );

  const aiSay = async (text: string, delay = 700) => {
    const typingId = uid();
    setMessages((prev) => [...prev, { id: typingId, kind: "typing" } as ChatMessage]);
    await wait(delay);
    setMessages((prev) =>
      prev.map((m) =>
        m.id === typingId
          ? ({ id: m.id, kind: "bubble", role: "ai", text } as ChatMessage)
          : m
      )
    );
    await wait(200);
  };

  const openDetail = useCallback((mv: Movie) => {
    setDetailId(mv.id);
    setDetailPitch(mv.custom_pitch ?? null);
  }, []);

  const resetToHome = useCallback(() => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
    setMessages([]);
    convoRef.current = [];
    sessionFiltersRef.current = {};
    setBusy(false);
    setView("home");
  }, []);

  // ── 핵심: Gemini 대화 → 질문 또는 결과 ─────────────────────
  const converse = useCallback(async (userText: string) => {
    if (busy) return;
    setBusy(true);
    deactivateQuicks();
    push({ kind: "bubble", role: "user", text: userText });

    // 히스토리에 사용자 메시지 추가
    const history = [...convoRef.current, { role: "user", content: userText }];
    convoRef.current = history;

    const shownIds = messagesRef.current
      .filter((m): m is ChatMessage & { kind: "result" } => m.kind === "result")
      .flatMap((m) => m.movies.map((mv) => mv.id));

    // 가장 최근 결과 화면의 영화 제목 전체 (refine/detail 컨텍스트)
    const lastResult = [...messagesRef.current]
      .reverse()
      .find((m): m is ChatMessage & { kind: "result" } => m.kind === "result");
    const currentMovieTitles = lastResult
      ? [...lastResult.movies, ...lastResult.pool].map((mv) => mv.title)
      : [];

    try {
      await wait(300);
      const res = await api.chatConverse(history, shownIds, currentMovieTitles, sessionFiltersRef.current);
      if (res.session_filters) sessionFiltersRef.current = res.session_filters;

      if (res.type === "question") {
        convoRef.current = [...history, { role: "assistant", content: res.ai_message }];
        await aiSay(res.ai_message);
        if (res.suggestions.length > 0) {
          push({
            kind: "quick",
            options: res.suggestions.map((s, i) => ({ label: s, index: i })),
            active: true,
          });
        }
      } else if (res.type === "chat") {
        // 잡담·단순 반응 — 재탐색 없이 대화 버블만
        convoRef.current = [...history, { role: "assistant", content: res.ai_message }];
        await aiSay(res.ai_message);
      } else {
        const allMovies = res.results.map((r) => ({ ...r.movie, custom_pitch: r.pitch || undefined }));
        // 추천 영화 제목을 convoRef에 포함 — Gemini가 후속 질문 맥락 파악용
        const topTitles = allMovies.slice(0, 3).map((m) => m.title).join(", ");
        convoRef.current = [...history, { role: "assistant", content: `${res.ai_message} 추천 영화: ${topTitles}` }];
        await aiSay(res.ai_message);
        push({ kind: "result", movies: allMovies.slice(0, 3), pool: allMovies.slice(3) });
        await wait(120);
        push({ kind: "quick", options: [{ label: "처음부터 다시", index: -1 }], active: true });
      }
    } catch (e) {
      console.error("[converse]", e);
      retryFn.current = () => converse(userText);
      await aiSay("잠깐 문제가 생겼어요. 다시 시도해볼까요?");
      push({ kind: "quick", options: [{ label: "다시 시도", index: -4 }, { label: "처음부터 다시", index: -1 }], active: true });
    } finally {
      setBusy(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [busy]);

  // ── 대화 시작 (홈 → 챗) ───────────────────────────────────
  const startFlow = useCallback((query: string, echoText?: string) => {
    setDraft("");
    convoRef.current = [];
    sessionFiltersRef.current = {};
    setView("chat");
    converse(echoText ?? query);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [converse]);

  // ── 결과 후 자유 입력 → 시맨틱 검색 직행 ──────────────────
  const followupSearch = useCallback(async (text: string) => {
    if (busy) return;
    setBusy(true);
    deactivateQuicks();
    push({ kind: "bubble", role: "user", text });

    const shownIds = messagesRef.current
      .filter((m): m is ChatMessage & { kind: "result" } => m.kind === "result")
      .flatMap((m) => m.movies.map((mv) => mv.id));

    try {
      await wait(300);
      const res = await api.chatFollowup(text, shownIds);
      if (res.results.length === 0) {
        await aiSay("딱 맞는 영화를 못 찾겠어요. 조금 다르게 말해주실 수 있어요?");
      } else {
        await aiSay(res.ai_message);
        const allMovies = res.results.map((r) => ({ ...r.movie, custom_pitch: r.pitch || undefined }));
        push({ kind: "result", movies: allMovies.slice(0, 3), pool: allMovies.slice(3) });
        await wait(120);
        push({ kind: "quick", options: [{ label: "처음부터 다시", index: -1 }], active: true });
      }
    } catch (e) {
      console.error("[followupSearch]", e);
      retryFn.current = () => followupSearch(text);
      await aiSay("검색 중 오류가 났어요. 다시 시도해볼까요?");
      push({ kind: "quick", options: [{ label: "다시 시도", index: -4 }, { label: "처음부터 다시", index: -1 }], active: true });
    } finally {
      setBusy(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [busy]);

  // ── 영화 교체 — pool 우선, 소진 시 랜덤 ─────────────────────
  const swapMovie = useCallback((msgId: string, movie: Movie) => {
    setMessages((prev) => {
      const msg = prev.find((m) => m.id === msgId && m.kind === "result");
      if (!msg || msg.kind !== "result") return prev;

      const shownIds = new Set(msg.movies.map((m) => m.id));
      const nextFromPool = msg.pool.find((p) => !shownIds.has(p.id));

      if (nextFromPool) {
        return prev.map((m) => {
          if (m.id !== msgId || m.kind !== "result") return m;
          return {
            ...m,
            movies: m.movies.map((mv) => (mv.id === movie.id ? nextFromPool : mv)),
            pool: m.pool.filter((p) => p.id !== nextFromPool.id),
          };
        });
      }

      // pool 소진 — 랜덤 fallback
      const excludeIds = [...shownIds];
      api.movieRandom(excludeIds).then((next) => {
        setMessages((p) =>
          p.map((m) => {
            if (m.id !== msgId || m.kind !== "result") return m;
            return { ...m, movies: m.movies.map((mv) => (mv.id === movie.id ? next : mv)) };
          })
        );
      }).catch(() => {});
      return prev;
    });
  }, []);

  // ── 자유 입력 전송 ────────────────────────────────────────
  const send = useCallback(() => {
    const text = draft.trim();
    if (!text || busy) return;
    setDraft("");
    if (messagesRef.current.length > 0) {
      converse(text);
    } else {
      startFlow(text);
    }
  }, [draft, busy, startFlow, converse]);

  // ── 퀵 버튼 처리 ─────────────────────────────────────────
  const handleQuick = useCallback((option: ChatOption) => {
    if (option.index === -4) {
      retryFn.current?.();
    } else if (option.index < 0) {
      resetToHome();
    } else {
      // 대화 중 선택지 = 해당 텍스트로 converse 호출
      converse(option.label);
    }
  }, [converse, resetToHome]);

  // ── 데스크톱 캔버스: 가장 최근 결과 ──────────────────────
  let latestMovies: Movie[] | null = null;
  let latestMsgId: string | null = null;
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (m.kind === "result") { latestMovies = m.movies; latestMsgId = m.id; break; }
  }

  return (
    <div className="app bubble-round">
      {/* 탑바 */}
      <header className={"topbar " + (view === "home" ? "topbar--home" : "")}>
        <button className="brandmark" onClick={resetToHome} aria-label="홈으로">
          <span className="brandmark__logo">ㅇㅎㅊㅊ</span>
        </button>
        {view !== "home" && (
          <span className="topbar__slogan">영화는 언제 만나는지도 중요하다</span>
        )}
      </header>

      {/* 홈 */}
      {view === "home" && (
        <HomeScreen
          draft={draft}
          setDraft={setDraft}
          onSend={send}
          onHint={(text: string) => startFlow(text, text)}
        />
      )}

      {/* 챗 */}
      {view === "chat" && (
        <div className="stage">
          <section className="convo">
            <main className="thread" ref={threadRef}>
              <div className="thread__inner">
                {messages.map((m) => {
                  if (m.kind === "typing")
                    return <Typing key={m.id} />;
                  if (m.kind === "bubble")
                    return <Bubble key={m.id} role={m.role}>{m.text}</Bubble>;
                  if (m.kind === "quick")
                    return (
                      <div key={m.id} className={"quickwrap" + (m.active ? "" : " quickwrap--done")}>
                        <QuickRow
                          options={m.options}
                          disabled={!m.active}
                          onPick={(o) => m.active && handleQuick(o)}
                        />
                      </div>
                    );
                  if (m.kind === "result")
                    return (
                      <ResultBlock
                        key={m.id}
                        movies={m.movies}
                        layout={layout}
                        onOpen={openDetail}
                        onSwap={(mv) => swapMovie(m.id, mv)}
                      />
                    );
                  return null;
                })}
              </div>
            </main>

            <div className="composerbar">
              <form className="composer" onSubmit={(e) => { e.preventDefault(); send(); }}>
                <input
                  className="composer__input"
                  value={draft}
                  disabled={busy}
                  placeholder={busy ? "생각하는 중…" : "원하는 걸 더 말해도 돼요 (예: 한국 영화 빼고)"}
                  onChange={(e) => setDraft(e.target.value)}
                />
                <button className="composer__send" type="submit" disabled={busy} aria-label="보내기">↑</button>
              </form>
            </div>
          </section>

          <CanvasPane
            movies={latestMovies}
            layout={layout}
            busy={busy}
            onOpen={openDetail}
            onSwap={(mv) => { if (latestMsgId) swapMovie(latestMsgId, mv); }}
          />
        </div>
      )}

      <DetailSheet movieId={detailId} customPitch={detailPitch ?? undefined} onClose={() => { setDetailId(null); setDetailPitch(null); }} />
    </div>
  );
}
