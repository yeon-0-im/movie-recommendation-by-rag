// ohcc-data.jsx — 영화 데이터 + 추천 대화 플로우
// 4-Pillar Taxonomy: context(상황) / emotion(감정) / sensory(감각) / load(인지부하)

// 포스터 플레이스홀더용 듀오톤 (oklch, 동일 명도·채도, 색상만 변주)
const POSTER_TONES = {
  amber:  { bg: "oklch(0.42 0.09 55)",  ink: "oklch(0.93 0.05 70)" },
  rose:   { bg: "oklch(0.42 0.09 18)",  ink: "oklch(0.93 0.05 30)" },
  plum:   { bg: "oklch(0.42 0.09 330)", ink: "oklch(0.93 0.05 340)" },
  indigo: { bg: "oklch(0.42 0.09 270)", ink: "oklch(0.93 0.05 280)" },
  teal:   { bg: "oklch(0.42 0.09 200)", ink: "oklch(0.93 0.05 200)" },
  forest: { bg: "oklch(0.42 0.09 150)", ink: "oklch(0.93 0.05 150)" },
  slate:  { bg: "oklch(0.40 0.03 250)", ink: "oklch(0.92 0.02 250)" },
};

// 영화 마스터 데이터
const MOVIES = {
  intern: {
    id: "intern", title: "인턴", titleEn: "The Intern", year: 2015,
    tone: "slate", genre: "드라마 · 코미디", runtime: "121분", rating: "전체 관람가",
    tags: { context: "퇴근길·번아웃", emotion: "위로", sensory: "따뜻한 색감", load: "Low-Load" },
    pitch: "회사에 입사한지 얼마 안 돼 적응이 힘든 상황이군요. 인생의 지혜와 따뜻한 위로, 현실적인 직장 공감대를 동시에 얻을 수 있어요. 지금 당신 상황과 딱 맞아서 몰입 잘 될 거예요.",
    synopsis: "70세 시니어 인턴 벤이 잘나가는 스타트업 CEO 줄스의 곁에서 묵묵히 신뢰를 쌓아가는 이야기. 조급할 때 곁에 두면 좋은, 어른의 품격이 담긴 위로.",
    cast: ["로버트 드 니로", "앤 해서웨이"],
  },
  hangover: {
    id: "hangover", title: "행오버", titleEn: "The Hangover", year: 2009,
    tone: "amber", genre: "코미디", runtime: "100분", rating: "청소년 관람불가",
    tags: { context: "머리 비우고 싶을 때", emotion: "텐션 업", sensory: "라스베가스 네온", load: "Low-Load" },
    pitch: "오늘 같은 날엔 뇌를 꺼야 합니다. 전날 기억이 통째로 날아간 총각파티 뒷수습 코미디. 아무 생각 없이 깔깔대다 보면 스트레스가 증발해요.",
    synopsis: "라스베가스 총각파티 다음 날, 신랑은 사라지고 기억은 없다. 단서를 거꾸로 쫓는 막장 추격 코미디.",
    cast: ["브래들리 쿠퍼", "재크 갈리피아나키스"],
  },
  superbad: {
    id: "superbad", title: "슈퍼배드", titleEn: "Superbad", year: 2007,
    tone: "amber", genre: "코미디", runtime: "113분", rating: "청소년 관람불가",
    tags: { context: "가볍게 웃고 싶을 때", emotion: "텐션 업", sensory: "하이틴 무드", load: "Low-Load" },
    pitch: "복잡한 거 1도 없이, 그냥 웃깁니다. 졸업 직전 고등학생들의 좌충우돌 하루. 머리 비우기엔 이만한 게 없어요.",
    synopsis: "졸업을 앞둔 두 친구의 인생 마지막(?) 파티를 향한 하룻밤 대모험.",
    cast: ["조나 힐", "마이클 세라"],
  },
  johnwick: {
    id: "johnwick", title: "존 윅", titleEn: "John Wick", year: 2014,
    tone: "slate", genre: "액션 · 스릴러", runtime: "101분", rating: "청소년 관람불가",
    tags: { context: "답답함을 뚫고 싶을 때", emotion: "카타르시스", sensory: "스타일리시 액션", load: "Fast-paced" },
    pitch: "막힌 속, 이 한 편이면 뻥 뚫립니다. 군더더기 없는 합과 미친 듯이 깔끔한 총격. 스토리는 단순하고 액션은 압도적이에요.",
    synopsis: "은퇴한 전설의 킬러가 단 하나 남은 소중한 것을 건드린 자들을 향해 돌아온다. 시원함의 정석.",
    cast: ["키아누 리브스"],
  },
  madmax: {
    id: "madmax", title: "매드맥스: 분노의 도로", titleEn: "Mad Max: Fury Road", year: 2015,
    tone: "rose", genre: "액션", runtime: "120분", rating: "15세 관람가",
    tags: { context: "다 부수고 싶을 때", emotion: "카타르시스", sensory: "압도적 미장센", load: "Fast-paced" },
    pitch: "폭발하고 질주하고, 끝. 2시간 내내 엔진 풀가동. 사막을 가로지르는 광기의 추격전이 스트레스를 통째로 날려버립니다.",
    synopsis: "황폐한 미래, 폭주하는 개조 차량들의 끝없는 추격. 영화사에 길이 남을 액션의 향연.",
    cast: ["톰 하디", "샤를리즈 테론"],
  },
  fast: {
    id: "fast", title: "분노의 질주", titleEn: "Fast & Furious", year: 2009,
    tone: "indigo", genre: "액션", runtime: "107분", rating: "12세 관람가",
    tags: { context: "질주하고 싶을 때", emotion: "텐션 업", sensory: "엔진 사운드", load: "Low-Load" },
    pitch: "고민할 시간에 액셀을 밟습니다. 패밀리와 자동차, 그리고 폭발. 머리 비우고 보는 질주 본능의 끝판왕.",
    synopsis: "거리의 레이서들이 모여 벌이는 초고속 카 체이스 액션 시리즈의 시작.",
    cast: ["빈 디젤", "폴 워커"],
  },
  killbill: {
    id: "killbill", title: "킬 빌", titleEn: "Kill Bill", year: 2003,
    tone: "rose", genre: "액션 · 스릴러", runtime: "111분", rating: "청소년 관람불가",
    tags: { context: "강렬함이 필요할 때", emotion: "카타르시스", sensory: "타란티노 스타일", load: "Fast-paced" },
    pitch: "독하고, 강렬하고, 스타일리시합니다. 복수 하나로 직진하는 핏빛 미학. 자극이 필요한 날 정확히 꽂혀요.",
    synopsis: "결혼식장에서 모든 걸 잃은 여자가 복수의 칼날을 갈고 돌아온다.",
    cast: ["우마 서먼"],
  },
  abouttime: {
    id: "abouttime", title: "어바웃 타임", titleEn: "About Time", year: 2013,
    tone: "forest", genre: "로맨스 · 드라마", runtime: "123분", rating: "15세 관람가",
    tags: { context: "이별 직후", emotion: "위로", sensory: "따뜻한 영국 색감", load: "Low-Load" },
    pitch: "헤어짐이 아릴 땐, 다시 살아갈 용기를 주는 영화. 시간을 되돌릴 수 있어도 결국 중요한 건 지금이라는 위로. 펑펑 울고 나면 개운해져요.",
    synopsis: "시간을 되돌리는 능력을 가진 남자가 사랑과 일상의 소중함을 깨닫는 따뜻한 이야기.",
    cast: ["돔놀 글리슨", "레이첼 맥아담스"],
  },
  "500days": {
    id: "500days", title: "500일의 썸머", titleEn: "(500) Days of Summer", year: 2009,
    tone: "teal", genre: "로맨스 · 드라마", runtime: "95분", rating: "12세 관람가",
    tags: { context: "이별 직후", emotion: "공감·정화", sensory: "감각적인 색감", load: "Low-Load" },
    pitch: "지금 당신 마음, 이 영화가 대신 말해줍니다. 사랑의 시작과 끝을 솔직하게 그린 이야기. 아프지만 결국 앞으로 나아가게 해줘요.",
    synopsis: "운명을 믿는 남자와 사랑을 의심하는 여자의 500일을 뒤섞어 보여주는 이별 후일담.",
    cast: ["조셉 고든레빗", "주이 디샤넬"],
  },
  begin: {
    id: "begin", title: "비긴 어게인", titleEn: "Begin Again", year: 2013,
    tone: "teal", genre: "음악 · 드라마", runtime: "104분", rating: "15세 관람가",
    tags: { context: "이별 후 회복기", emotion: "위로", sensory: "사운드트랙 맛집", load: "Low-Load" },
    pitch: "음악이 무너진 마음을 다시 일으켜요. 이별 후 길거리 음악으로 다시 일어서는 이야기. 듣다 보면 나도 다시 시작하고 싶어집니다.",
    synopsis: "실연 당한 싱어송라이터와 한물간 음악 프로듀서가 뉴욕 거리에서 앨범을 만든다.",
    cast: ["키이라 나이틀리", "마크 러팔로"],
  },
  whiplash: {
    id: "whiplash", title: "위플래쉬", titleEn: "Whiplash", year: 2014,
    tone: "amber", genre: "드라마 · 음악", runtime: "107분", rating: "15세 관람가",
    tags: { context: "동기부여가 필요할 때", emotion: "텐션 업", sensory: "숨막히는 드럼", load: "High-Load" },
    pitch: "느슨해진 멘탈에 채찍질이 필요할 때. 광기 어린 연습과 압박이 심장을 조여옵니다. 보고 나면 뭐라도 해내고 싶어져요.",
    synopsis: "최고가 되려는 드러머와 그를 극한으로 몰아붙이는 폭군 교수의 대결.",
    cast: ["마일즈 텔러", "J.K. 시몬스"],
  },
  bohemian: {
    id: "bohemian", title: "보헤미안 랩소디", titleEn: "Bohemian Rhapsody", year: 2018,
    tone: "indigo", genre: "음악 · 드라마", runtime: "134분", rating: "12세 관람가",
    tags: { context: "끓어오르고 싶을 때", emotion: "카타르시스", sensory: "전설의 라이브", load: "Low-Load" },
    pitch: "심장이 다시 뛰게 만드는 영화. 퀸의 음악과 함께 끓어오르는 라이브 에이드 피날레. 보고 나면 세상 다 가진 기분이에요.",
    synopsis: "전설적 밴드 퀸과 프레디 머큐리의 삶, 그리고 역사적인 라이브 무대.",
    cast: ["라미 말렉"],
  },
  intouchables: {
    id: "intouchables", title: "언터처블: 1%의 우정", titleEn: "The Intouchables", year: 2011,
    tone: "forest", genre: "코미디 · 드라마", runtime: "112분", rating: "12세 관람가",
    tags: { context: "기운이 필요할 때", emotion: "위로·미소", sensory: "유쾌한 색감", load: "Low-Load" },
    pitch: "보기만 해도 기분이 좋아지는 영화. 정반대의 두 사람이 만드는 따뜻하고 유쾌한 우정. 무겁지 않게, 가볍게 힐링돼요.",
    synopsis: "전신마비 백만장자와 거친 동네 청년이 신분을 넘어 쌓아가는 진짜 우정.",
    cast: ["프랑수아 클루제", "오마 사이"],
  },
  amelie: {
    id: "amelie", title: "아멜리에", titleEn: "Amélie", year: 2001,
    tone: "forest", genre: "로맨스 · 코미디", runtime: "122분", rating: "15세 관람가",
    tags: { context: "프랑스어 공부", emotion: "산뜻한 위로", sensory: "색감 깡패", load: "Low-Load" },
    pitch: "눈이 먼저 행복해지는 영화. 파리의 색감과 아기자기한 상상력이 가득. 프랑스어 리스닝과 힐링을 한 번에 챙겨요.",
    synopsis: "타인의 행복을 몰래 돕는 파리지앵 아멜리에의 사랑스러운 일상.",
    cast: ["오드리 토투"],
  },
  paddington: {
    id: "paddington", title: "패딩턴", titleEn: "Paddington", year: 2014,
    tone: "teal", genre: "가족 · 코미디", runtime: "95분", rating: "전체 관람가",
    tags: { context: "영어 공부·가벼운 힐링", emotion: "위로·미소", sensory: "산뜻한 영국 무드", load: "Low-Load" },
    pitch: "마음이 말랑해지는 영화. 또박또박한 영국식 영어와 사랑스러운 곰 한 마리. 부담 없이 보기 딱 좋아요.",
    synopsis: "런던에 온 작은 곰 패딩턴이 한 가족과 가까워지며 벌어지는 따뜻한 소동.",
    cast: ["벤 위쇼(목소리)"],
  },
  lalaland: {
    id: "lalaland", title: "라라랜드", titleEn: "La La Land", year: 2016,
    tone: "plum", genre: "로맨스 · 뮤지컬", runtime: "128분", rating: "12세 관람가",
    tags: { context: "감성에 젖고 싶을 때", emotion: "여운", sensory: "색감 깡패·사운드트랙", load: "Low-Load" },
    pitch: "화면과 음악에 그냥 취하는 영화. 황혼의 LA, 춤추는 색감과 멜로디. 분위기에 흠뻑 젖고 싶은 날 완벽해요.",
    synopsis: "꿈을 좇는 두 예술가의 만남과 엇갈림을 그린 황홀한 뮤지컬.",
    cast: ["라이언 고슬링", "엠마 스톤"],
  },
};

// 추천 대화 플로우 (Step1 진입 → Step2 튜닝 질문 → 영화 세트)
const FLOWS = {
  stress: {
    label: "스트레스 해소",
    userEcho: "오늘 회사에서 완전 깨짐. 뇌 비우고 스트레스 풀 만한 영화 추천해줘",
    aiQuestion: "많이 답답하셨겠어요. 차라리 아무 생각 없이 깔깔 웃기는 영화가 좋은가요, 아니면 스토리는 짱짱하고 시원한 액션이 좋은가요?",
    options: [
      { label: "그냥 웃긴 거", movies: ["hangover", "superbad", "intouchables"] },
      { label: "스릴 넘치고 시원한 거", movies: ["johnwick", "killbill", "madmax"] },
      { label: "폭발하고 질주하는 거", movies: ["madmax", "fast", "johnwick"] },
      { label: "잔인한 거", movies: ["killbill", "johnwick", "madmax"] },
    ],
  },
  breakup: {
    label: "이별 치유",
    userEcho: "얼마 전에 헤어졌어. 마음 좀 추스를 영화 없을까?",
    aiQuestion: "마음이 많이 헛헛하시겠어요. 펑펑 울고 개운해지는 쪽이 좋아요, 아니면 음악으로 슬며시 일어서는 쪽이 좋아요?",
    options: [
      { label: "펑펑 울고 싶어", movies: ["abouttime", "500days", "begin"] },
      { label: "공감되는 이야기", movies: ["500days", "abouttime", "lalaland"] },
      { label: "음악으로 위로받고 싶어", movies: ["begin", "lalaland", "abouttime"] },
      { label: "그냥 기분 풀고 싶어", movies: ["intouchables", "begin", "lalaland"] },
    ],
  },
  boost: {
    label: "자극과 동기부여",
    userEcho: "요즘 너무 늘어졌어. 정신 번쩍 들 영화 추천해줘",
    aiQuestion: "지금 필요한 건 채찍질이군요. 압박감 속에서 끓어오르는 쪽이 좋아요, 아니면 짜릿한 성취감으로 벅차오르는 쪽이 좋아요?",
    options: [
      { label: "독하게 채찍질", movies: ["whiplash", "madmax", "johnwick"] },
      { label: "벅차오르는 성취감", movies: ["bohemian", "whiplash", "begin"] },
      { label: "끓어오르는 에너지", movies: ["bohemian", "madmax", "fast"] },
      { label: "심장 뛰는 라이브", movies: ["bohemian", "begin", "lalaland"] },
    ],
  },
  light: {
    label: "언어공부·가벼운 힐링",
    userEcho: "부담 없이 보면서 외국어도 익힐 만한 영화 있어?",
    aiQuestion: "좋아요, 가볍게 가시죠. 또박또박한 영어가 좋아요, 아니면 색감 예쁜 프랑스어가 좋아요?",
    options: [
      { label: "또박또박 영어", movies: ["paddington", "intouchables", "begin"] },
      { label: "색감 예쁜 프랑스어", movies: ["amelie", "intouchables", "lalaland"] },
      { label: "그냥 힐링되는 거", movies: ["intouchables", "paddington", "amelie"] },
      { label: "감성 충전", movies: ["lalaland", "amelie", "begin"] },
    ],
  },
};

// 대안 풀 (이미 봤어 / 다른 거 → 교체용)
const ALT_POOL = ["lalaland", "intern", "amelie", "begin", "intouchables", "paddington", "abouttime", "bohemian", "johnwick", "hangover"];

// 파싱된 실제 리뷰 원문 (추천 근거) — 출처/작성자는 익명 처리
const REVIEWS = {
  intern: [
    { q: "퇴근하고 지친 날 봤는데 벤 할아버지가 그냥 위로 그 자체임… 나도 이런 어른 옆에 두고 싶다", src: "왓챠 · 평점 4.5" },
    { q: "회사 적응 안 돼서 힘들 때 보면 진짜 공감 백배. 잔잔하게 마음이 풀림", src: "네이버 관람평" },
  ],
  hangover: [
    { q: "아무 생각 없이 깔깔거리다 끝남ㅋㅋ 머리 비우기엔 이게 최고", src: "왓챠 · 평점 4.0" },
    { q: "스트레스 받은 날 보면 진짜 다 잊고 웃게 됨. 전개도 안 지루함", src: "CGV 골든에그" },
  ],
  superbad: [
    { q: "그냥 처음부터 끝까지 웃겼다. 복잡한 거 1도 없음", src: "네이버 관람평" },
    { q: "하이틴 특유의 찌질함이 너무 웃겨ㅋㅋ 부담 없이 보기 딱", src: "왓챠 · 평점 3.5" },
  ],
  johnwick: [
    { q: "막혔던 속이 뻥 뚫림. 액션 합이 미쳤고 군더더기가 없다", src: "왓챠 · 평점 4.5" },
    { q: "스토리는 단순한데 그게 매력. 그냥 시원하게 부숴버리는 영화", src: "네이버 관람평" },
  ],
  madmax: [
    { q: "2시간 내내 질주하고 폭발함. 보고 나니 스트레스가 증발했다", src: "CGV 골든에그" },
    { q: "미장센 미쳤다… 극장에서 본 게 인생 최고의 선택", src: "왓챠 · 평점 5.0" },
  ],
  fast: [
    { q: "생각 없이 보기 좋은 카체이싱. 엔진 소리에 도파민 터짐", src: "네이버 관람평" },
    { q: "패밀리랑 자동차랑 폭발. 그냥 신나게 봤다", src: "왓챠 · 평점 3.5" },
  ],
  killbill: [
    { q: "강렬하고 스타일리시함. 복수극 하나로 직진하는 게 시원하다", src: "왓챠 · 평점 4.0" },
    { q: "타란티노 미감 제대로… 자극 필요할 때 딱", src: "네이버 관람평" },
  ],
  abouttime: [
    { q: "헤어지고 펑펑 울면서 봤는데 이상하게 개운해짐. 다시 살 용기를 줌", src: "왓챠 · 평점 4.5" },
    { q: "결국 중요한 건 지금이라는 말에 눈물… 위로받고 싶을 때 강추", src: "CGV 골든에그" },
  ],
  "500days": [
    { q: "지금 내 마음을 영화가 대신 말해주는 느낌. 아프지만 솔직해서 좋다", src: "왓챠 · 평점 4.0" },
    { q: "이별 직후에 보니까 너무 공감됐다. 그래도 앞으로 나아가게 해줌", src: "네이버 관람평" },
  ],
  begin: [
    { q: "무너진 마음을 음악이 일으켜 세워줌. 듣다 보니 나도 다시 시작하고 싶어짐", src: "왓챠 · 평점 4.5" },
    { q: "이별 후에 들으면 사운드트랙이 다 위로가 된다", src: "네이버 관람평" },
  ],
  whiplash: [
    { q: "느슨했던 멘탈에 채찍질 제대로 당함. 보고 나서 뭐라도 하게 됨", src: "왓챠 · 평점 4.5" },
    { q: "숨 막히는 긴장감… 동기부여 필요할 때 이만한 게 없다", src: "CGV 골든에그" },
  ],
  bohemian: [
    { q: "라이브 에이드 장면에서 심장이 다시 뛰었다. 끝나고 세상 다 가진 기분", src: "왓챠 · 평점 5.0" },
    { q: "퀸 노래에 끓어오름. 무기력할 때 보면 벅차오른다", src: "네이버 관람평" },
  ],
  intouchables: [
    { q: "보기만 해도 기분 좋아지는 영화. 무겁지 않게 힐링됨", src: "왓챠 · 평점 4.5" },
    { q: "정반대 두 사람 우정이 따뜻하고 유쾌하다. 기운 없을 때 추천", src: "네이버 관람평" },
  ],
  amelie: [
    { q: "눈이 먼저 행복해지는 색감… 보는 내내 기분이 산뜻해진다", src: "왓챠 · 평점 4.5" },
    { q: "프랑스어 공부 겸 틀었다가 분위기에 그냥 빠져버림", src: "네이버 관람평" },
  ],
  paddington: [
    { q: "마음이 말랑해지는 영화. 또박또박한 영국 영어라 듣기도 편함", src: "왓챠 · 평점 4.0" },
    { q: "부담 없이 보기 딱 좋고 곰이 너무 사랑스럽다", src: "CGV 골든에그" },
  ],
  lalaland: [
    { q: "화면이랑 음악에 그냥 취함. 감성에 젖고 싶은 날 완벽한 선택", src: "왓챠 · 평점 4.5" },
    { q: "엔딩 보고 한참 여운 남았다. 색감과 멜로디가 계속 맴돔", src: "네이버 관람평" },
  ],
};

Object.assign(window, { POSTER_TONES, MOVIES, FLOWS, ALT_POOL, REVIEWS });
