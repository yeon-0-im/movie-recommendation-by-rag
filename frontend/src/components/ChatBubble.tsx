export function Typing() {
  return (
    <div className="msg msg--ai">
      <div className="avatar" aria-hidden="true">ㅇ</div>
      <div className="bubble bubble--ai typing">
        <span className="dot" />
        <span className="dot" />
        <span className="dot" />
      </div>
    </div>
  );
}

interface BubbleProps {
  role: "ai" | "user";
  children: React.ReactNode;
}

export function Bubble({ role, children }: BubbleProps) {
  const isAI = role === "ai";
  return (
    <div className={"msg " + (isAI ? "msg--ai" : "msg--user")}>
      {isAI && <div className="avatar" aria-hidden="true">ㅇ</div>}
      <div className={"bubble " + (isAI ? "bubble--ai" : "bubble--user")}>{children}</div>
    </div>
  );
}
