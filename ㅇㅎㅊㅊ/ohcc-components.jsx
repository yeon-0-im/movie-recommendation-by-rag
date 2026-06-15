// ohcc-components.jsx — 공통 UI 컴포넌트

// ── 포스터 플레이스홀더 (듀오톤 + 타이틀) ─────────────────────
function Poster({ movie, className = "", style = {} }) {
  const tone = POSTER_TONES[movie.tone] || POSTER_TONES.slate;
  return (
    <div className={"poster " + className} style={{ background: tone.bg, color: tone.ink, ...style }}>
      <div className="poster__grain" />
      <div className="poster__top">
        <span className="poster__year">{movie.year}</span>
        <span className="poster__mono">KEY ART</span>
      </div>
      <div className="poster__title">
        <span className="poster__ko">{movie.title}</span>
        <span className="poster__en">{movie.titleEn}</span>
      </div>
    </div>
  );
}

// ── 4-Pillar 태그 칩 (내부 분류용 — UI 노출 X) ──────────────
const PILLAR_LABEL = { context: "상황", emotion: "무드", sensory: "감각", load: "몰입도" };
function PillarTags({ tags, compact = false }) {
  const order = ["context", "emotion", "sensory", "load"];
  return (
    <div className={"pillars" + (compact ? " pillars--compact" : "")}>
      {order.map((k) => (
        <span className="pillar" key={k}>
          <span className="pillar__k">{PILLAR_LABEL[k]}</span>
          <span className="pillar__v">{tags[k]}</span>
        </span>
      ))}
    </div>
  );
}

// ── 리뷰 원문 발췌 (추천 근거) ───────────────────────────────
function ReviewQuotes({ movieId, count = 1, showSrc = false, labeled = false }) {
  const reviews = (REVIEWS[movieId] || []).slice(0, count);
  if (!reviews.length) return null;
  return (
    <div className="reviews">
      {labeled && <span className="reviews__label">이 리뷰에서 골랐어요</span>}
      {reviews.map((r, i) => (
        <blockquote className="review" key={i}>
          <p className="review__q">{r.q}</p>
          {showSrc && <cite className="review__src">{r.src}</cite>}
        </blockquote>
      ))}
    </div>
  );
}

// ── 타이핑 인디케이터 ────────────────────────────────────────
function Typing() {
  return (
    <div className="msg msg--ai">
      <div className="avatar" aria-hidden="true">ㅇ</div>
      <div className="bubble bubble--ai typing">
        <span className="dot" /><span className="dot" /><span className="dot" />
      </div>
    </div>
  );
}

// ── 채팅 말풍선 ──────────────────────────────────────────────
function Bubble({ role, children }) {
  const isAI = role === "ai";
  return (
    <div className={"msg " + (isAI ? "msg--ai" : "msg--user")}>
      {isAI && <div className="avatar" aria-hidden="true">ㅇ</div>}
      <div className={"bubble " + (isAI ? "bubble--ai" : "bubble--user")}>{children}</div>
    </div>
  );
}

// ── 퀵 버튼 묶음 ─────────────────────────────────────────────
function QuickRow({ options, onPick, disabled }) {
  return (
    <div className="quickrow">
      {options.map((o, i) => (
        <button
          key={i}
          className="quickbtn"
          disabled={disabled}
          onClick={() => onPick(o, i)}
        >
          {o.label || o}
        </button>
      ))}
    </div>
  );
}

// ── 영화 카드 (리스트형) ─────────────────────────────────────
function MovieCardList({ movie, index, onOpen, onSeen, onSwap }) {
  return (
    <div className="mcard mcard--list">
      <button className="mcard__hit" onClick={() => onOpen(movie)} aria-label={movie.title + " 상세"}>
        <Poster movie={movie} className="poster--list" />
      </button>
      <div className="mcard__body">
        <div className="mcard__head">
          <span className="mcard__rank">{String(index + 1).padStart(2, "0")}</span>
          <div className="mcard__titles" onClick={() => onOpen(movie)}>
            <h3 className="mcard__title">{movie.title}</h3>
            <p className="mcard__meta">{movie.titleEn} · {movie.year} · {movie.genre}</p>
          </div>
        </div>
        <p className="mcard__pitch">{movie.pitch}</p>
        <ReviewQuotes movieId={movie.id} count={1} showSrc labeled />
        <div className="mcard__actions">
          <button className="ghostbtn" onClick={() => onSeen(movie)}>이거 이미 봤어</button>
          <button className="ghostbtn" onClick={() => onSwap(movie)}>다른 거 보여줘</button>
          <button className="linkbtn" onClick={() => onOpen(movie)}>자세히 →</button>
        </div>
      </div>
    </div>
  );
}

// ── 영화 카드 (그리드형) ─────────────────────────────────────
function MovieCardGrid({ movie, index, onOpen, onSeen, onSwap }) {
  return (
    <div className="mcard mcard--grid">
      <button className="mcard__hit" onClick={() => onOpen(movie)} aria-label={movie.title + " 상세"}>
        <Poster movie={movie} className="poster--grid" />
        <span className="mcard__rank mcard__rank--float">{String(index + 1).padStart(2, "0")}</span>
      </button>
      <div className="mcard__body">
        <h3 className="mcard__title" onClick={() => onOpen(movie)}>{movie.title}</h3>
        <p className="mcard__meta">{movie.year} · {movie.genre}</p>
        <p className="mcard__pitch mcard__pitch--clamp">{movie.pitch}</p>
        <ReviewQuotes movieId={movie.id} count={1} showSrc />
        <div className="mcard__actions">
          <button className="ghostbtn ghostbtn--sm" onClick={() => onSeen(movie)}>봤어</button>
          <button className="ghostbtn ghostbtn--sm" onClick={() => onSwap(movie)}>다른 거</button>
          <button className="linkbtn" onClick={() => onOpen(movie)}>자세히 →</button>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { Poster, PillarTags, ReviewQuotes, Typing, Bubble, QuickRow, MovieCardList, MovieCardGrid });
