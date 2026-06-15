const HINTS: { label: string; text: string }[] = [
  { label: "스트레스 해소",  text: "뇌 비우고 스트레스 풀 만한 영화 추천해줘" },
  { label: "언어 공부",     text: "영어 공부할 때 볼만한 영화 추천해줘" },
  { label: "동기부여",      text: "요즘 너무 늘어졌어. 정신 번쩍 들 영화 추천해줘" },
  { label: "가볍게 힐링",   text: "부담 없이 보면서 힐링할 만한 영화 있어?" },
  { label: "색다른 영화",   text: "뻔한 영화는 싫어. 퇴근하고 볼만한 이색적인 영화 추천해줘" },
  { label: "고전 명작",      text: "1990년대 이전 고전 명작 추천해줘" },
  { label: "부모님과 볼만한 영화",      text: "주말에 부모님과 함께 볼만한 영화 추천해줘" },
];

interface Props {
  draft: string;
  setDraft: (v: string) => void;
  onSend: () => void;
  onHint: (text: string) => void;
}

export default function HomeScreen({ draft, setDraft, onSend, onHint }: Props) {
  return (
    <main className="home">
      <div className="home__hero">
        <div className="home__logo">ㅇㅎㅊㅊ</div>
        <p className="home__slogan">영화는 언제 만나는지도 중요하다.</p>
      </div>
      <div className="home__panel">
        <p className="home__greet">
          <b>ㅇㅎㅊㅊ.</b> 오늘 당신에게 딱 맞는 영화.
        </p>
        <p className="home__sub">지금 기분이나 상황을 그냥 편하게 적어보세요. 1분이면 충분해요.</p>
        <form
          className="composer composer--inline composer--big"
          onSubmit={(e) => { e.preventDefault(); onSend(); }}
        >
          <input
            className="composer__input"
            value={draft}
            placeholder="예) 대학생 때로 돌아가고 싶어. 지금 볼만한 청춘 영화 추천해줘 "
            onChange={(e) => setDraft(e.target.value)}
            autoFocus
          />
          <button className="composer__send" type="submit" aria-label="보내기">↑</button>
        </form>
        <div className="home__hint">
          <span className="home__hintlabel">이건 어떠세요?</span>
          <div className="home__chips">
            {HINTS.map((h) => (
              <button key={h.label} type="button" className="hintchip" onClick={() => onHint(h.text)}>
                {h.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}
