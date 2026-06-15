// ohcc-app.jsx — 메인 앱: 스플래시 → 챗 핑퐁 → 결과 카드 → 상세

const { useState, useRef, useEffect, useCallback } = React;

let _uid = 0;
const uid = () => "m" + (++_uid);

// 자유 입력 → 플로우 키 매칭
function matchFlow(text) {
  const t = text || "";
  if (/이별|헤어|그리|차였|짝사랑|보고\s*싶/.test(t)) return "breakup";
  if (/동기|자극|늘어|의욕|채찍|성취|벅차/.test(t)) return "boost";
  if (/공부|영어|프랑스|언어|가볍|힐링|편하/.test(t)) return "light";
  return "stress";
}

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [view, setView] = useState("home");        // home | chat | detail
  const [messages, setMessages] = useState([]);
  const [flowKey, setFlowKey] = useState(null);
  const [detail, setDetail] = useState(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const threadRef = useRef(null);
  const timers = useRef([]);

  // 정리
  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  // 자동 스크롤
  useEffect(() => {
    const el = threadRef.current;
    if (el) el.scrollTop = el.scrollHeight + 400;
  }, [messages, view]);

  const wait = (ms) => new Promise((res) => { const id = setTimeout(res, ms); timers.current.push(id); });

  const push = (m) => setMessages((prev) => [...prev, { id: uid(), ...m }]);
  const deactivateQuicks = () =>
    setMessages((prev) => prev.map((m) => (m.quick ? { ...m, active: false } : m)));

  // AI 발화 (타이핑 → 텍스트)
  const aiSay = async (chunks, delay = 700) => {
    const arr = Array.isArray(chunks) ? chunks : [chunks];
    for (const text of arr) {
      const typingId = uid();
      setMessages((prev) => [...prev, { id: typingId, typing: true }]);
      await wait(delay);
      setMessages((prev) => prev.map((m) => (m.id === typingId ? { id: m.id, role: "ai", text } : m)));
      await wait(220);
    }
  };

  // ── Step1: 진입 선택 ───────────────────────────────────────
  const startFlow = async (key, customText) => {
    if (busy) return;
    setBusy(true);
    const flow = FLOWS[key];
    setFlowKey(key);
    deactivateQuicks();
    setView("chat");
    push({ role: "user", text: customText || flow.userEcho });
    await wait(260);
    await aiSay(flow.aiQuestion);
    push({ quick: { kind: "tuning", options: flow.options }, active: true });
    setBusy(false);
  };

  // ── Step2: 튜닝 선택 → 결과 ────────────────────────────────
  const pickTuning = async (option, key) => {
    if (busy) return;
    setBusy(true);
    deactivateQuicks();
    push({ role: "user", text: option.label });
    await wait(240);
    await aiSay("그럴 땐 이 영화 어떠세요? 지금 당신 타이밍에 딱 맞춰 골라봤어요.");
    await wait(120);
    push({ result: { movieIds: option.movies.slice(0, 3) } });
    await wait(120);
    push({ quick: { kind: "restart", options: [{ label: "처음부터 다시" }, { label: "다른 무드로" }] }, active: true });
    setBusy(false);
  };

  // 결과 카드 내 영화 교체
  const swapMovie = (resultMsgId, movieId) => {
    setMessages((prev) =>
      prev.map((m) => {
        if (m.id !== resultMsgId || !m.result) return m;
        const shown = new Set(m.result.movieIds);
        const next = ALT_POOL.find((x) => !shown.has(x)) || movieId;
        return { ...m, result: { movieIds: m.result.movieIds.map((x) => (x === movieId ? next : x)) } };
      })
    );
  };

  // 자유 입력 전송
  const send = async () => {
    const text = draft.trim();
    if (!text || busy) return;
    setDraft("");
    if (view === "home" || !flowKey) {
      await startFlow(matchFlow(text), text);
      return;
    }
    // 챗 진행 중 자유입력 → 현재 플로우에서 키워드 매칭 후 결과
    setBusy(true);
    deactivateQuicks();
    push({ role: "user", text });
    const flow = FLOWS[flowKey];
    const opt =
      flow.options.find((o) => text.includes(o.label.slice(0, 2))) || flow.options[0];
    await wait(240);
    await aiSay("오케이, 바로 찾아봤어요.");
    push({ result: { movieIds: opt.movies.slice(0, 3) } });
    push({ quick: { kind: "restart", options: [{ label: "처음부터 다시" }, { label: "다른 무드로" }] }, active: true });
    setBusy(false);
  };

  const restart = (mode) => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
    setMessages([]);
    setFlowKey(null);
    setBusy(false);
    setView("home");
  };

  const openDetail = (movie) => { setDetail(movie); setView("detail"); };
  const closeDetail = () => { setView(flowKey ? "chat" : "home"); setTimeout(() => setDetail(null), 220); };

  const handleQuick = (block, option, idx) => {
    if (block.kind === "entry") startFlow(option.key);
    else if (block.kind === "tuning") pickTuning(option, flowKey);
    else if (block.kind === "restart") restart(option.label);
  };

  const ACCENT_DEEP = {
    "#FF5722": "#E8431A", "#FF6B00": "#E05600",
    "#FF8A00": "#E07400", "#F94E2E": "#DD3A1C",
  };
  const accentVars = {
    "--accent": t.accent,
    "--accent-deep": ACCENT_DEEP[t.accent] || t.accentDeep || t.accent,
  };

  // 데스크톱 캔버스용: 가장 최근 결과 메시지
  let latestResult = null;
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].result) { latestResult = messages[i]; break; }
  }

  return (
    <div className={"app bubble-" + t.bubbleStyle} style={accentVars} data-screen-label="ㅇㅎㅊㅊ">
      {/* 헤더 */}
      <header className={"topbar " + (view === "home" ? "topbar--home" : "")}>
        <button className="brandmark" onClick={() => restart()} aria-label="홈으로">
          <span className="brandmark__logo">ㅇㅎㅊㅊ</span>
        </button>
        {view !== "home" && <span className="topbar__slogan">영화는 언제 만나는지도 중요하다</span>}
      </header>

      {/* 홈(스플래시·웰컴) */}
      {view === "home" && (
        <HomeScreen onEntry={(key) => startFlow(key)} draft={draft} setDraft={setDraft} send={send} />
      )}

      {/* 챗 — 데스크톱 2-pane / 모바일 단일 컬럼 */}
      {view !== "home" && (
        <div className="stage">
          <section className="convo">
            <main className="thread" ref={threadRef}>
              <div className="thread__inner">
                {messages.map((m) => {
                  if (m.typing) return <Typing key={m.id} />;
                  if (m.role) return <Bubble key={m.id} role={m.role}>{m.text}</Bubble>;
                  if (m.quick)
                    return (
                      <div key={m.id} className={"quickwrap" + (m.active ? "" : " quickwrap--done")}>
                        <QuickRow options={m.quick.options} disabled={!m.active}
                          onPick={(o, i) => m.active && handleQuick(m.quick, o, i)} />
                      </div>
                    );
                  if (m.result)
                    return (
                      <ResultBlock key={m.id} msgId={m.id} movieIds={m.result.movieIds}
                        layout={t.cardLayout} onOpen={openDetail}
                        onSeen={(mv) => swapMovie(m.id, mv.id)} onSwap={(mv) => swapMovie(m.id, mv.id)} />
                    );
                  return null;
                })}
              </div>
            </main>
            <ComposerBar draft={draft} setDraft={setDraft} send={send} busy={busy} />
          </section>

          {/* 데스크톱 전용 추천 캔버스 */}
          <aside className="canvas" aria-label="추천 결과">
            {latestResult ? (
              <CanvasResults result={latestResult} layout={t.cardLayout} onOpen={openDetail}
                onSwap={(mv) => swapMovie(latestResult.id, mv.id)} />
            ) : (
              <CanvasEmpty busy={busy} />
            )}
          </aside>
        </div>
      )}

      {/* 상세 */}
      {detail && (
        <DetailScreen movie={detail} open={view === "detail"} onClose={closeDetail} />
      )}

      <TweakControls t={t} setTweak={setTweak} />
    </div>
  );
}

// ── 홈 화면 ────────────────────────────────────────────────
function HomeScreen({ onEntry, draft, setDraft, send }) {
  const entries = [
    { key: "stress", label: "스트레스 해소", desc: "머리 비우고 싶을 때" },
    { key: "breakup", label: "이별 치유", desc: "마음 추스를 한 편" },
    { key: "boost", label: "자극과 동기부여", desc: "정신 번쩍 들게" },
    { key: "light", label: "언어공부 · 가벼운 힐링", desc: "부담 없이 가볍게" },
  ];
  return (
    <main className="home" data-screen-label="스플래시·웰컴">
      <div className="home__hero">
        <div className="home__logo">ㅇㅎㅊㅊ</div>
        <p className="home__slogan">영화는 언제 만나는지도 중요하다.</p>
      </div>
      <div className="home__panel">
        <p className="home__greet"><b>ㅇㅎㅊㅊ.</b> 오늘 당신에게 딱 맞는 영화.</p>
        <p className="home__sub">지금 기분이나 상황을 그냥 편하게 적어보세요. 1분이면 충분해요.</p>
        <ComposerInline draft={draft} setDraft={setDraft} send={send} big
          placeholder="예) 대학생 때로 돌아가고 싶어. 지금 볼만한 청춘 영화 추천해줘 " />
        <div className="home__hint">
          <span className="home__hintlabel">이건 어떠세요?</span>
          <div className="home__chips">
            {entries.map((e) => (
              <button key={e.key} className="hintchip" onClick={() => onEntry(e.key)}>
                {e.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}

// ── 결과 블록 ──────────────────────────────────────────────
function ResultBlock({ msgId, movieIds, layout, onOpen, onSeen, onSwap }) {
  const movies = movieIds.map((id) => MOVIES[id]).filter(Boolean);
  return (
    <div className="resultblock">
      {layout === "grid" ? (
        <div className="grid">
          {movies.map((mv, i) => (
            <MovieCardGrid key={mv.id} movie={mv} index={i} onOpen={onOpen} onSeen={onSeen} onSwap={onSwap} />
          ))}
        </div>
      ) : (
        <div className="list">
          {movies.map((mv, i) => (
            <MovieCardList key={mv.id} movie={mv} index={i} onOpen={onOpen} onSeen={onSeen} onSwap={onSwap} />
          ))}
        </div>
      )}
      <p className="result__foot">마음에 드는 게 없으면 카드의 <b>‘다른 거’</b>를 눌러요. 다른 영화를 추천해드릴게요.</p>
    </div>
  );
}

// ── 데스크톱 추천 캔버스 ───────────────────────────────────
function CanvasResults({ result, layout, onOpen, onSwap }) {
  const movies = result.result.movieIds.map((id) => MOVIES[id]).filter(Boolean);
  return (
    <div className="canvas__in" data-screen-label="추천 캔버스">
      <div className="canvas__head">
        <span className="canvas__kicker">오늘의 추천</span>
        <h2 className="canvas__title">지금 당신 타이밍에 딱 맞춘 {movies.length}편</h2>
        <p className="canvas__sub">카드의 <b>‘다른 거’</b>를 누르면 변명 없이 바로 바꿔드려요.</p>
      </div>
      <div className={layout === "list" ? "list" : "grid"}>
        {movies.map((mv, i) =>
          layout === "list" ? (
            <MovieCardList key={mv.id} movie={mv} index={i} onOpen={onOpen}
              onSeen={() => onSwap(mv)} onSwap={() => onSwap(mv)} />
          ) : (
            <MovieCardGrid key={mv.id} movie={mv} index={i} onOpen={onOpen}
              onSeen={() => onSwap(mv)} onSwap={() => onSwap(mv)} />
          )
        )}
      </div>
    </div>
  );
}

function CanvasEmpty({ busy }) {
  return (
    <div className="canvas__empty">
      <div className="canvas__mark">ㅇㅎㅊㅊ</div>
      <p className="canvas__emptytitle">{busy ? "당신의 타이밍을 맞춰보는 중…" : "왼쪽 대화 몇 번이면 충분해요"}</p>
      <p className="canvas__emptysub">감정·상황·감각·몰입도까지 읽어<br />지금 가장 잘 맞는 영화를 여기에 펼쳐드릴게요.</p>
    </div>
  );
}

// ── 상세 화면 ──────────────────────────────────────────────
function DetailScreen({ movie, open, onClose }) {
  return (
    <div className={"detail " + (open ? "detail--open" : "")} data-screen-label={"상세-" + movie.title}>
      <div className="detail__scrim" onClick={onClose} />
      <div className="detail__sheet">
        <button className="detail__close" onClick={onClose} aria-label="닫기">✕</button>
        <div className="detail__hero">
          <Poster movie={movie} className="poster--detail" />
          <div className="detail__head">
            <span className="detail__rating">{movie.rating}</span>
            <h2 className="detail__title">{movie.title}</h2>
            <p className="detail__meta">{movie.titleEn} · {movie.year}</p>
            <p className="detail__meta2">{movie.genre} · {movie.runtime}</p>
            <p className="detail__cast">{movie.cast.join(", ")}</p>
          </div>
        </div>
        <div className="detail__pitchcard">
          <span className="detail__pitchtag">왜 지금, 이 영화냐면</span>
          <p className="detail__pitch">{movie.pitch}</p>
        </div>
        <div className="detail__reviews">
          <span className="detail__reviewslabel">이 리뷰들에서 골랐어요</span>
          <ReviewQuotes movieId={movie.id} count={2} showSrc />
        </div>
        <p className="detail__synopsis">{movie.synopsis}</p>
        <div className="detail__cta">
          <button className="bigbtn">이 영화 보러 가기 →</button>
          <button className="bigbtn bigbtn--ghost" onClick={onClose}>다른 추천 볼게요</button>
        </div>
      </div>
    </div>
  );
}

// ── 입력 컴포넌트 ──────────────────────────────────────────
function ComposerInline({ draft, setDraft, send, big, placeholder }) {
  return (
    <form className={"composer composer--inline" + (big ? " composer--big" : "")} onSubmit={(e) => { e.preventDefault(); send(); }}>
      <input className="composer__input" value={draft} placeholder={placeholder || "예) 오늘 회사에서 깨짐. 뇌 비울 영화 줘"}
        onChange={(e) => setDraft(e.target.value)} autoFocus />
      <button className="composer__send" type="submit" aria-label="보내기">↑</button>
    </form>
  );
}

function ComposerBar({ draft, setDraft, send, busy }) {
  return (
    <div className="composerbar">
      <form className="composer" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <input className="composer__input" value={draft} disabled={busy}
          placeholder={busy ? "고르는 중…" : "원하는 걸 더 말해도 돼요 (예: 한국 영화 빼고)"}
          onChange={(e) => setDraft(e.target.value)} />
        <button className="composer__send" type="submit" disabled={busy} aria-label="보내기">↑</button>
      </form>
    </div>
  );
}

// ── Tweaks 패널 ────────────────────────────────────────────
function TweakControls({ t, setTweak }) {
  return (
    <TweaksPanel>
      <TweakSection label="결과 카드" />
      <TweakRadio label="레이아웃" value={t.cardLayout} options={["list", "grid"]}
        onChange={(v) => setTweak("cardLayout", v)} />
      <TweakSection label="대화 UI" />
      <TweakRadio label="말풍선" value={t.bubbleStyle} options={["round", "edge", "line"]}
        onChange={(v) => setTweak("bubbleStyle", v)} />
      <TweakSection label="브랜드" />
      <TweakColor label="오렌지 포인트" value={t.accent}
        options={["#FF5722", "#FF6B00", "#FF8A00", "#F94E2E"]}
        onChange={(v) => setTweak("accent", v)} />
    </TweaksPanel>
  );
}

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "cardLayout": "grid",
  "bubbleStyle": "round",
  "accent": "#FF6B00",
  "accentDeep": "#E05600"
}/*EDITMODE-END*/;

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
