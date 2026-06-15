import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ㅇㅎㅊㅊ — 오늘 당신에게 딱 맞는 영화",
  description: "지금 기분과 상황에 딱 맞는 영화를 찾아드려요.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <head>
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
