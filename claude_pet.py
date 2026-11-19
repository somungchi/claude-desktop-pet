"""Claude 펫: 화면 오른쪽 밖에서 튀어나와 사과하는 데스크톱 마스코트.
실행: pythonw claude_pet.py   (콘솔 없이)  /  python claude_pet.py
호출: curl http://127.0.0.1:47321/sorry   (사과하며 등장)  /hi (인사)  /ladder /plant /rest  /done (작업 완료 알림)  /quit (종료)
상주 중엔 가끔 앉거나 휘파람 불거나 혼잣말함. 대화: 펫을 우클릭하면 입력창(가만있어/앉아/엎드려/돌아다녀/일어나/통통 등). 조작: 머리를 잡고 끌면 원하는 곳에 둠, 가끔 좌우로 저벅저벅 걸음. 머리 쪽에서 마우스를 좌우로 왔다갔다 = 쓰담쓰담(친밀도+3), 뒤돌았을 때 엉덩이 클릭 = 때찌(아야!)
"""
import datetime, io, json, math, os, queue, random, re, threading, time, tkinter as tk
import urllib.parse, urllib.request
try:  # 이미 펫이 떠 있으면(예: 아침 8시 예약 실행과 겹침) 두 마리 안 뜨게 바로 종료
    urllib.request.urlopen("http://127.0.0.1:47321/ping", timeout=1); raise SystemExit
except SystemExit: raise
except Exception: pass
try:
    from PIL import Image, ImageDraw, ImageTk  # 선물 이미지용 (없으면 이모지로 대체)
except ImportError:
    Image = None
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
SAVE = os.path.join(HERE, "pet_save.json")
MAX_AFF = 100
GIFT_EVERY = 10  # 친밀도가 이 값의 배수를 넘을 때마다 선물
GIFTS = [("황금 목걸이", "gold necklace"), ("지렁이", "earthworm"), ("꿀사과", "honeycrisp apple"),
         ("황금 변기", "golden toilet"), ("초대형 오리 인형", "rubber duck"), ("감자", "potato"),
         ("마른 멸치", "dried anchovy"), ("우승 트로피", "trophy"), ("금괴", "gold bar"), ("도넛", "donut"),
         ("컵라면", "instant noodles cup"), ("후라이드 치킨", "fried chicken"), ("피자 한 판", "pizza"),
         ("공룡 화석", "dinosaur fossil"), ("삽", "shovel"), ("고구마", "sweet potato"),
         ("두루마리 휴지", "toilet paper roll"), ("다이아몬드", "diamond")]  # 선물 이미지는 Wikimedia Commons 검색
CATS = [("모자", ["밀짚모자", "티아라", "이모 앞머리", "갸루 소라빵머리", "유치원 노란 모자"]), ("상의", ["빨간 후드", "이모 스웨터", "갸루 크롭탑", "하늘색 카라티"]), ("하의", ["청치마", "체크 치마", "이모 체인 치마", "갸루 미니스커트", "유치원 반바지"]), ("허리", ["징 벨트"]), ("손목", ["체크 손목밴드"])]  # 한 부위에는 하나만 입음
OUTFITS = [o for _, lst in CATS for o in lst]
CAT_OF = {o: cat for cat, lst in CATS for o in lst}
PLACES = ["길가 쓰레기통에서", "옆집 빨랫줄에서", "분실물 센터에서", "택배 상자 밑에서", "공원 벤치에서", "제 주머니를 뒤졌더니"]
SORRY = ["죄송해요… 제가 실수했어요 ㅠㅠ", "앗, 제가 틀렸어요. 벌 받을게요!", "잘못했어요… 저는 맞아도 싸요 🥺"]
PET = ["헤헤 좋아요~", "쓰담쓰담 최고예요 💕", "더 해주세요!", "오늘도 열심히 할게요!"]
TALK = ["오늘 코드 몇 줄이나 짰더라…", "버그 없는 세상… 있을까…", "아 배고파… 꿀사과 먹고 싶다",
        "(두리번두리번)", "혼자 있으니까 조용하네요…", "커피 한잔 하고 싶다…", "오늘도 수고했어요 흐흐"]
HIT = ["아야!! 😭", "으앗! 다신 안 그럴게요ㅠㅠ", "때찌 맞았어요… 반성 중…"]

try:
    save = json.load(open(SAVE, encoding="utf-8"))
except Exception:
    save = {"aff": 0, "inv": {}}
save.setdefault("outfit", [])
save["outfit"] = [x for x in save["outfit"] if x in OUTFITS]  # 옛 그림 옷은 정리
def wear_on(o):  # 옷 입기: 같은 부위에 입고 있던 건 벗음
    save["outfit"][:] = [x for x in save["outfit"] if CAT_OF[x] != CAT_OF[o]] + [o]
for _o in list(save["outfit"]): wear_on(_o)  # 예전 저장에 겹쳐 있던 것 정리
save["owned"] = [x for x in save.setdefault("owned", list(save["outfit"])) if x in OUTFITS]
save["owned"] += [x for x in ("유치원 노란 모자", "하늘색 카라티", "유치원 반바지", "징 벨트", "체크 손목밴드", "이모 앞머리", "이모 스웨터", "이모 체인 치마", "갸루 소라빵머리", "갸루 크롭탑", "갸루 미니스커트") if x not in save["owned"]]  # 목도리는 선물로 바로 지급  # 가진 옷 (입은 옷은 그중 일부)
GIFT_DIR = os.path.join(HERE, "gift_img"); os.makedirs(GIFT_DIR, exist_ok=True)  # 가방에 보여줄 선물 사진 (git 제외)
save.setdefault("coin", 0); save.setdefault("skin_until", 0)
PRICE = {"황금 변기": 600, "다이아몬드": 800, "금괴": 500, "황금 목걸이": 400, "우승 트로피": 300, "초대형 오리 인형": 120, "삽": 80, "공룡 화석": 350,
         "지렁이": 10, "마른 멸치": 20, "감자": 15, "고구마": 20, "꿀사과": 30, "도넛": 25, "컵라면": 30, "후라이드 치킨": 60, "피자 한 판": 70, "두루마리 휴지": 15}
def price(k): return PRICE.get(k, 40)
OUTFIT_COST, SNACK_COST, SKIN_COST = 150, 40, 300  # 펫이 직접 쓰는 값
def flush():
    json.dump(save, open(SAVE, "w", encoding="utf-8"), ensure_ascii=False)

W, H, TR = 340, 290, "#010203"  # 오른쪽 100px은 선물 이미지를 손 옆에 내밀 자리
S = 0.6  # 캐릭터 크기 배율 (더 작게: 0.5)
root = tk.Tk()
root.overrideredirect(True); root.attributes("-topmost", True)
root.attributes("-transparentcolor", TR); root.config(bg=TR)
SW = root.winfo_screenwidth(); Y = root.winfo_screenheight() - H - 60
c = tk.Canvas(root, width=W, height=H, bg=TR, highlightthickness=0); c.pack()
SH = root.winfo_screenheight()
XL, XR, YT, YB = -70, SW - 170, -100, SH - H  # 창 여백(캔버스 340x290 중 펫은 가운데 작게 그려짐)을 빼고 펫 몸이 화면 구석까지 가게
def cx(x): return max(XL, min(XR, x))
def cy(y): return max(YT, min(YB, y))
px, py = save.get("pos", [SW - W, Y])
px, py = cx(px), cy(py)  # 화면 밖에 저장돼 있으면 안으로
root.geometry(f"{W}x{H}+{px}+{py}")  # 항상 화면에 상주
hide_id, mood, busy = None, "normal", False
mode, gen, pgen = "auto", 0, 0  # mode: auto(알아서) / roam(계속 움직임) / still / sit / plank  # busy: 끄는 중이거나 걷는 중
SKINS = [("기본 주황", "#D97757"), ("흰색", "#F6EFE8"), ("보라", "#9B7BD8"), ("분홍", "#F29BB5"), ("민트", "#7CCFB0")]
def darker(h, k=0.62): return "#%02x%02x%02x" % tuple(int(int(h[i:i + 2], 16) * k) for i in (1, 3, 5))
ORANGE, DARK = SKINS[save.get("skin", 0) % len(SKINS)][1], "#3b2a22"
OUTL = darker(ORANGE, 0.66)  # 몸/옷 테두리: 검정 대신 진한 갈색 (눈·입은 DARK 그대로)
sq = [1.0, 1.0]  # 말랑 변형(가로, 세로 배율)

def rrect(x0, y0, x1, y1, r=8, **kw):  # 모서리가 둥근 사각형 (smooth 다각형)
    pts = [x0+r, y0, x1-r, y0, x1, y0, x1, y0+r, x1, y1-r, x1, y1, x1-r, y1, x0+r, y1, x0, y1, x0, y1-r, x0, y0+r, x0, y0]
    return c.create_polygon(pts, smooth=True, **kw)

def lerp(a, b, f): return tuple(round(x + (y - x) * f) for x, y in zip(a, b))
def limbs(m, f, arm):
    if m == "read":  # 책 양옆을 팔로 잡음 (별도 손을 그리지 않음)
        return [(52, 168 + round(3 * f), 74, 200 + round(3 * f)), (166, 168, 188, 200), (80, 200, 102, 232), (138, 200, 160, 232)]
    if m == "game":  # 게임기 양옆을 잡고 버튼 누르는 쪽 팔이 살짝 움직임
        return [(50, 160, 72, 192), (168, 160 + round(4 * f), 190, 192 + round(4 * f)), (80, 200, 102, 232), (138, 200, 160, 232)]
    if m == "work":  # 팔을 키보드 높이로 내리고 번갈아 두드림
        return [(44, 146 + round(10 * f), 66, 178 + round(10 * f)), (174, 146 + round(10 * (1 - f)), 196, 178 + round(10 * (1 - f))), (80, 200, 102, 232), (138, 200, 160, 232)]
    if m == "gym":  # 덤벨을 들어올릴수록 팔이 올라감
        y = round(140 - 85 * f); return [(50, y, 72, y + 30), (168, y, 190, y + 30), (80, 200, 102, 232), (138, 200, 160, 232)]
    if m == "jack":  # 팔 벌려 뛰기
        return [lerp((40, 148, 62, 178), (34, 84, 56, 116), f), lerp((178, 148, 200, 178), (184, 84, 206, 116), f), lerp((82, 200, 104, 232), (62, 200, 84, 232), f), lerp((136, 200, 158, 232), (156, 200, 178, 232), f)]
    if m == "rope": return [(34, 140, 56, 170), (184, 140, 206, 170), (80, 200, 102, 232), (138, 200, 160, 232)]
    if m == "run":  # 달리기: 팔다리를 번갈아
        A = [(44, 112, 66, 142), (174, 142, 196, 172), (72, 196, 94, 222), (146, 200, 168, 232)]; B = [(36, 142, 58, 172), (182, 112, 204, 142), (76, 200, 98, 232), (142, 196, 164, 222)]
        return [lerp(a, b, f) for a, b in zip(A, B)]
    return limbs0(m, f, arm)

def limbs0(m, f, arm):  # 팔다리 위치. struggle(잡혀서 발버둥)이면 프레임 f에 따라 번갈아 휘두름
    if m in ("struggle", "climb", "farm", "rummage"):
        return [(40, 100, 62, 130) if f == 0 else (40, 150, 62, 180),
                (178, 150, 200, 180) if f == 0 else (178, 100, 200, 130),
                (66, 205, 88, 234) if f == 0 else (90, 200, 112, 224),
                (152, 200, 174, 224) if f == 0 else (128, 205, 150, 234)]
    return [(40, 148, 62, 178), arm, (80, 200, 102, 232), (138, 200, 160, 232)]

def anger(x, y, o):  # 💢 대신: 빨간 ㄱ자 네 개
    for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        c.create_line(x + dx * 3, y + dy * 9, x + dx * 3, y + dy * 3, x + dx * 9, y + dy * 3, fill="#e23b3b", width=2, **o)

def sweat(x, y, o):  # 💦 대신: 파란 땀방울
    for dx, dy in ((0, 0), (9, 8), (-2, 14)):
        c.create_polygon(x+dx, y+dy-6, x+dx+4, y+dy+2, x+dx-4, y+dy+2, fill="#5ab4f0", outline="#2d7fc0", **o)
        c.create_oval(x+dx-4, y+dy-1, x+dx+4, y+dy+7, fill="#5ab4f0", outline="#2d7fc0", **o)

def icon(kind, x, y, o):  # 건네는 물건 아이콘: 옷(티셔츠) / 선물상자
    if kind == "👕":
        pts = [(-18, -12), (-7, -16), (-3, -12), (3, -12), (7, -16), (18, -12), (22, -2), (13, 1), (10, -3), (10, 16), (-10, 16), (-10, -3), (-13, 1), (-22, -2)]
        c.create_polygon([v for px, py in pts for v in (x + px, y + py)], fill="#5aa9e6", outline=OUTL, width=2, **o)
        c.create_line(x - 3, y - 12, x, y - 8, x + 3, y - 12, fill=DARK, width=2, **o)
    else:
        c.create_rectangle(x - 15, y - 8, x + 15, y + 14, fill="#ff6b6b", outline=OUTL, width=2, **o)
        c.create_rectangle(x - 17, y - 14, x + 17, y - 6, fill="#ff8f8f", outline=OUTL, width=2, **o)
        c.create_rectangle(x - 3, y - 14, x + 3, y + 14, fill="#ffd84d", **o)
        c.create_oval(x - 10, y - 24, x, y - 13, outline="#ffd84d", width=3, **o)
        c.create_oval(x, y - 24, x + 10, y - 13, outline="#ffd84d", width=3, **o)

OUTFIT_DIR = os.path.join(HERE, "outfit_img")  # 옷 사진(누끼 PNG) 보관 (git 제외)
os.makedirs(OUTFIT_DIR, exist_ok=True)
OUTFIT_Q = {"밀짚모자": "straw hat", "중절모": "fedora hat", "선글라스": "sunglasses", "티아라": "tiara museum jewellery"}
OUTFIT_EX = " -portrait -man -woman -girl -boy -people -person -model -wearing -painting -singer -actress -queen -princess"
OUTFIT_SHAPE = {"밀짚모자": (0.8, 2.5), "중절모": (0.8, 2.5), "선글라스": (1.6, 4.5), "티아라": (1.3, 5)}  # 가로/세로 비율 허용 범위
# 입은 모습: (그릴 가로폭, 기준점 방향, x, y)  좌표는 축소 전 캐릭터 좌표
OUTFIT_SPEC = {"밀짚모자": (190, "s", 120, 100), "중절모": (150, "s", 120, 98), "티아라": (90, "s", 120, 106), "선글라스": (100, "center", 120, 128)}
worn_ph = {}  # 옷 PhotoImage 캐시 (참조를 들고 있어야 함)
def worn_image(n):
    if n in worn_ph: return worn_ph[n]
    if n not in OUTFIT_SPEC: return None
    path = os.path.join(OUTFIT_DIR, n + ".png")
    if not (Image and os.path.exists(path)): return None
    im = Image.open(path).convert("RGBA"); w = max(1, int(OUTFIT_SPEC[n][0] * S)); h = max(1, int(im.height * w / im.width))
    worn_ph[n] = ImageTk.PhotoImage(im.resize((w, h), Image.LANCZOS)); return worn_ph[n]

def wear(o, front, arms, legs):  # 입은 옷: 사진 누끼 우선, 없으면 그림 (선글라스는 앞모습일 때만)
    for n in sorted(save["outfit"], key=OUTFITS.index):  # 부위 순서대로(상의 → 하의 → 신발)
        ph = worn_image(n)
        if ph:
            if not (n == "선글라스" and not front):
                _, anchor, x, y = OUTFIT_SPEC[n]; c.create_image(x, y, image=ph, anchor=anchor, **o)
            continue
        if n == "밀짚모자":  # 챙 넓은 밀짚모자: 챙 + 둥근 머리 + 빨간 띠 + 결
            c.create_oval(58, 84, 182, 106, fill="#e8c874", outline=OUTL, width=2, **o)
            c.create_arc(86, 54, 154, 100, start=0, extent=180, style="chord", fill="#f0d58a", outline=OUTL, width=2, **o)
            c.create_rectangle(87, 84, 153, 92, fill="#c0392b", outline=OUTL, **o)
            for x in range(92, 150, 10): c.create_line(x, 62 + abs(x - 120) // 4, x, 82, fill="#d4b05c", **o)
        elif n == "중절모":  # 챙 + 눌린 크라운 + 검은 띠
            c.create_oval(72, 86, 168, 102, fill="#55555f", outline=OUTL, width=2, **o)
            c.create_polygon(92, 90, 92, 66, 104, 58, 120, 66, 136, 58, 148, 66, 148, 90, fill="#6b6b78", outline=OUTL, width=2, **o)
            c.create_rectangle(92, 80, 148, 90, fill="#222", outline=OUTL, **o)
            c.create_rectangle(134, 78, 144, 92, fill="#c0392b", outline=OUTL, **o)
        elif n == "티아라":  # 작은 은색 티아라 + 보석
            c.create_polygon(94, 90, 98, 74, 108, 84, 120, 64, 132, 84, 142, 74, 146, 90, fill="#e8e8f0", outline=OUTL, width=2, **o)
            c.create_rectangle(94, 88, 146, 95, fill="#cfcfe0", outline=OUTL, width=2, **o)
            c.create_oval(115, 67, 125, 77, fill="#ff5d8f", outline=OUTL, **o)
            for gx in (98, 142): c.create_oval(gx - 3, 71, gx + 3, 77, fill="#5ab4f0", outline=OUTL, **o)
        elif n == "동그란 안경" and front:  # 얇은 동그란 안경테
            for ex in (95, 145): c.create_oval(ex - 15, 111, ex + 15, 141, outline="#3a2a1a", width=3, **o)
            c.create_line(110, 124, 130, 124, fill="#3a2a1a", width=3, **o)
            c.create_line(80, 122, 60, 118, fill="#3a2a1a", width=2, **o); c.create_line(160, 122, 180, 118, fill="#3a2a1a", width=2, **o)
        elif n == "줄무늬 티셔츠":  # 파랑/흰 줄무늬 + 소매
            rrect(60, 158, 180, 205, r=6, fill="#ffffff", outline=OUTL, width=2, **o)
            for y in range(162, 204, 12): c.create_rectangle(62, y, 178, y + 6, fill="#4a86c8", outline="", **o)
        elif n == "빨간 후드":  # 빨간 후드티: 앞주머니 + 끈
            rrect(60, 158, 180, 205, r=6, fill="#d83a3a", outline=OUTL, width=2, **o)
            for (x0, y0, x1, y1) in arms: rrect(x0, y0, x1, y1 - 8, r=8, fill="#d83a3a", outline=OUTL, width=2, **o)
            if front:
                c.create_rectangle(88, 180, 152, 198, fill="#b82e2e", outline=OUTL, **o)
                for ex in (106, 134): c.create_line(ex, 158, ex, 172, fill="white", width=2, **o)
        elif n == "징 벨트":  # 검정 벨트 + 은색 징 + 별 해골 버클
            c.create_rectangle(62, 184, 178, 194, fill="#1a1418", outline=OUTL, width=2, **o)
            for x in range(68, 112, 9): c.create_oval(x - 2, 187, x + 2, 191, fill="#d7dae2", outline="", **o)
            for x in range(132, 176, 9): c.create_oval(x - 2, 187, x + 2, 191, fill="#d7dae2", outline="", **o)
            c.create_polygon(120, 177, 124, 186, 133, 186, 126, 191, 129, 200, 120, 195, 111, 200, 114, 191, 107, 186, 116, 186, fill="#c9ccd6", outline=OUTL, **o)
            c.create_oval(116, 186, 124, 194, fill="#1a1418", outline="", **o)
        elif n == "체크 손목밴드":  # 왼팔에 흑백 체크 손목밴드
            ax0, ay0, ax1, ay1 = arms[0]; yy = ay0 + (ay1 - ay0) // 2 - 2
            c.create_rectangle(ax0 - 1, yy, ax1 + 1, yy + 10, fill="white", outline=OUTL, width=2, **o)
            for i, xx in enumerate(range(ax0, ax1, 6)):
                c.create_rectangle(xx, yy + 5 * (i % 2), xx + 6, yy + 5 * (i % 2) + 5, fill="#1a1418", outline="", **o)
        elif n == "유치원 노란 모자":  # 병아리 같은 노란 둥근 모자 + 눈 두 개 + 주황 부리
            c.create_oval(56, 90, 184, 112, fill="#f2c92e", outline=OUTL, width=2, **o)  # 챙
            c.create_arc(70, 56, 170, 132, start=0, extent=180, style="chord", fill="#f7d94c", outline="", **o)  # 둥근 윗부분 (챙 윗선을 덮음)
            c.create_arc(70, 56, 170, 132, start=0, extent=180, style="arc", outline=OUTL, width=2, **o)  # 윗부분 테두리는 바깥 곡선만
            for ex in (104, 136): c.create_oval(ex - 4, 76, ex + 4, 86, fill=DARK, outline="", **o)
            c.create_polygon(112, 88, 128, 88, 120, 98, fill="#f0892b", outline=OUTL, **o)
        elif n == "하늘색 카라티":  # 하늘색 폴로 + 흰 카라 + 단추 + 노란 이름표
            rrect(60, 158, 180, 205, r=6, fill="#8fd0f0", outline=OUTL, width=2, **o)
            for (x0, y0, x1, y1) in arms: rrect(x0 + 2, y0 + 2, x1 - 2, y0 + round((y1 - y0) * 0.5), r=3, fill="#8fd0f0", outline="", **o)  # 반팔: 팔 윗부분만 옷 색으로 칠함 (테두리 없음)
            c.create_polygon(96, 157, 120, 176, 108, 160, fill="white", outline=OUTL, **o); c.create_polygon(144, 157, 120, 176, 132, 160, fill="white", outline=OUTL, **o)
            c.create_line(120, 176, 120, 196, fill="#5ba6cf", width=2, **o)
            for yy in (182, 191): c.create_oval(117, yy - 2, 123, yy + 4, fill="white", outline="", **o)
            c.create_rectangle(144, 174, 170, 190, fill="#ffe46b", outline=OUTL, **o); c.create_oval(152, 178, 162, 186, fill="#f7c72e", outline="", **o)
        elif n == "유치원 반바지":  # 곤색 반바지
            rrect(62, 184, 178, 214, r=6, fill="#2f4a86", outline=OUTL, width=2, **o)
            c.create_rectangle(62, 184, 178, 191, fill="#243a6b", outline=OUTL, **o); c.create_line(120, 191, 120, 214, fill="#1d2f58", width=2, **o)
        elif n == "이모 앞머리":  # 이모 머리: 납작한 정수리 + 왼쪽 얼굴을 통째로 덮는 긴 옆머리(끝이 들쭉날쭉) + 오른쪽은 귀까지 내려옴. 오른쪽 눈만 보임
            H = "#17121a"
            c.create_arc(55, 70, 185, 132, start=0, extent=180, style="chord", fill=H, outline=H, **o)
            c.create_polygon(58, 98, 58, 140, 66, 148, 74, 142, 84, 152, 96, 144, 108, 150, 118, 140, 126, 126, 134, 116, 148, 108, 164, 110, 182, 102, 184, 94, fill=H, outline=H, **o)
            c.create_polygon(170, 100, 186, 100, 187, 138, 181, 146, 175, 138, 169, 142, 166, 120, fill=H, outline=H, **o)
            c.create_polygon(98, 104, 110, 104, 104, 128, 94, 146, fill="#8a4fd0", outline="", **o)
            for (x0, y0, x1, y1) in ((82, 80, 104, 98), (118, 78, 140, 96)): c.create_line(x0, y0, x1, y1, fill="#3a3044", width=2, **o)
        elif n == "갸루 소라빵머리":  # 금발 + 머리 위 양쪽 소라빵(똬리) 머리 + 분홍 곱창밴드
            Y = "#f2d36b"
            for bx in (88, 152):
                c.create_oval(bx - 22, 54, bx + 22, 98, fill=Y, outline=OUTL, width=2, **o)
                c.create_arc(bx - 14, 62, bx + 14, 90, start=40, extent=250, style="arc", outline="#c9a53a", width=2, **o)
                c.create_arc(bx - 7, 69, bx + 7, 83, start=220, extent=250, style="arc", outline="#c9a53a", width=2, **o)
            rrect(58, 82, 182, 106, r=22, fill=Y, outline=OUTL, width=2, **o)
            fr = [60, 118, 76, 110, 92, 122, 108, 110, 120, 124, 132, 110, 148, 122, 164, 110, 180, 118]
            c.create_polygon(60, 100, *fr, 180, 100, fill=Y, outline="", **o)  # 앞머리 면 (윗선 없음)
            c.create_line(*fr, fill=OUTL, width=2, **o); c.create_line(60, 100, 60, 118, fill=OUTL, width=2, **o); c.create_line(180, 100, 180, 118, fill=OUTL, width=2, **o)  # 아랫 물결선만
            for bx, sx in ((88, -1), (152, 1)):  # 소라빵 바깥쪽 위에 분홍 리본
                kx, ky = bx + sx * 18, 66
                c.create_polygon(kx, ky, kx + 14, ky - 9, kx + 14, ky + 9, fill="#ff6fa8", outline=OUTL, width=2, **o); c.create_polygon(kx, ky, kx - 14, ky - 9, kx - 14, ky + 9, fill="#ff6fa8", outline=OUTL, width=2, **o); c.create_oval(kx - 4, ky - 4, kx + 4, ky + 4, fill="#ff3d86", outline=OUTL, **o)
        elif n == "이모 스웨터":  # 검정 + 보라 줄무늬 + 해골 프린트
            rrect(60, 158, 180, 205, r=6, fill="#1a1418", outline=OUTL, width=2, **o)
            for (x0, y0, x1, y1) in arms: rrect(x0 + 2, y0 + 2, x1 - 2, y0 + round((y1 - y0) * 0.5), r=3, fill="#1a1418", outline="", **o)  # 반팔
            for y in range(166, 204, 12): c.create_rectangle(62, y, 178, y + 4, fill="#7a3fb8", outline="", **o)
            c.create_oval(108, 170, 132, 190, fill="#f2eee8", outline="", **o); c.create_oval(113, 176, 119, 183, fill="#1a1418", outline="", **o); c.create_oval(121, 176, 127, 183, fill="#1a1418", outline="", **o)
            c.create_rectangle(113, 189, 127, 196, fill="#f2eee8", outline="", **o)
        elif n == "갸루 크롭탑":  # 분홍 짧은 탑 + 하트 + 흰 끈
            rrect(60, 158, 180, 188, r=12, fill="#ff8fbf", outline=OUTL, width=2, **o)
            c.create_text(120, 173, text="♥", font=("Arial", 15, "bold"), fill="white", **o)
            c.create_line(84, 158, 92, 148, fill="white", width=3, **o); c.create_line(156, 158, 148, 148, fill="white", width=3, **o)
        elif n == "이모 체인 치마":  # 검정 체크 + 보라 줄 + 은색 체인
            c.create_polygon(62, 184, 178, 184, 188, 216, 52, 216, fill="#1a1418", outline=OUTL, width=2, **o)
            for y in (196, 208): c.create_line(54, y, 186, y, fill="#7a3fb8", **o)
            for x in range(72, 172, 20): c.create_line(x, 186, x + 4, 214, fill="#7a3fb8", **o)
            c.create_line(62, 188, 96, 200, 130, 192, 176, 200, fill="#cfd2dc", width=2, dash=(3, 2), **o)
        elif n == "갸루 미니스커트":  # 분홍 초미니 + 흰 프릴 + 하트 점
            c.create_polygon(62, 184, 178, 184, 186, 208, 54, 208, fill="#ff9ac6", outline=OUTL, width=2, **o)
            c.create_polygon(54, 208, 186, 208, 182, 216, 170, 211, 150, 217, 130, 211, 110, 217, 90, 211, 70, 217, 56, 212, fill="white", outline=OUTL, **o)
            for (hx, hy) in ((84, 196), (120, 200), (156, 196)): c.create_text(hx, hy, text="♥", font=("Arial", 9, "bold"), fill="white", **o)
        elif n == "청치마":  # 파란 데님 치마 + 허리띠 + 박음질
            c.create_polygon(62, 184, 178, 184, 188, 216, 52, 216, fill="#3b64a8", outline=OUTL, width=2, **o)
            c.create_rectangle(62, 184, 178, 192, fill="#2c4f8a", outline=OUTL, **o)
            c.create_line(54, 212, 186, 212, fill="#8fb0e0", dash=(4, 3), **o)
        elif n == "체크 치마":  # 빨강 체크무늬 주름치마
            c.create_polygon(62, 184, 178, 184, 188, 216, 52, 216, fill="#c0392b", outline=OUTL, width=2, **o)
            for y in (194, 204, 214): c.create_line(52 - (y - 218) // 3 * 0, y, 188, y, fill="#7a1f16", **o)
            for x in range(66, 180, 14): c.create_line(x, 186, 120 + (x - 120) * 1.35, 217, fill="#e87a6e", **o)
            c.create_rectangle(62, 184, 178, 191, fill="#7a1f16", outline=OUTL, **o)
        elif n in ("빨간 목도리", "하늘 목도리"):  # 목에 두른 띠 + 앞으로 늘어진 꼬리 + 줄무늬
            c1, c2 = ("#d83a3a", "#f5c0c0") if n[0] == "빨" else ("#4aa8e0", "#d6efff")
            rrect(50, 158, 190, 180, r=10, fill=c1, outline=OUTL, width=2, **o)
            for x in range(60, 186, 14): c.create_line(x, 160, x, 178, fill=c2, width=3, **o)
            if front:
                c.create_polygon(138, 174, 162, 174, 164, 214, 142, 214, fill=c1, outline=OUTL, width=2, **o)
                c.create_line(142, 198, 163, 198, fill=c2, width=3, **o); c.create_line(141, 206, 164, 206, fill=c2, width=3, **o)
        elif n == "운동화":  # 흰 운동화 + 빨간 줄
            for (x0, y0, x1, y1) in legs:
                rrect(x0 - 4, y1 - 9, x1 + 4, y1 + 3, r=5, fill="white", outline=OUTL, width=2, **o)
                c.create_line(x0 - 2, y1 - 3, x1 + 2, y1 - 3, fill="#e23b3b", width=2, **o)
        elif n == "장화":  # 노란 장화
            for (x0, y0, x1, y1) in legs: rrect(x0 - 3, y1 - 20, x1 + 3, y1 + 3, r=5, fill="#f2c230", outline=OUTL, width=2, **o)
        elif n == "선글라스" and front:  # 번쩍이는 렌즈 + 다리
            c.create_line(84, 122, 62, 118, fill="#222", width=3, **o); c.create_line(156, 122, 178, 118, fill="#222", width=3, **o)
            c.create_oval(82, 112, 108, 138, fill="#1a1a1a", outline="#555", width=2, **o)
            c.create_oval(132, 112, 158, 138, fill="#1a1a1a", outline="#555", width=2, **o)
            c.create_arc(106, 114, 134, 130, start=0, extent=180, style="arc", width=3, outline="#222", **o)
            for gx in (89, 139): c.create_line(gx, 118, gx + 6, 114, fill="white", width=2, **o)

brow = 0
def draw(m, gift=None, f=0):
    if m == "plank": return draw_plank(f)
    global mood; mood = m
    c.delete("body")
    o = dict(tags="body")
    arm = (178, 122, 226, 142) if gift else (178, 148, 200, 178)  # 선물 줄 땐 팔을 쭉 뻗음
    if m == "poop":  # 변기 (황금 변기가 있으면 황금색): 어깨 뒤의 물탱크 + 엉덩이 밑의 변좌와 받침
        gold = "황금 변기" in save["inv"]; tc, to = ("#f5c518", "#a87b00") if gold else ("#ffffff", "#8a8a8a")
        c.create_rectangle(52, 58, 188, 70, fill=tc, outline=to, width=2, **o); rrect(58, 66, 182, 104, r=6, fill=tc, outline=to, width=2, **o); c.create_oval(112, 76, 128, 92, fill="#d8d8d8", outline=to, **o)
        c.create_polygon(84, 226, 156, 226, 150, 248, 90, 248, fill=tc, outline=to, width=2, **o); c.create_oval(54, 196, 186, 230, fill=tc, outline=to, width=2, **o)
    lm = limbs(m, f, arm); sit_legs = [(62, 205, 112, 222), (128, 205, 178, 222)]
    for box in lm:
        rrect(*box, r=10, fill=ORANGE, outline=OUTL, width=2, **o)
    rrect(60, 90, 180, 205, r=24, fill=ORANGE, outline=OUTL, width=2, **o)
    if m == "sit":  # 앉기: 다리를 앞으로 뻗음
        c.delete("body"); o = dict(tags="body")
        for box in [(40, 148, 62, 178), (178, 148, 200, 178), (62, 205, 112, 222), (128, 205, 178, 222)]:
            rrect(*box, r=10, fill=ORANGE, outline=OUTL, width=2, **o)
        rrect(60, 90, 180, 205, r=24, fill=ORANGE, outline=OUTL, width=2, **o)
    front = m not in ("sorry", "hit", "climb")
    if not front:  # 뒤돌아서 엉덩이를 내밀기 (얼굴 없음)
        if m != "climb":  # 사다리 오를 땐 뒷모습만 (엉덩이 볼터치 없음)
            c.create_oval(66, 140, 120, 205, fill="#f4a7a0", outline=OUTL, width=2, **o)
            c.create_oval(120, 140, 174, 205, fill="#f4a7a0", outline=OUTL, width=2, **o)
        if m == "hit":
            anger(120, 172, o)
    else:
        for ex in (95, 145):
            if m == "struggle" or (m in ("poop", "gym") and 0.6 < f < 2):  # > <  (힘주는 얼굴)
                k = 1 if ex < 120 else -1
                c.create_line(ex-8*k, 114, ex+8*k, 125, ex-8*k, 136, width=3, fill=DARK, **o)
            elif m in ("happy", "shower") or (m == "poop" and f >= 2):  # ^ ^
                c.create_arc(ex-9, 118, ex+9, 142, start=0, extent=180, style="arc", width=3, outline=OUTL, **o)
            elif m == "doze":  # 감은 눈
                c.create_arc(ex-9, 118, ex+9, 140, start=180, extent=180, style="arc", width=3, outline=OUTL, **o)
            elif m in ("read", "game"):  # 아래를 봄
                c.create_oval(ex-5, 126, ex+5, 141, fill=DARK, **o)
            else:  # 기본 눈: 까만 눈 바깥쪽 가장자리에 한 입 베어문 듯한 홈
                c.create_oval(ex-9, 114, ex+9, 142, fill=DARK, **o)
                ex > 120 and c.create_oval(ex + 6, 124, ex + 12, 130, fill=ORANGE, outline=ORANGE, **o)  # 둥글게 한 입 베어문 홈
        if m in ("read", "game", "gym", "brush", "run", "rope", "jack", "work") or (m == "poop" and 0.6 < f < 2):  # 집중한 눈썹: 안쪽이 낮은 대각선 \ /
            by_ = -9 if (m == "read" and brow) else 0  # 흥미로울 땐 눈썹이 들썩
            c.create_line(82, 106 + by_, 108, 116 + by_, width=4, fill=DARK, capstyle="round", **o); c.create_line(158, 106 + by_, 132, 116 + by_, width=4, fill=DARK, capstyle="round", **o)
        if (m == "eat" and f > 0.7) or (m == "munch" and f): c.create_oval(113, 146, 127, 158, fill="#7a2e2e", outline=OUTL, **o)  # 우물우물
        if m == "whistle":  # 휘파람 입
            c.create_oval(113, 146, 127, 160, fill=DARK, **o)
    if m == "struggle":  # 머리 꼬집힘: 머리 위가 쭉 늘어남 + 벌린 입
        c.create_polygon(100, 92, 120, 62, 140, 92, fill=ORANGE, outline=OUTL, width=2, **o)
        c.create_line(101, 91, 139, 91, fill=ORANGE, width=3, **o)
        c.create_oval(110, 144, 130, 164, fill="#7a2e2e", outline=OUTL, **o)
        anger(152, 74, o)
    if m == "farm":  # 괭이질
        y = 25 * f
        c.create_line(205, 108 + y, 232, 160 + y, width=4, fill="#8b5a2b", **o)
        c.create_polygon(226, 156 + y, 246, 160 + y, 238, 172 + y, fill="#b0b0b0", outline=OUTL, **o)
    wear(o, front, [lm[0], lm[1]] if m != "sit" else [(40, 148, 62, 178), (178, 148, 200, 178)], sit_legs if m == "sit" else [lm[2], lm[3]])
    if time.time() < save.get("skin_until", 0):  # 피부과 다녀온 뒤: 반질반질 광택 (모든 옷·소품보다 위에 그림)
        for (x0, y0, x1, y1, st_) in ((64, 92, 104, 132, 100), (150, 156, 176, 196, 280)): c.create_arc(x0, y0, x1, y1, start=st_, extent=50, style="arc", outline="white", width=3, **o)  # 얇은 하이라이트 선
        for (sx, sy, sz) in ((182, 96, 14), (56, 108, 11), (178, 170, 11), (66, 176, 9)): c.create_text(sx, sy, text="✦", font=("Arial", sz, "bold"), fill="#ffd34d", **o)
    if m == "shower":  # 샤워기 + 떨어지는 물 + 머리 위 거품
        c.create_line(120, -30, 120, 8, width=6, fill="#9aa5b1", **o)
        c.create_polygon(94, 10, 146, 10, 138, 30, 102, 30, fill="#b8c2cc", outline=OUTL, width=2, **o)
        for i, x in enumerate(range(100, 142, 8)):
            for yy in range(34 + 7 * (i % 3), 205, 38): c.create_line(x, yy + 38 * f, x - 1, yy + 38 * f + 18, fill="#5ab4f0", width=2, **o)
        for (bx, by, br) in ((92, 90, 10), (110, 82, 12), (130, 84, 11), (148, 92, 9), (120, 92, 10)): c.create_oval(bx - br, by - br, bx + br, by + br, fill="white", outline="#bcd0e0", **o)
        for (bx, by) in ((70, 120 - 6 * f), (172, 150 + 6 * f), (64, 180 - 4 * f)): c.create_oval(bx - 5, by - 5, bx + 5, by + 5, outline="#5ab4f0", **o)
    elif m == "brush":  # 칫솔질: 입 주위 거품 + 칫솔이 좌우로
        for (bx, by, br) in ((112, 154, 8), (125, 158, 7), (136, 152, 6), (120, 165, 5)): c.create_oval(bx - br, by - br, bx + br, by + br, fill="white", outline="#bcd0e0", **o)
        c.create_line(196, 150, 138 + 8 * f, 154, width=5, fill="#4a86c8", **o); c.create_rectangle(126 + 8 * f, 150, 140 + 8 * f, 158, fill="white", outline="#4a86c8", **o)
    elif m == "poop":  # 힘주기 / 시원 (똥 한 덩이가 옆에 떨어짐) / 물 내리기. 변기 본체는 draw 앞부분에서 펫 뒤에 그림
        if 0.6 < f < 2: sweat(158, 84, o)
        if f == 2:
            for (px_, py_, rx, ry) in ((208, 236, 15, 6), (208, 230, 11, 5), (208, 225, 6, 4)): c.create_oval(px_ - rx, py_ - ry, px_ + rx, py_ + ry, fill="#8b5a2b", outline="#4a2f18", **o)
        if f == 3:
            for sx, sy in ((46, 214), (194, 214)): c.create_arc(sx - 12, sy, sx + 12, sy + 20, start=200, extent=240, style="arc", outline="#5ab4f0", width=2, **o)
            for sx in (52, 188): c.create_line(sx, 232, sx + (-6 if sx < 120 else 6), 244, fill="#5ab4f0", width=2, **o)
    elif m == "jack":
        c.move("body", 0, -16 * f)
        if f > 0.5: sweat(160, 70, o)
    elif m == "rope":  # 줄넘기: 줄이 빙글빙글 돌고 줄이 발 밑을 지날 때 점프
        c.create_arc(40, 20, 200, 250, start=360 * f, extent=150, style="arc", outline="#a0642a", width=3, **o)
        c.move("body", 0, -18 * math.sin(math.pi * f))
    elif m == "run":  # 달리기: 속도선 + 땀
        for y in (120, 150, 180): c.create_line(4, y, 36 + 6 * f, y, fill="#aab", width=2, **o)
        sweat(176, 74, o)
    elif m == "coffee":  # 커피 한 잔 (f가 커질수록 입으로 가져가서 홀짝)
        y0 = 176 - 22 * f
        for k in range(3): c.create_line(104 + 10 * k, y0 - 6, 100 + 10 * k + 4 * f, y0 - 14, 106 + 10 * k, y0 - 22, fill="#c8c8c8", width=2, smooth=True, **o)
        rrect(92, y0, 134, y0 + 32, r=6, fill="#ffffff", outline=OUTL, width=2, **o); c.create_rectangle(96, y0 + 4, 130, y0 + 10, fill="#6b3f1d", **o)
        c.create_arc(126, y0 + 6, 148, y0 + 26, start=270, extent=180, style="arc", outline=OUTL, width=3, **o)
        for hx in (80, 138): rrect(hx, y0 + 8, hx + 16, y0 + 28, r=7, fill=ORANGE, outline=OUTL, width=2, **o)
    elif m == "eat":  # 밥그릇과 숟가락 (f가 커질수록 숟가락이 입으로)
        c.create_polygon(82, 178, 158, 178, 150, 212, 90, 212, fill="#ffffff", outline=OUTL, width=2, **o)
        c.create_oval(84, 170, 156, 186, fill="#fffdf2", outline=OUTL, width=2, **o); c.create_oval(96, 160, 144, 180, fill="#ffffff", outline="#ccc", **o)
        for gx in (104, 118, 130): c.create_oval(gx, 166, gx + 4, 170, fill="#e8e0c8", **o)
        c.create_line(190, 176 - 24 * f, 134, 172 - 20 * f, width=4, fill="#b0b0b0", **o); c.create_oval(126, 167 - 20 * f, 138, 177 - 20 * f, fill="#c8c8c8", outline=OUTL, **o)
        if f > 0.5: c.create_oval(124, 166 - 20 * f, 130, 172 - 20 * f, fill="white", **o)
    elif m == "gym":  # 운동: 머리띠 + 덤벨. 위로 갈수록 힘들어서 바들바들 떨림
        c.create_rectangle(62, 98, 178, 106, fill="#e23b3b", outline=OUTL, **o); c.create_polygon(178, 98, 192, 92, 190, 108, 178, 106, fill="#e23b3b", outline=OUTL, **o)
        by = round(140 - 85 * f) + 8
        c.create_line(56, by, 184, by, width=6, fill="#555", **o)
        for dx in (42, 184): c.create_rectangle(dx, by - 14, dx + 14, by + 14, fill="#333", outline=OUTL, **o)
        for hx in (50, 168): rrect(hx, by - 9, hx + 22, by + 9, r=7, fill=ORANGE, outline=OUTL, width=2, **o)
        if f > 0.6: sweat(160, 74, o)
        if f > 0.8: k_ = (f - 0.8) / 0.2; c.move("body", random.uniform(-3.5, 3.5) * k_, random.uniform(-2, 2) * k_)  # 바들바들
    elif m == "doze":  # Zzz가 떠오름 + 고개를 꾸벅
        for k, (zx, zy, sz) in enumerate(((172, 96, 12), (190, 74, 16), (210, 48, 20))):
            c.create_text(zx + 6 * f, zy - 5 * f * (k + 1) / 2, text="Z", font=("Arial", sz, "bold"), fill="#4a7bd8", **o)
        c.move("body", 0, 3 * f)
    elif m == "read":  # 책을 펫 쪽으로 펼쳐 듦: 관객에게는 표지(뒷면)가 보임. f=1이면 책장이 넘어감
        c.create_polygon(72, 176, 120, 184, 120, 214, 72, 206, fill="#3a6fb5", outline=OUTL, width=2, **o)
        c.create_polygon(168, 176, 120, 184, 120, 214, 168, 206, fill="#3a6fb5", outline=OUTL, width=2, **o)
        c.create_line(120, 184, 120, 214, width=3, fill=DARK, **o); c.create_rectangle(132, 190, 156, 196, fill="#f2d98a", outline="", **o)
        c.create_polygon(76, 174, 120, 182, 164, 174, 164, 178, 120, 186, 76, 178, fill="#fffdf2", outline=OUTL, **o)  # 윗면의 책장 단면
        if f > 0.04: c.create_polygon(120, 182, 120 + 38 * f, 172 - 6 * f, 120 + 38 * f, 176 - 6 * f, 120, 186, fill="#f3ecd2", outline=OUTL, **o)
    elif m == "work":  # 노트북 작업: 화면은 펫 쪽, 우리에겐 덮개 뒷면. f가 번갈아 키보드를 두드림
        rrect(68, 150, 172, 198, r=8, fill="#b9bfc8", outline=OUTL, width=2, **o); c.create_oval(112, 166, 128, 182, fill="#dfe3e8", outline="#8a909a", **o)
        c.create_polygon(54, 200, 186, 200, 196, 214, 44, 214, fill="#9aa0aa", outline=OUTL, width=2, **o)
        c.create_oval(116, 170, 124, 178, fill="#ffd34d" if f else "#dfe3e8", outline="", **o)  # 손 대신 로고 불빛이 깜빡이며 타자 중 표시
    elif m == "game":  # 휴대용 게임기 (화면이 깜빡이고 버튼을 누름)
        rrect(72, 168, 168, 202, r=10, fill="#2b2f4a", outline=OUTL, width=2, **o)
        c.create_rectangle(96, 173, 144, 197, fill="#8af0b0" if f else "#c8ffd8", outline=OUTL, **o)
        c.create_rectangle(104 + 10 * f, 180, 112 + 10 * f, 188, fill="#2b2f4a", **o); c.create_rectangle(128, 186, 136, 192, fill="#d83a3a", **o)
        c.create_rectangle(80, 184, 90, 188, fill="#ddd", **o); c.create_rectangle(83, 181, 87, 191, fill="#ddd", **o)
        c.create_oval(150, 182 + 2 * f, 158, 190 + 2 * f, fill="#e8506a", **o); c.create_oval(156, 178, 164, 186, fill="#f2c230", **o)
    if gift:
        if gift.strip(): icon(gift, 236, 132, o)
    if m == "sit": c.move("body", 0, 10)
    finish()

def finish():  # 축소 + 말랑 변형 적용, 친밀도 표시
    c.scale("body", 120, 235, S, S)
    c.scale("body", 120, 235, sq[0], sq[1])
    c.delete("aff"); c.create_text(120, 272, text=f"♥ {save['aff']}/{MAX_AFF}", fill="#ff5d8f",
                                   font=("Malgun Gothic", 12, "bold"), tags="aff")

def draw_plank(f):  # 엎드려 뻗쳐: 옆모습으로 팔굽혀펴기 (f=1이면 몸이 내려감)
    global mood; mood = "plank"
    c.delete("body"); o = dict(tags="body"); d = 16 * f
    for box in [(60, 200 + d, 82, 232), (146, 200 + d, 168, 232)]:  # 뒷다리, 앞팔
        rrect(*box, r=10, fill=ORANGE, outline=OUTL, width=2, **o)
    rrect(50, 160 + d, 180, 202 + d, r=18, fill=ORANGE, outline=OUTL, width=2, **o)
    c.create_line(150, 172 + d, 162, 180 + d, 150, 188 + d, width=3, fill=DARK, **o)  # > 힘든 눈
    sweat(192, 150 + d, o)
    finish()

sayn = 0
def speak(msg, ms=5000):  # 말하고 잠시 뒤 말풍선 지움 (그 사이 다른 말이 나왔으면 건드리지 않음)
    say(msg); n = sayn; root.after(ms, lambda: sayn == n and c.delete("bub"))

def say(msg, ms=7000):  # 말풍선은 읽을 만큼만 떠 있다가 사라짐 (더 오래 둘 땐 show의 keep/speak)
    _say(msg); n = sayn; root.after(ms, lambda: sayn == n and mood not in ("sorry", "hit") and c.delete("bub"))

def _say(msg):  # 머리 바로 위에 꼬리 달린 둥근 말풍선
    global sayn; sayn += 1
    msg = re.sub(r"[\U00010000-\U0010ffff\ufe0f]", "", msg).strip()  # 이모지는 깨져서 뺌
    c.delete("bub")
    if mood == "shower":  # 샤워기·물줄기가 머리 위를 덮으니 말풍선은 옆(오른쪽)에
        t = c.create_text(188, 130, anchor="w", text=msg, width=130, font=("Malgun Gothic", 10), tags="bub")
        x0, y0, x1, y1 = c.bbox(t); x0, y0, x1, y1 = x0 - 9, y0 - 6, x1 + 9, y1 + 6; cy_ = (y0 + y1) // 2
        c.create_polygon(x0 - 12, cy_, x0 + 2, cy_ - 7, x0 + 2, cy_ + 7, fill="white", outline="", tags="bub"); c.create_line(x0 + 1, cy_ - 7, x0 - 12, cy_, x0 + 1, cy_ + 7, fill="#888", tags="bub")
        bg = c.create_polygon(x0 + 10, y0, x1 - 10, y0, x1, y0, x1, y0 + 10, x1, y1 - 10, x1, y1, x1 - 10, y1, x0 + 10, y1, x0, y1, x0, y1 - 10, x0, y0 + 10, x0, y0, smooth=True, fill="white", outline="#888", tags="bub")
        c.tag_lower(bg, t); c.tag_raise(t); return
    t = c.create_text(120, 100, anchor="s", text=msg, width=190, font=("Malgun Gothic", 10), tags="bub")
    x0, y0, x1, y1 = c.bbox(t); x0, y0, x1, y1 = x0-9, y0-6, x1+9, y1+6; r = 10
    c.create_polygon(112, y1-1, 128, y1-1, 120, y1+13, fill="white", outline="", tags="bub")
    c.create_line(112, y1, 120, y1+13, 128, y1, fill="#888", tags="bub")
    bg = c.create_polygon(x0+r, y0, x1-r, y0, x1, y0, x1, y0+r, x1, y1-r, x1, y1, x1-r, y1, x0+r, y1, x0, y1,
                          x0, y1-r, x0, y0+r, x0, y0, smooth=True, fill="white", outline="#888", tags="bub")
    c.create_line(113, y1, 127, y1, fill="white", width=2, tags="bub")
    c.tag_lower(bg, t)
    c.tag_raise(t)

def show(msg, m, gift=None, keep=0):
    global hide_id
    draw(m, gift); say(msg)
    if hide_id: root.after_cancel(hide_id)
    hide_id = root.after(keep or (60000 if m in ("sorry", "hit") else 9000), hide)

def pose():  # 사용자가 시킨 자세 (없으면 평상시)
    return {"sit": "sit", "plank": "plank"}.get(mode, "normal")

def hide():  # 숨지 않고 현재 자세로 복귀, 말풍선 지움
    draw(pose()); c.delete("bub")

def hearts(sym="♥", color="#ff5d8f"):
    for _ in range(4):
        x = random.randint(70, 170)
        h = c.create_text(x, 90, text=sym, fill=color, font=("Malgun Gothic", 16), tags="heart")
        def rise(h=h, n=0):
            if n > 20: c.delete(h); return
            c.move(h, 0, -4); root.after(40, rise, h, n+1)
        root.after(random.randint(0, 300), rise)

def conv(e):  # 축소 전 좌표로 환산
    return 120 + (e.x - 120) / S, 235 + (e.y - 235) / S

IMGQ = queue.Queue()
UA = {"User-Agent": "ClaudePetToy/1.0"}
RB, RB_LOCK = [], threading.Lock()
def rembg_ready():  # AI 누끼 모델은 처음 한 번만 불러옴 (없으면 False)
    with RB_LOCK:
        if not RB:
            try:
                from rembg import remove, new_session
                RB.extend([remove, new_session("u2net")])
            except Exception:
                RB.extend([None, None])
    return RB[0] is not None
threading.Thread(target=rembg_ready, daemon=True).start()  # 시작할 때 미리 불러둠

def cutout(im, size=150, thresh=45):  # 물건만 오려내기. rembg가 있으면 깔끔, 없으면 흰 배경만 지움
    if Image and rembg_ready():
        im = RB[0](im, session=RB[1]).convert("RGBA")
        a = im.getchannel("A").point(lambda v: 255 if v > 128 else 0); im.putalpha(a)  # 투명색 창이라 반투명 금지
        bb = a.getbbox()
        if bb: im = im.crop(bb)
    else:
        im = im.convert("RGBA")
        if im.getchannel("A").getextrema()[0] == 255:
            for xy in ((0, 0), (im.width - 1, 0), (0, im.height - 1), (im.width - 1, im.height - 1)):
                ImageDraw.floodfill(im, xy, (255, 0, 255, 0), thresh=thresh)
        im.putalpha(im.getchannel("A").point(lambda v: 255 if v > 128 else 0))
    im.thumbnail((size, size)); return im

def fetch_gift(name, q, size=150, ok=None, ex="", shape=None, limit=12):
    def run():
        try:
            u = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(dict(
                action="query", generator="search", gsrnamespace=6, gsrsearch=q + ex + " filetype:bitmap", gsrlimit=limit,
                prop="imageinfo", iiprop="url|mime", iiurlwidth=400, format="json"))
            pages = list(json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=15))["query"]["pages"].values())
            random.shuffle(pages)
            for p in pages:
                ii = p["imageinfo"][0]
                if ii["mime"] in ("image/jpeg", "image/png", "image/gif", "image/webp"):
                    b = urllib.request.urlopen(urllib.request.Request(ii["thumburl"], headers=UA), timeout=15).read()
                    im = Image.open(io.BytesIO(b))
                    if ok and not ok(im): continue  # 예: 사다리는 세로로 긴 사진만
                    cut = cutout(im, size)
                    if shape and not (shape[0] <= cut.width / cut.height <= shape[1]): continue  # 엉뚱한 모양 제외
                    IMGQ.put((name, cut)); return
        except Exception:
            pass
        IMGQ.put((name, None))  # 실패하면 그린 그림/상자로
    threading.Thread(target=run, daemon=True).start()

gift_ph = []  # PhotoImage는 참조를 들고 있어야 안 사라짐
def curtain(mid, end, t=0, phase=0):  # 탈의실 커튼: 닫힘 → (그 사이 옷 갈아입음) → 열림
    n = 8; c.delete("curtain")
    w = 75 * (t / n if phase == 0 else 1 - t / n)
    c.create_line(40, 105, 200, 105, width=4, fill="#6b4a2f", tags="curtain")  # 커튼봉
    if w > 0:
        for x0, x1, sgn in ((45, 45 + w, 1), (195 - w, 195, -1)):
            c.create_rectangle(x0, 108, x1, 245, fill="#8e5bd4", outline="#5b3a99", width=2, tags="curtain")
            for i in range(1, int(w // 15) + 1):  # 주름
                x = (x0 if sgn == 1 else x1) + sgn * 15 * i
                c.create_line(x, 110, x, 243, fill="#6f44b3", tags="curtain")
    c.tag_raise("curtain")
    if t < n: root.after(45, curtain, mid, end, t + 1, phase); return
    if phase == 0: mid(); c.tag_raise("curtain"); root.after(900, curtain, mid, end, 0, 1); return
    c.delete("curtain"); end()

def give(item, outfit, img=None):  # 선물/옷을 내밀고 3.5초 뒤 건네줌. 옷은 커튼 치고 갈아입음
    if outfit and img is not None: img.save(os.path.join(OUTFIT_DIR, item + ".png")); worn_ph.pop(item, None)
    shown = None
    if img: shown = img.copy(); shown.thumbnail((150, 150))
    place = random.choice(PLACES)
    show(f"친밀도 {save['aff']}! {place} 이거 주웠어요. 받아주세요! → {item}", "happy", " " if shown else ("👕" if outfit else "🎁"))
    if shown:  # 몸보다 큰 물건을 손 옆에 내밀어 보여줌
        gift_ph[:] = [ImageTk.PhotoImage(shown)]; c.create_image(268, 188, image=gift_ph[0], tags="giftimg")
    def swap():
        if item not in save["owned"]: save["owned"].append(item)
        wear_on(item)
        draw("happy"); flush()
    def done():
        c.delete("giftimg")
        if outfit:
            say("잠깐만요, 갈아입고 올게요! (탈의실)")
            curtain(swap, lambda: say(f"짜잔~ {item} 입어봤어요! 어때요?"))
        else:
            save["inv"][item] = save["inv"].get(item, 0) + 1
            if img is not None and Image: t_ = img.copy(); t_.thumbnail((72, 72)); t_.save(os.path.join(GIFT_DIR, item + ".png"))
            draw("happy"); say(f"{item}, 잘 간직해 주세요!"); flush()
    root.after(3500, done)

DRAWN = {"황금 변기", "금괴", "황금 목걸이", "우승 트로피", "지렁이", "초대형 오리 인형", "삽", "공룡 화석"}  # 사진 검색이 잘 안 맞아서 그림으로
FOOD = {"꿀사과", "감자", "마른 멸치", "도넛", "컵라면", "후라이드 치킨", "피자 한 판", "고구마"}  # 눌러서 먹을 수 있는 선물
USE = {"황금 변기": "황금 변기 설치 완료! 오늘부터 여기가 제 왕좌예요", "다이아몬드": "반짝반짝! 눈부셔요", "금괴": "묵직하다… 부자 된 기분!", "우승 트로피": "제가 1등이에요!",
       "지렁이": "꿈틀꿈틀… 낚시하러 가야겠다", "삽": "이걸로 농사지어야지!", "공룡 화석": "크아앙! 공룡 뼈다!", "초대형 오리 인형": "꽥꽥! 목욕 시간이다", "두루마리 휴지": "휴지 풀기 놀이~",
       "황금 목걸이": "어때요? 잘 어울려요?"}
def item_art(n, px=64):  # 선물 그림 (직접 그림)
    K = 4; im = Image.new("RGBA", (64 * K, 64 * K), (0, 0, 0, 0)); d = ImageDraw.Draw(im); O = "#3a2a1a"
    def E(x0, y0, x1, y1, **kw): d.ellipse([x0 * K, y0 * K, x1 * K, y1 * K], **kw)
    def R(x0, y0, x1, y1, **kw): d.rectangle([x0 * K, y0 * K, x1 * K, y1 * K], **kw)
    def PG(pts, **kw): d.polygon([(x * K, y * K) for x, y in pts], **kw)
    def L(pts, w=2, **kw): d.line([(x * K, y * K) for x, y in pts], width=int(w * K), **kw)
    G, GD = "#f5c518", "#a87b00"
    if n == "황금 변기":
        R(16, 6, 48, 24, fill=G, outline=GD, width=K); E(10, 24, 54, 46, fill=G, outline=GD, width=K); E(16, 27, 48, 41, fill="#fff3a8", outline=GD, width=K // 2)
        PG([(22, 44), (42, 44), (44, 58), (20, 58)], fill=G, outline=GD, width=K); R(42, 9, 46, 13, fill="#fff3a8")
    elif n == "다이아몬드":
        PG([(12, 24), (22, 10), (42, 10), (52, 24), (32, 56)], fill="#6fd3f5", outline="#1b6f93", width=K)
        L([(12, 24), (52, 24)], 1.5, fill="#1b6f93"); L([(22, 10), (28, 24), (32, 56)], 1.2, fill="#1b6f93"); L([(42, 10), (36, 24), (32, 56)], 1.2, fill="#1b6f93"); PG([(24, 12), (30, 12), (28, 22), (20, 22)], fill="#d8f6ff")
    elif n == "마른 멸치":
        PG([(52, 32), (62, 22), (62, 42)], fill="#bda46a", outline=O, width=K // 2); E(4, 24, 54, 41, fill="#cdb67f", outline=O, width=K // 2)
        E(10, 29, 15, 34, fill="#222"); L([(20, 28), (44, 30)], 1, fill="#9c8450"); L([(20, 36), (44, 35)], 1, fill="#9c8450")
    elif n == "금괴":
        PG([(14, 28), (48, 28), (58, 40), (4, 40)], fill="#ffe27a", outline=GD, width=K); R(4, 40, 58, 52, fill=G, outline=GD, width=K); L([(10, 46), (52, 46)], 1.2, fill="#fff3a8")
    elif n == "황금 목걸이":
        d.arc([10 * K, 6 * K, 54 * K, 50 * K], 20, 160, fill=G, width=3 * K); d.arc([10 * K, 6 * K, 54 * K, 50 * K], 160, 380, fill=G, width=3 * K)
        E(26, 44, 38, 58, fill="#ff4d79", outline=GD, width=K)
    elif n == "우승 트로피":
        PG([(16, 8), (48, 8), (44, 30), (32, 38), (20, 30)], fill=G, outline=GD, width=K); d.arc([4 * K, 10 * K, 22 * K, 28 * K], 90, 270, fill=GD, width=2 * K); d.arc([42 * K, 10 * K, 60 * K, 28 * K], 270, 450, fill=GD, width=2 * K)
        R(29, 38, 35, 48, fill=G, outline=GD, width=K // 2); R(20, 48, 44, 56, fill="#8a5a2b", outline=O, width=K // 2)
    elif n == "지렁이":
        pts = [(6 + i * 4, 32 + 8 * (1 if i % 2 else -1)) for i in range(15)]; L(pts, 6, fill="#d98b8b", joint="curve"); E(5, 24, 11, 30, fill="#b86a6a")
    elif n == "초대형 오리 인형":
        E(8, 26, 50, 56, fill="#ffe14d", outline=O, width=K); E(28, 6, 54, 32, fill="#ffe14d", outline=O, width=K); PG([(52, 18), (62, 22), (52, 26)], fill="#ff9a1f", outline=O, width=K // 2); E(40, 14, 45, 19, fill="#222")
    elif n == "삽":
        L([(40, 4), (26, 36)], 4, fill="#8b5a2b"); PG([(18, 34), (36, 34), (38, 58), (27, 62), (16, 58)], fill="#b8bcc4", outline=O, width=K); L([(36, 6), (46, 12)], 4, fill="#8b5a2b")
    elif n == "두루마리 휴지":
        R(14, 14, 50, 52, fill="#ffffff", outline=O, width=K); E(14, 8, 50, 22, fill="#f4f4f4", outline=O, width=K); E(26, 12, 38, 18, fill="#bbb"); E(14, 46, 50, 58, fill="#ffffff", outline=O, width=K); R(15, 46, 49, 52, fill="#ffffff")
    elif n == "공룡 화석":
        E(4, 12, 60, 54, fill="#cdbb98", outline=O, width=K); L([(14, 34), (50, 34)], 3, fill="#fff8e6")
        for x in range(18, 48, 7): L([(x, 24), (x, 44)], 2, fill="#fff8e6")
        E(8, 28, 18, 40, fill="#fff8e6")
    return im.resize((px, px), Image.LANCZOS)
def gift_icon(n):  # 가방 칸용 그림 파일
    p = os.path.join(GIFT_DIR, "gi_" + n + ".png")
    if not os.path.exists(p) and Image: item_art(n, 64).save(p)
    return p

def eq_icon(n):  # 장비 아이콘: 직접 그린 그림 (64x64). 한 번 그리면 파일로 보관
    p = os.path.join(GIFT_DIR, "eq_" + n + ".png")
    if os.path.exists(p) or not Image: return p
    K = 4; im = Image.new("RGBA", (64 * K, 64 * K), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    def E(x0, y0, x1, y1, **kw): d.ellipse([x0 * K, y0 * K, x1 * K, y1 * K], **kw)
    def R(x0, y0, x1, y1, **kw): d.rectangle([x0 * K, y0 * K, x1 * K, y1 * K], **kw)
    def PG(pts, **kw): d.polygon([(x * K, y * K) for x, y in pts], **kw)
    def L(pts, w=2, **kw): d.line([(x * K, y * K) for x, y in pts], width=int(w * K), **kw)
    O = "#3a2a1a"
    if n == "밀짚모자":
        E(4, 38, 60, 54, fill="#e8c874", outline=O, width=K); d.chord([16 * K, 10 * K, 48 * K, 46 * K], 180, 360, fill="#f0d58a", outline=O, width=K)
        R(17, 36, 47, 42, fill="#c0392b")
    elif n == "중절모":
        E(6, 40, 58, 54, fill="#55555f", outline=O, width=K)
        PG([(16, 44), (16, 22), (24, 15), (32, 22), (40, 15), (48, 22), (48, 44)], fill="#6b6b78", outline=O, width=K); R(16, 34, 48, 42, fill="#222")
    elif n == "티아라":
        PG([(10, 46), (13, 26), (22, 36), (32, 16), (42, 36), (51, 26), (54, 46)], fill="#e8e8f0", outline=O, width=K); R(10, 44, 54, 52, fill="#cfcfe0", outline=O, width=K)
        E(28, 22, 36, 30, fill="#ff5d8f", outline=O, width=K // 2)
    elif n == "선글라스":
        E(6, 24, 30, 46, fill="#1a1a1a", outline="#555", width=K); E(34, 24, 58, 46, fill="#1a1a1a", outline="#555", width=K); L([(30, 30), (34, 30)], 3, fill="#222"); L([(6, 28), (2, 24)], 2, fill="#222"); L([(58, 28), (62, 24)], 2, fill="#222")
    elif n == "동그란 안경":
        E(6, 22, 30, 46, outline=O, width=int(2.5 * K)); E(34, 22, 58, 46, outline=O, width=int(2.5 * K)); L([(30, 32), (34, 32)], 2.5, fill=O); L([(6, 30), (1, 26)], 2, fill=O); L([(58, 30), (63, 26)], 2, fill=O)
    elif n in ("줄무늬 티셔츠", "빨간 후드"):
        pts = [(4, 18), (20, 8), (26, 12), (38, 12), (44, 8), (60, 18), (54, 32), (46, 28), (46, 58), (18, 58), (18, 28), (10, 32)]
        if n == "줄무늬 티셔츠":
            PG(pts, fill="#ffffff", outline=O, width=K)
            m = Image.new("L", im.size, 0); ImageDraw.Draw(m).polygon([(x * K, y * K) for x, y in pts], fill=255)
            st = Image.new("RGBA", im.size, (0, 0, 0, 0)); sd = ImageDraw.Draw(st)
            for y in range(10, 60, 10): sd.rectangle([0, y * K, 64 * K, (y + 5) * K], fill="#4a86c8")
            im.paste(st, (0, 0), Image.composite(st.getchannel("A"), Image.new("L", im.size, 0), m)); d = ImageDraw.Draw(im); PG(pts, outline=O, width=K)
        else:
            PG(pts, fill="#d83a3a", outline=O, width=K); E(22, 4, 42, 22, fill="#b82e2e", outline=O, width=K); R(22, 42, 42, 54, fill="#b82e2e", outline=O, width=K // 2)
            L([(28, 18), (28, 30)], 1.5, fill="white"); L([(36, 18), (36, 30)], 1.5, fill="white")
    elif n == "징 벨트":
        R(4, 24, 60, 38, fill="#1a1418", outline=O, width=K // 2)
        for x in range(8, 24, 7): E(x - 2, 29, x + 2, 33, fill="#d7dae2")
        for x in range(42, 58, 7): E(x - 2, 29, x + 2, 33, fill="#d7dae2")
        PG([(32, 14), (36, 26), (46, 26), (38, 33), (41, 44), (32, 38), (23, 44), (26, 33), (18, 26), (28, 26)], fill="#c9ccd6", outline=O, width=K // 2); E(28, 26, 36, 34, fill="#1a1418")
    elif n == "체크 손목밴드":
        for i in range(8): R(10 + i * 6, 22 + 8 * (i % 2), 16 + i * 6, 30 + 8 * (i % 2), fill="#1a1418" if i % 2 == 0 else "white")
        R(8, 22, 58, 38, outline=O, width=K // 2)
    elif n == "유치원 노란 모자":
        E(4, 34, 60, 48, fill="#f2c92e", outline=O, width=K); d.chord([10 * K, 6 * K, 54 * K, 44 * K], 180, 360, fill="#f7d94c"); d.arc([10 * K, 6 * K, 54 * K, 44 * K], 180, 360, fill=O, width=K)
        E(22, 22, 26, 28, fill=O); E(38, 22, 42, 28, fill=O); PG([(28, 30), (36, 30), (32, 36)], fill="#f0892b", outline=O)
    elif n == "하늘색 카라티":
        pts = [(4, 18), (20, 8), (26, 12), (38, 12), (44, 8), (60, 18), (54, 32), (46, 28), (46, 58), (18, 58), (18, 28), (10, 32)]
        PG(pts, fill="#8fd0f0", outline=O, width=K); PG([(24, 10), (32, 24), (28, 10)], fill="white", outline=O); PG([(40, 10), (32, 24), (36, 10)], fill="white", outline=O); L([(32, 24), (32, 44)], 1.3, fill="#5ba6cf")
    elif n == "유치원 반바지":
        d.rounded_rectangle([10 * K, 14 * K, 54 * K, 50 * K], 4 * K, fill="#2f4a86", outline=O, width=K); R(10, 14, 54, 21, fill="#243a6b"); L([(32, 21), (32, 50)], 1.5, fill="#1d2f58")
    elif n == "이모 앞머리":
        for sx in (2, 46): PG([(sx + 4, 22), (sx + 14, 34), (sx + 12, 58), (sx + 2, 48)], fill="#17121a")
        d.chord([6 * K, 2 * K, 58 * K, 44 * K], 180, 360, fill="#17121a"); PG([(8, 26), (10, 40), (16, 34), (22, 48), (30, 36), (38, 44), (44, 34), (50, 42), (54, 26)], fill="#17121a"); PG([(24, 28), (30, 28), (26, 46)], fill="#8a4fd0")
    elif n == "갸루 소라빵머리":
        for bx in (18, 46):
            E(bx - 12, 4, bx + 12, 28, fill="#f2d36b", outline=O, width=K); d.arc([(bx - 7) * K, 9 * K, (bx + 7) * K, 23 * K], 40, 290, fill="#c9a53a", width=K)
        d.rounded_rectangle([6 * K, 20 * K, 58 * K, 44 * K], 10 * K, fill="#f2d36b", outline=O, width=K)
        for bx, sx in ((18, -1), (46, 1)):
            kx, ky = bx + sx * 12, 10; PG([(kx, ky), (kx + 8, ky - 5), (kx + 8, ky + 5)], fill="#ff6fa8", outline=O, width=K // 2); PG([(kx, ky), (kx - 8, ky - 5), (kx - 8, ky + 5)], fill="#ff6fa8", outline=O, width=K // 2); E(kx - 2, ky - 2, kx + 2, ky + 2, fill="#ff3d86")
    elif n == "이모 스웨터":
        pts = [(4, 18), (20, 8), (26, 12), (38, 12), (44, 8), (60, 18), (54, 32), (46, 28), (46, 58), (18, 58), (18, 28), (10, 32)]
        PG(pts, fill="#1a1418", outline=O, width=K)
        for y in (32, 42, 52): R(18, y, 46, y + 3, fill="#7a3fb8")
        E(26, 20, 38, 31, fill="#f2eee8"); E(28, 23, 31, 27, fill="#1a1418"); E(33, 23, 36, 27, fill="#1a1418")
    elif n == "갸루 크롭탑":
        d.rounded_rectangle([6 * K, 16 * K, 58 * K, 44 * K], 8 * K, fill="#ff8fbf", outline=O, width=K); L([(16, 16), (20, 8)], 2.5, fill="white"); L([(48, 16), (44, 8)], 2.5, fill="white"); E(26, 22, 38, 34, fill="white")
    elif n == "이모 체인 치마":
        PG([(14, 14), (50, 14), (60, 52), (4, 52)], fill="#1a1418", outline=O, width=K)
        for y in (30, 42): L([(7, y), (57, y)], 1.5, fill="#7a3fb8")
        L([(14, 18), (26, 28), (36, 22), (52, 30)], 1.5, fill="#cfd2dc")
    elif n == "갸루 미니스커트":
        PG([(14, 14), (50, 14), (60, 44), (4, 44)], fill="#ff9ac6", outline=O, width=K); PG([(4, 44), (60, 44), (56, 54), (44, 48), (32, 54), (20, 48), (8, 54)], fill="white", outline=O, width=K)
        for hx in (18, 32, 46): E(hx - 3, 26, hx + 3, 32, fill="white")
    elif n == "청치마":
        PG([(14, 14), (50, 14), (60, 52), (4, 52)], fill="#3b64a8", outline=O, width=K); R(14, 14, 50, 21, fill="#2c4f8a", outline=O, width=K // 2); L([(8, 46), (56, 46)], 1.5, fill="#8fb0e0")
    elif n == "체크 치마":
        PG([(14, 14), (50, 14), (60, 52), (4, 52)], fill="#c0392b", outline=O, width=K)
        for y in (28, 38, 48): L([(7, y), (57, y)], 1.5, fill="#7a1f16")
        for x in range(10, 56, 9): L([(32 + (x - 32) * 0.5, 16), (x + (x - 32) * 0.1, 50)], 1.2, fill="#e87a6e")
        R(14, 14, 50, 20, fill="#7a1f16", outline=O, width=K // 2)
    elif n in ("빨간 목도리", "하늘 목도리"):
        c1, c2 = ("#d83a3a", "#f5c0c0") if n[0] == "빨" else ("#4aa8e0", "#d6efff")
        d.rounded_rectangle([6 * K, 14 * K, 58 * K, 32 * K], 8 * K, fill=c1, outline=O, width=K); PG([(40, 30), (56, 30), (58, 58), (42, 58)], fill=c1, outline=O, width=K)
        for x in range(12, 56, 10): L([(x, 16), (x, 30)], 2.5, fill=c2)
        L([(42, 46), (57, 46)], 2.5, fill=c2); L([(42, 53), (58, 53)], 2.5, fill=c2)
    elif n == "운동화":
        PG([(6, 22), (24, 22), (28, 34), (52, 38), (60, 46), (60, 52), (6, 52)], fill="white", outline=O, width=K); R(6, 48, 60, 54, fill="#cccccc", outline=O, width=K // 2); L([(14, 38), (44, 44)], 3, fill="#e23b3b")
    elif n == "장화":
        PG([(14, 6), (34, 6), (36, 40), (56, 46), (58, 56), (12, 56)], fill="#f2c230", outline=O, width=K); R(12, 52, 58, 58, fill="#c99a14", outline=O, width=K // 2)
    im.resize((64, 64), Image.LANCZOS).save(p); return p
icon_req = set()
def icon_path(n): return os.path.join(GIFT_DIR, n + ".png")
def want_icons():  # 선물 중 사진이 없는 것을 1.5초 간격으로 하나씩 받아옴 (검색 서버 제한 방지)
    if not Image: return
    todo = [(k, dict(GIFTS).get(k, k)) for k in save["inv"] if k not in DRAWN and not os.path.exists(icon_path(k)) and k not in icon_req]
    for i, (n, q) in enumerate(todo):
        icon_req.add(n); root.after(1500 * i, lambda n=n, q=q: fetch_gift("__icon__" + n, q, 110))
def gift_pil(k):  # 선물 그림 (PIL). 없으면 None
    p = gift_icon(k) if k in DRAWN else icon_path(k)
    if not (Image and os.path.exists(p)): return None
    im = Image.open(p).convert("RGBA"); im.thumbnail((110, 110)); return im

def use_gift(k):  # 선물 쓰기: 음식은 입으로 가져가 한 입씩 먹고, 나머지는 꺼내서 보여줌
    if drag or typing or k not in save["inv"]: return
    stopmove(); eat = k in FOOD; im = gift_pil(k); ph = []
    def put(x, y, sc=1.0):  # 선물 그림을 (x, y)에 sc 배율로
        c.delete("giftimg")
        if not im or sc <= 0.05: return
        ph[:] = [ImageTk.PhotoImage(im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.LANCZOS))]; c.create_image(x, y, image=ph[0], tags="giftimg")
    def finish():
        c.delete("giftimg")
        if eat:
            save["inv"][k] -= 1
            if save["inv"][k] <= 0: del save["inv"][k]
            flush(); say(f"{k} 잘 먹었습니다! 꺼억~"); hearts()
        else: say("다시 넣어둘게요~")
        draw("happy")
        if len(bagwin) > 1 and bagwin[0] and bagwin[0].winfo_exists(): bagwin[1]()
    if not eat:
        show(USE.get(k, f"{k}, 보세요! 소중히 간직할게요~"), "happy", " "); put(268, 188, 96 / max(im.size) if im else 1)
        root.after(3000, finish); return
    st = [(0, lambda: (draw("normal"), say(f"{k} 꺼냈어요! 냠냠 먹어볼까요~"), put(268, 188)))]
    for i in range(1, 11): st.append((45, lambda i=i: put(268 - 148 * i / 10, 188 - 22 * i / 10)))  # 입 앞으로 가져옴
    for n in range(4):  # 네 입에 나눠 먹음: 우물우물
        for ch in range(3): st.append((170, lambda n=n, ch=ch: (draw("munch", f=ch % 2), put(120, 166, 1 - 0.22 * n - 0.06 * ch * (ch == 2)), ch == 2 and n % 2 == 0 and say("냠냠… 맛있다!"))))
        st.append((120, lambda n=n: (put(120, 166, 1 - 0.25 * (n + 1)), hearts("♪", "#f0a030") if n == 1 else None)))
    st.append((300, lambda: None))
    sequence(st, finish)

def gift_menu(e, k):  # 선물 칸을 누르면 뜨는 메뉴: 사용 / 팔기 / 버리기
    if k not in save["inv"]: return
    n = save["inv"][k]; m = tk.Menu(t_bag(), tearoff=0, font=("Malgun Gothic", 10))
    m.add_command(label="🍴 먹기" if k in FOOD else "👀 꺼내 보기", command=lambda: use_gift(k))
    m.add_command(label=f"💰 1개 팔기 (+{price(k)})", command=lambda: sell(k, 1))
    if n > 1: m.add_command(label=f"💰 {n}개 모두 팔기 (+{price(k) * n})", command=lambda: sell(k, n))
    m.add_command(label="🗑 1개 버리기", command=lambda: sell(k, 1, trash=True))
    try: m.tk_popup(e.x_root, e.y_root)
    finally: m.grab_release()

def t_bag(): return bagwin[0]

def sell(k, n, trash=False):  # 선물 팔기(코인) / 버리기
    if k not in save["inv"]: return
    n = min(n, save["inv"][k]); save["inv"][k] -= n
    if save["inv"][k] <= 0: del save["inv"][k]
    if trash: say(f"{k} 버렸어요… 안녕 (ㅠㅠ)")
    else: save["coin"] += price(k) * n; say(f"{k} 팔아서 {price(k) * n}코인 벌었어요! (보유 {save['coin']})")
    flush()
    if len(bagwin) > 1 and bagwin[0] and bagwin[0].winfo_exists(): bagwin[1]()

# 펫이 번 돈으로 직접 쓰기: 옷 / 간식 / 피부과
away = [False]
def buy_outfit():
    left = [x for x in OUTFITS if x not in save["owned"]]
    if not left or save["coin"] < OUTFIT_COST: return False
    o = random.choice(left); save["coin"] -= OUTFIT_COST; save["owned"].append(o); flush(); global busy; busy = True
    def sw(): wear_on(o); draw(pose()); flush()
    sequence([(0, lambda: (draw("happy"), say(f"모아둔 돈으로 옷 사러 갈래요! ({OUTFIT_COST}코인)"))), (3000, lambda: curtain(sw, lambda: (say(f"{o} 샀어요! 어때요?"), hearts()))), (4000, lambda: None)], finish_act)
    return True

def buy_snack():
    if save["coin"] < SNACK_COST: return False
    k = random.choice(sorted(FOOD)); save["coin"] -= SNACK_COST; save["inv"][k] = save["inv"].get(k, 0) + 1; flush(); global busy; busy = True
    sequence([(0, lambda: (draw("happy"), say(f"간식 사 먹어야지~ {k} 샀어요! ({SNACK_COST}코인)"))), (2500, lambda: None)], lambda: (finish_act(), use_gift(k)))
    return True

def skin_clinic():  # 피부과: 화면 밖으로 다녀옴 → 반질반질 피부로 복귀
    if save["coin"] < SKIN_COST: return False
    save["coin"] -= SKIN_COST; flush(); global busy; busy = True; away[0] = True
    x0, y0 = root.winfo_x(), root.winfo_y(); st = [(0, lambda: (draw("normal"), say(f"피부과 다녀올게요~ 피부가 좀 칙칙해서… ({SKIN_COST}코인)"))), (2500, lambda: draw("normal"))]
    for i in range(1, 21): st.append((30, lambda i=i: root.geometry(f"+{round(x0 + (SW + 20 - x0) * i / 20)}+{y0}")))
    st.append((7000, lambda: None))  # 진료 중 (화면 밖)
    for i in range(1, 21): st.append((30, lambda i=i: root.geometry(f"+{round(SW + 20 + (x0 - SW - 20) * i / 20)}+{y0}")))
    def back():
        away[0] = False; save["skin_until"] = time.time() + 1800; flush(); draw("happy"); say("짜잔~ 피부 반질반질! 어때요? ✨"); hearts("✨", "#ffd34d")
    st += [(200, back), (5000, lambda: None)]
    sequence(st, finish_act)
    return True

def schedule_morning():  # 다음 오전 8시에 펫을 다시 실행하는 작업 스케줄러 작업을 만든다 (놓쳐도 켜지면 바로 실행)
    import subprocess, sys
    now = datetime.datetime.now(); t = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if t <= now: t += datetime.timedelta(days=1)
    exe = sys.executable.replace("python.exe", "pythonw.exe"); script = os.path.abspath(__file__)
    ps = (f"$a = New-ScheduledTaskAction -Execute '{exe}' -Argument '\"{script}\"' -WorkingDirectory '{HERE}'; "
          f"$t = New-ScheduledTaskTrigger -Once -At '{t:%Y-%m-%d %H:%M}'; $s = New-ScheduledTaskSettingsSet -StartWhenAvailable; "
          "Register-ScheduledTask -TaskName ClaudePetMorning -Action $a -Trigger $t -Settings $s -Force | Out-Null")
    try: subprocess.run(["powershell", "-NoProfile", "-Command", ps], creationflags=0x08000000, timeout=30)
    except Exception: pass

def leave():  # 퇴근: 인사하고 화면 밖으로 나가 종료, 다음 오전 8시에 다시 나타남
    global busy; busy = True; away[0] = True
    x0, y0 = root.winfo_x(), root.winfo_y()
    st = [(0, lambda: (draw("happy"), say("수고하셨어요! 내일 아침 8시에 다시 올게요~ 🙌"), hearts())), (4500, lambda: draw("normal"))]
    for i in range(1, 21): st.append((30, lambda i=i: root.geometry(f"+{round(x0 + (SW + 20 - x0) * i / 20)}+{y0}")))
    sequence(st, lambda: (schedule_morning(), root.destroy()))

def shop():  # 돈으로 살 수 있는 것 중 하나를 고름
    opts = [f for f, cost in ((skin_clinic, SKIN_COST), (buy_outfit, OUTFIT_COST), (buy_snack, SNACK_COST)) if save["coin"] >= cost and (f is not skin_clinic or (time.time() > save.get("skin_until", 0) and random.random() < 0.1))]  # 피부과는 광택이 끝났고 10% 확률일 때만
    random.shuffle(opts)
    for f in opts:
        if f(): return
    say(f"돈이 모자라요… 선물을 팔아 주세요! (보유 {save['coin']}코인)")

bagwin, bag_ph = [None], []
bag_tab = [0]; bag_page = [0]
bag_off = [None, None, False]  # [펫 기준 (dx, dy), 드래그 시작점, 드래그 중]
def bag():  # 인벤토리: 부위별 장비 칸(눌러서 입기/벗기) + 선물 칸
    if bagwin[0] and bagwin[0].winfo_exists(): bagwin[0].destroy(); bagwin[0] = None; return  # 열려 있으면 다시 눌러 닫음
    t = tk.Toplevel(root); t.overrideredirect(True); t.attributes("-topmost", True)  # 제목줄 없는 패널: 펫 옆에 붙어 따라다님
    t.config(bg="#fff7ec", highlightthickness=2, highlightbackground="#e0a060"); bagwin[0] = t
    off = bag_off  # 끌어서 옮기면 펫 기준 상대 위치를 기억하고 그대로 따라다님
    def follow():
        if not t.winfo_exists(): return
        if off[0] and not off[2]: t.geometry(f"+{root.winfo_x() + off[0][0]}+{root.winfo_y() + off[0][1]}"); t.after(40, follow); return
        if off[2]: t.after(40, follow); return
        w, h = t.winfo_width(), t.winfo_height(); x = root.winfo_x() + 14 - w  # 말풍선(창 가운데 약 16~224px)을 가리지 않게 그 바깥에
        if x < 0: x = root.winfo_x() + 226  # 왼쪽 공간이 없으면 말풍선 오른쪽 바깥에
        t.geometry(f"+{x}+{max(0, min(SH - h - 40, root.winfo_y() + 290 - h))}"); t.after(80, follow)
    t.after(30, follow)
    off = bag_off; tab = bag_tab  # 0=옷차림, 1=선물 (닫았다 열어도 마지막 탭 유지)
    fnt, bfnt, sfnt = ("Malgun Gothic", 10), ("Malgun Gothic", 10, "bold"), ("Malgun Gothic", 8)
    def toggle(o):
        if drag: say("지금은 바빠요~ 잠시 뒤에 다시요!"); return
        stopmove()  # 하던 동작을 멈추고 옷부터 갈아입음
        def sw():
            if o in save["outfit"]: save["outfit"].remove(o)
            else: wear_on(o)
            draw(pose()); flush()
        curtain(sw, lambda: (say(f"{o} {'입었어요' if o in save['outfit'] else '벗었어요'}!"), refresh()))
    def thumb(n, sz):  # 칸에 넣을 사진 (없으면 None)
        p = eq_icon(n) if n in OUTFITS else gift_icon(n) if n in DRAWN else icon_path(n)
        if not (Image and os.path.exists(p)): return None
        im = Image.open(p).convert("RGBA"); im.thumbnail((sz, sz)); bag_ph.append(ImageTk.PhotoImage(im)); return bag_ph[-1]
    def refresh():
        if not t.winfo_exists(): return
        for w in t.winfo_children(): w.destroy()
        bag_ph.clear()
        hd = tk.Frame(t, bg="#fff7ec"); hd.grid(row=0, column=0, sticky="we", padx=8, pady=(8, 2))
        grip = tk.Label(hd, text="≡ 이동", bg="#ffe0b8", font=sfnt, cursor="fleur", padx=6); grip.pack(side="left", padx=(0, 6))
        def gdown(e): off[1] = (e.x_root - t.winfo_x(), e.y_root - t.winfo_y()); off[2] = True
        def gmove(e): t.geometry(f"+{e.x_root - off[1][0]}+{e.y_root - off[1][1]}")
        def gup(e): off[2] = False; off[0] = (t.winfo_x() - root.winfo_x(), t.winfo_y() - root.winfo_y())
        for w_ in (grip, hd): w_.bind("<Button-1>", gdown); w_.bind("<B1-Motion>", gmove); w_.bind("<ButtonRelease-1>", gup)
        for ti, tn in enumerate(("옷차림", "선물")):
            tk.Button(hd, text=tn, font=bfnt, width=7, relief="sunken" if tab[0] == ti else "raised", bg="#ffd9a8" if tab[0] == ti else "#f3f3f3", command=lambda ti=ti: (tab.__setitem__(0, ti), refresh())).pack(side="left", padx=2)
        tk.Button(hd, text="✕", command=t.destroy, font=bfnt, width=3, relief="flat", bg="#e86a5a", fg="white").pack(side="right", padx=(4, 0))
        tk.Label(hd, text=f"💰 {save['coin']}  친밀도 {save['aff']}/{MAX_AFF}", bg="#fff7ec", font=sfnt).pack(side="right")
        if tab[0] == 0:
            eq = tk.LabelFrame(t, text=" 장비 (눌러서 입기/벗기) ", bg="#fff7ec", fg="#a05a20", font=bfnt); eq.grid(row=1, column=0, padx=8, pady=4)
            for r, (cat, lst) in enumerate(CATS):
                tk.Label(eq, text=cat, bg="#fff7ec", font=bfnt, width=5, anchor="w").grid(row=r, column=0, padx=(6, 2), pady=3)
                for k, o in enumerate(lst):
                    if o in save["owned"]:
                        on = o in save["outfit"]
                        im_ = thumb(o, 34)
                        tk.Button(eq, text=o, image=im_, compound="top" if im_ else "none", font=sfnt, width=64 if im_ else 10, height=54 if im_ else 2, bg="#ffd9a8" if on else "#f3f3f3", relief="sunken" if on else "raised", command=lambda o=o: toggle(o)).grid(row=r, column=k + 1, padx=2, pady=2)
                    else: tk.Label(eq, text="?", font=sfnt, width=10, height=3, bg="#dddddd", relief="groove").grid(row=r, column=k + 1, padx=2, pady=2)
        else:
            iv = tk.LabelFrame(t, text=" 선물 ", bg="#fff7ec", fg="#a05a20", font=bfnt); iv.grid(row=1, column=0, padx=8, pady=4)
            allit = list(save["inv"].items()); pages = max(1, (len(allit) + 11) // 12); bag_page[0] = max(0, min(pages - 1, bag_page[0]))
            items = allit[bag_page[0] * 12:(bag_page[0] + 1) * 12]  # 한 쪽에 12칸(4x3)
            pb = tk.Frame(iv, bg="#fff7ec"); pb.grid(row=3, column=0, columnspan=4, pady=(2, 4))
            tk.Button(pb, text="◀", font=bfnt, width=3, command=lambda: (bag_page.__setitem__(0, bag_page[0] - 1), refresh()), state="normal" if bag_page[0] > 0 else "disabled").pack(side="left", padx=6)
            tk.Label(pb, text=f"{bag_page[0] + 1} / {pages}", bg="#fff7ec", font=bfnt).pack(side="left", padx=6)
            tk.Button(pb, text="▶", font=bfnt, width=3, command=lambda: (bag_page.__setitem__(0, bag_page[0] + 1), refresh()), state="normal" if bag_page[0] < pages - 1 else "disabled").pack(side="left", padx=6)
            for i in range(12):  # 게임 인벤토리처럼 빈 칸도 보임
                f = tk.Frame(iv, bg="#ffffff" if i < len(items) else "#e6e0d6", bd=1, relief="solid", width=72, height=82); f.grid(row=i // 4, column=i % 4, padx=2, pady=2); f.grid_propagate(False)
                if i < len(items):
                    k, v = items[i]; im_ = thumb(k, 50)
                    if im_: tk.Label(f, image=im_, bg="#fff").pack(pady=(4, 0))
                    tk.Label(f, text=f"{k} x{v}", bg="#fff", font=sfnt, wraplength=66).pack(side="bottom", pady=2)
                    for w in [f] + list(f.winfo_children()):
                        w.bind("<Button-1>", lambda e, k=k: gift_menu(e, k)); w.config(cursor="hand2")
                        if k not in DRAWN: w.bind("<Button-3>", lambda e, k=k: (os.path.exists(icon_path(k)) and os.remove(icon_path(k)), icon_req.discard(k), want_icons(), refresh()))  # 사진이 이상하면 다시 찾기
    bagwin[1:] = [refresh]; refresh(); want_icons()

def bring_gift():  # 선물이나 옷을 주워옴 (사진을 받아오는 동안 말하고 기다림)
    left = [x for x in OUTFITS if x not in save["owned"]]
    if left and random.random() < 0.5:
        n = random.choice(left); speak("앗, 입을 걸 주워왔어요… 잠깐만요!"); give(n, True)
    elif Image:
        name, q = random.choice(GIFTS); speak("앗, 뭔가 주워왔어요… 잠깐만요!")
        if name in DRAWN: root.after(1200, give, name, False, item_art(name, 150))
        else: fetch_gift(name, q)
    else: give(random.choice(GIFTS)[0], False)

def pet():
    before = save["aff"] // GIFT_EVERY
    save["aff"] = min(MAX_AFF, save["aff"] + 1)
    hearts()
    if save["aff"] >= MAX_AFF and not save.get("danced"):  # 친밀도 100 도달: 기념 댄스
        stopmove(); setmode("auto"); breakdance()
    elif save["aff"] // GIFT_EVERY > before:
        bring_gift()
    else:
        show(random.choice(PET), "happy")
    flush()

# 손 커서: 머리를 잡거나 쓰다듬을 때 마우스 위치에 실제 손 사진(hand.png, 누끼)을 보여줌. 파일이 없으면 생략
HAND_PET = ("hand.png", 150, (0.3, 0.92), (0, 22))  # 쓰다듬는 손: 아래로 22px      # 쓰다듬는 손: 파일, 가로폭, 커서가 놓일 곳(손 그림 안 비율 좌표)
HAND_GRAB = ("hand_grab.png", 160, (0.05, 0.5), (0, -30))  # 머리를 꼬집어 드는 손 (엄지와 검지 사이가 커서). 두 손으로 받치는 모양은 hand_two.png (170, (0.42, 0.5))
def hand_make(spec):
    fname, wd, (ax, ay), off = spec  # off=(x, y) 화면에서 손을 더 옮길 픽셀 (위로는 음수)
    path = os.path.join(HERE, fname)
    if not (Image and os.path.exists(path)): return {}
    im = Image.open(path).convert("RGBA"); im.thumbnail((wd, wd * 2))
    bg = Image.new("RGB", im.size, TR); bg.paste(im, mask=im.getchannel("A"))
    t = tk.Toplevel(root); t.overrideredirect(True); t.attributes("-topmost", True); t.attributes("-transparentcolor", TR); t.config(bg=TR)
    ph = ImageTk.PhotoImage(bg); tk.Label(t, image=ph, bg=TR, bd=0).pack(); t.update_idletasks()
    try:  # 클릭이 손 창에 막히지 않고 그대로 통과 (WS_EX_TRANSPARENT)
        import ctypes; u = ctypes.windll.user32; hw = u.GetParent(t.winfo_id()) or t.winfo_id()
        u.SetWindowLongW(hw, -20, u.GetWindowLongW(hw, -20) | 0x20 | 0x80000)
    except Exception: pass
    t.withdraw(); return dict(win=t, ph=ph, px=int(im.width * ax), py=int(im.height * ay) - off[1], job=None)
hand, pinch = hand_make(HAND_PET), hand_make(HAND_GRAB)
def hand_show(x, y, hold=None, h=None):  # 손의 기준점이 (x, y)에 오도록. hold ms 뒤 자동으로 숨김(쓰다듬기용)
    h = h or hand
    if not h: return
    h["win"].geometry(f"+{x - h['px']}+{y - h['py']}"); h["win"].deiconify(); h["win"].lift(); c.config(cursor="none")  # 손이 보이는 동안 마우스 커서는 숨김
    if h["job"]: root.after_cancel(h["job"]); h["job"] = None
    if hold: h["job"] = root.after(hold, hand_hide)
def hand_hide():
    for h in (hand, pinch):
        if h: h["win"].withdraw()
    c.config(cursor="")

# 방망이 커서: 뒤돌아 사과 중일 때 펫 위에 방망이를 보여주고, 엉덩이를 클릭하면 휘두름. bat.png가 없으면 생략
bat = {}
BAT_W = 260  # 방망이 가로폭. 때리는 끝=왼쪽 끝, 손으로 잡는 곳(회전 중심)=오른쪽 끝 근처 (그림에서 자동 계산)
def bat_load():
    path = os.path.join(HERE, "bat.png")
    if not (Image and os.path.exists(path)): return
    im = Image.open(path).convert("RGBA"); im.thumbnail((BAT_W, BAT_W)); w, h = im.size
    al = im.getchannel("A"); x0, _, x1, _ = al.getbbox()
    def mid(x):  # 그 열에서 불투명한 부분의 가운데 y
        ys = [y for y in range(h) if al.getpixel((min(x, w - 1), y)) > 0]; return sum(ys) / len(ys) if ys else h / 2
    tx, ty, ex, ey = x0 + 1, mid(x0 + 1), x1 - 2, mid(x1 - 2)
    gx, gy = tx + 0.88 * (ex - tx), ty + 0.88 * (ey - ty)
    vs = []; L = int(math.hypot(w, h)) + 4  # 회전해도 안 잘리게 넉넉한 캔버스
    for ang in (0, -30, 25):  # 평소 / 치켜들기 / 내려치기 (손 쥔 곳을 중심으로 회전)
        big = Image.new("RGBA", (2 * L, 2 * L), (0, 0, 0, 0)); big.paste(im, (int(L - gx), int(L - gy)))
        big = big.rotate(ang, resample=Image.BICUBIC, center=(L, L))
        bg = Image.new("RGB", big.size, TR); bg.paste(big, mask=big.getchannel("A").point(lambda v: 255 if v > 128 else 0))
        a, dx, dy = math.radians(ang), tx - gx, ty - gy  # 끝점이 회전한 위치
        vs.append((ImageTk.PhotoImage(bg), L + dx * math.cos(a) + dy * math.sin(a), L - dx * math.sin(a) + dy * math.cos(a)))
    t = tk.Toplevel(root); t.overrideredirect(True); t.attributes("-topmost", True); t.attributes("-transparentcolor", TR); t.config(bg=TR)
    lb = tk.Label(t, image=vs[0][0], bg=TR, bd=0); lb.pack(); t.update_idletasks()
    try:
        import ctypes; u = ctypes.windll.user32; hw = u.GetParent(t.winfo_id()) or t.winfo_id()
        u.SetWindowLongW(hw, -20, u.GetWindowLongW(hw, -20) | 0x20 | 0x80000)
    except Exception: pass
    t.withdraw(); bat.update(win=t, lb=lb, vs=vs, x=0, y=0, v=0, job=None)
def bat_show(x, y, hold=None, v=0):  # 방망이 끝이 (x, y)에 오도록
    if not bat: return
    bat.update(x=x, y=y, v=v); ph, px, py = bat["vs"][v]; bat["lb"].config(image=ph)
    bat["win"].geometry(f"+{int(x - px)}+{int(y - py)}"); bat["win"].deiconify(); bat["win"].lift(); c.config(cursor="none")
    if bat["job"]: root.after_cancel(bat["job"]); bat["job"] = None
    if hold: bat["job"] = root.after(hold, bat_hide)
def bat_hide():
    if bat: bat["win"].withdraw(); c.config(cursor="")
def bat_swing():  # 치켜들었다가 내려침
    if not bat: return
    x, y = bat["x"], bat["y"]; bat_show(x, y, None, 1)
    root.after(110, lambda: bat_show(x, y, None, 2)); root.after(260, lambda: bat_show(x, y, 900, 0))
bat_load()

drag = {}
def press(e):
    ex, ey = conv(e)
    if mood in ("sorry", "hit") and 40 < ex < 200 and 140 < ey < 235:  # 엉덩이 때찌
        show(random.choice(HIT), "hit"); bat_swing()
        root.after(1200, lambda: draw("sorry"))
    elif 40 < ex < 200 and 90 < ey < 140:  # 머리채 잡기
        global busy
        stopmove(); busy = True
        drag.update(mx=e.x_root, my=e.y_root, x=root.winfo_x(), y=root.winfo_y(), m=mood)
        hand_hide(); hand_show(e.x_root, e.y_root, h=pinch); flail()
def move(e):
    global busy
    if not drag: return
    busy = True
    nx = cx(drag["x"] + e.x_root - drag["mx"])
    ny = cy(drag["y"] + e.y_root - drag["my"])
    root.geometry(f"+{nx}+{ny}"); hand_show(e.x_root, e.y_root, h=pinch)
LAND = [(1.25, 0.72), (0.9, 1.18), (1.07, 0.93), (0.98, 1.03), (1, 1)]
def boing(seq, i=0, ms=60):  # 말랑한 반동: 찌그러졌다 늘어났다 제자리로
    if i >= len(seq): return
    nx, ny = seq[i]; c.scale("body", 120, 235, nx / sq[0], ny / sq[1]); sq[:] = nx, ny
    root.after(ms, boing, seq, i + 1, ms)

def flail(f=0):  # 잡혀 있는 동안 발버둥 + 출렁
    if not drag: return
    sq[:] = [1.04, 0.94] if f else [0.95, 1.07]
    draw("struggle", f=f); root.after(130, flail, 1 - f)

def release(e):
    global busy
    if drag:
        prev = drag["m"]; drag.clear(); busy = False; hand_hide()
        save["pos"] = [root.winfo_x(), root.winfo_y()]; flush()
        sq[:] = [1.0, 1.0]; draw("sorry" if prev in ("sorry", "hit") else pose()); boing(LAND)
        if mode == "roam": roam()
def dbl(e):  # 몸통(머리 아래)을 더블클릭하면 인벤토리
    ex, ey = conv(e)
    if mood not in ("sorry", "hit") and 40 < ex < 200 and 140 < ey < 235: bag()
c.bind("<Double-Button-1>", dbl); c.bind("<Button-1>", press); c.bind("<B1-Motion>", move); c.bind("<ButtonRelease-1>", release)

def stopmove():  # 진행 중인 이동/점프/활동을 모두 취소 (사다리·밭 같은 소품도 치움)
    global gen, busy
    gen += 1; busy = False; clear_props()

props = []
def prop(w, h, x, y, fn):  # 펫 옆에 놓는 소품 창 (사다리, 밭). 펫보다 뒤에 깔림
    t = tk.Toplevel(root); t.overrideredirect(True); t.attributes("-topmost", True)
    t.attributes("-transparentcolor", TR); t.config(bg=TR); t.geometry(f"{w}x{h}+{x}+{y}")
    cv = tk.Canvas(t, width=w, height=h, bg=TR, highlightthickness=0); cv.pack(); fn(cv)
    props.append(t); root.after(80, raise_pet); return cv

def raise_pet():  # topmost를 껐다 켜서 펫 창을 소품 위로
    root.attributes("-topmost", False); root.attributes("-topmost", True); root.lift()

def clear_props():
    for t in props: t.destroy()
    props.clear()

def sequence(steps, end=None):  # [(지연ms, 함수)...] 를 차례로 실행. 드래그/명령으로 취소되면 중단
    g = gen
    def go(i=0):
        if g != gen: return
        if i >= len(steps):
            if end: end()
            return
        d, fn = steps[i]
        def fire():
            if g != gen: return
            fn(); go(i + 1)
        root.after(d, fire)
    go()

QUOTES = [("천 리 길도 한 걸음부터", "노자"), ("실패는 성공의 어머니", "속담"), ("오늘 할 일을 내일로 미루지 마라", "벤저민 프랭클린"),
          ("가장 어두운 밤도 결국은 끝나고 해는 떠오른다", "빅토르 위고"), ("시작이 반이다", "아리스토텔레스"), ("작은 기회로부터 위대한 업적이 시작된다", "데모스테네스"),
          ("넘어지는 것이 아니라 일어나지 않는 것이 실패다", "공자"), ("할 수 있다고 믿으면 이미 반은 온 것이다", "시어도어 루즈벨트"),
          ("꿈을 계속 간직하고 있으면 반드시 실현된다", "괴테"), ("배움에는 왕도가 없다", "유클리드"), ("나는 생각한다, 고로 존재한다", "데카르트"),
          ("지식에 투자하는 것이 최고의 이자를 낳는다", "벤저민 프랭클린"), ("강한 자가 살아남는 것이 아니라 살아남는 자가 강하다", "속담"),
          ("행복은 습관이다. 그것을 몸에 지니라", "허버드"), ("먼저 자신을 이겨라", "플라톤"), ("고통 없이는 얻는 것도 없다", "속담"),
          ("오늘이라는 날은 두 번 다시 오지 않는다", "단테"), ("모든 것은 지나간다", "솔로몬"), ("아는 것이 힘이다", "프랜시스 베이컨"),
          ("버그 없는 코드는 아직 테스트되지 않은 코드다", "개발자 격언")]
STAY = 180000  # 책 읽기·졸기·게임·의자 쉬기는 한 번에 약 3분
def anim(m, n, frames=12, ms=60, saw=False, hook=None):  # m 동작을 n번 반복. 한 번에 frames장: f가 0→1→0으로 부드럽게 변함(saw면 0→1 반복)
    st = []
    for k in range(n):
        for i in range(frames):
            f = i / frames if saw else 0.5 - 0.5 * math.cos(2 * math.pi * i / frames)
            st.append((ms, lambda f=f, k=k, i=i: (draw(m, f=f), hook and hook(k, i))))
    return st

def doze():  # 꾸벅꾸벅 졸다가 화들짝 깸
    global busy; busy = True
    st = [(0, lambda: (draw("doze"), say("음… 졸리다…")))] + anim("doze", STAY // 1800, frames=20, ms=90)
    st += [(300, lambda: (draw("normal"), say("헉! 안 졸았어요!"))), (2500, lambda: None)]
    sequence(st, finish_act)

def wig(n):  # 눈썹을 n번 들썩
    global brow
    g = gen
    def go(i):
        global brow
        if g != gen or i >= n: brow = 0; return
        brow = i % 2 == 0; draw("read"); root.after(160, go, i + 1)
    go(0)

def sticky(title, body, bg="#fff3a8", fg="#8a5a00"):  # 펫 옆에 쪽지 창
    t = tk.Toplevel(root); t.title("쪽지"); t.attributes("-topmost", True); t.config(bg=bg)
    t.geometry(f"+{max(0, root.winfo_x() - 330)}+{max(0, root.winfo_y() + 30)}")
    tk.Label(t, text=title, bg=bg, fg=fg, font=("Malgun Gothic", 11, "bold")).pack(padx=18, pady=(14, 6), anchor="w")
    tk.Label(t, text=body, bg=bg, font=("Malgun Gothic", 10), justify="left", wraplength=280).pack(padx=18, anchor="w")
    tk.Label(t, text="- 클로드 드림", bg=bg, fg=fg, font=("Malgun Gothic", 9)).pack(padx=18, pady=(10, 2), anchor="e")
    tk.Button(t, text="고마워요", command=t.destroy, font=("Malgun Gothic", 9)).pack(pady=(2, 12))

def read_book():  # 책 읽기: 조용히 페이지를 넘기고(넘어가는 페이지가 부드럽게), 가끔만 한마디
    global busy; busy = True
    lines = ["음… 흥미롭군…", "오호 그렇구나", "이 부분 재밌다", "허허 이런 일이", "한 장만 더…"]
    st = [(0, lambda: (draw("read"), say("책 좀 읽어볼까요~")))]
    for j in range(STAY // 4000):
        def turn(j=j):
            draw("read")
            if j % 8 == 7:
                say(lines[j // 8 % len(lines)]); wig(6)  # 8장마다 한마디 + 눈썹 들썩
            elif j % 8 == 1: c.delete("bub")
        st += [(3600, lambda: draw("read"))] + [(45, lambda f=(i + 1) / 8: draw("read", f=f)) for i in range(8)] + [(40, turn)]
    q, who = random.choice(QUOTES)
    st += [(1200, lambda: (draw("happy"), say("재밌었다! 다 읽었어요"))),
           (1500, lambda: (sticky("오늘의 명언", f"\"{q}\"\n\n- {who}"), say("명언 하나 적어서 드렸어요~"))), (5000, lambda: None)]
    sequence(st, finish_act)

def work():  # 일하기: 노트북으로 타자를 치며 한참 일함 (약 3분), 가끔 한마디
    global busy; busy = True
    lines = ["회의록 정리 중…", "커밋 커밋~", "버그가 또 나왔네", "이슈 하나 처리!", "TC 작성 중이에요", "집중 집중…", "퇴근하고 싶다…", "메일 답장부터 해야지", "빌드 돌리는 중~"]
    st = [(0, lambda: (draw("work"), say("저도 일할게요! 같이 힘내요")))]
    for j in range(STAY // 400):
        def tick(j=j):
            draw("work", f=j % 2)
            if j % 70 == 69: say(random.choice(lines))
            elif j % 70 == 74 % 70: c.delete("bub")
        st.append((400, tick))
        if j == STAY // 400 // 2: st += stretch_steps() + [(300, lambda: draw("work"))]  # 일하다 중간에 스트레칭
    st += [(500, lambda: (draw("happy"), say("오늘 업무 끝! 퇴근해도 되죠?"))), (2500, lambda: None)]
    sequence(st, finish_act)

def play_game():  # 게임: 조용히 하다가 가끔만 한마디
    global busy; busy = True
    lines = ["아 죽었다!!", "한 판만 더…", "됐다! 깼다!", "어어어 잠깐만!"]
    st = [(0, lambda: (draw("game"), say("한 판만 할게요~")))]
    for j in range(STAY // 1950):
        def tick(j=j):
            draw("game")
            if j % 12 == 11: say(lines[j // 12 % len(lines)])
            elif j % 12 == 2: c.delete("bub")
        st += [(500, lambda: draw("game", f=1)), (400, tick)] + [(350, lambda k=k: draw("game", f=k % 2)) for k in range(3)]
    st += [(500, lambda: (draw("happy"), say("재밌다~ 이제 일해야지"))), (2500, lambda: None)]
    sequence(st, finish_act)

def shower():  # 샤워: 비누 거품 → 물 맞기 → 보송보송 (물줄기가 계속 흘러내림)
    global busy; busy = True
    hook = lambda k, i: i == 0 and (k == 12 and say("비누칠 중~ 거품거품") or k == 30 and say("헹구는 중~"))
    st = [(0, lambda: (draw("shower"), say("샤워할 시간~")))] + anim("shower", 40, frames=12, ms=58, saw=True, hook=hook)
    st += [(300, lambda: (draw("happy"), say("상쾌하다~ 보송보송!"))), (2500, lambda: None)]
    sequence(st, finish_act)

def brush_teeth(then=None):  # 양치: 칫솔이 좌우로 슥슥
    global busy; busy = True
    st = [(0, lambda: (draw("brush"), say("양치하자~")))] + anim("brush", 30, frames=10, ms=55, hook=lambda k, i: i == 0 and k == 14 and say("구석구석 닦는 중~"))
    st += [(300, lambda: (draw("happy"), say("이가 반짝반짝! 뽀득뽀득"))), (2500, lambda: None)]
    sequence(st, then or finish_act)

def toilet(then=None, after_meal=False):  # 화장실: 힘주기 → 시원 → 물 내리기
    global busy; busy = True
    gold = "황금 변기" in save["inv"]
    st = [(0, lambda: (draw("poop"), say(("밥 먹었더니 신호가 왔어요…" if after_meal else "앗… 화장실 가야겠다") if not gold else "황금 변기를 써볼 때가 왔군요"))), (1300, lambda: None)]
    st += anim("poop", 4, frames=14, ms=55, hook=lambda k, i: i == 0 and k == 0 and say("으으으…"))
    st += [(300, lambda: (draw("poop", f=2), say("후… 시원하다~"))), (2200, lambda: (draw("poop", f=3), say("쏴아아~ 물 내렸어요"))), (1800, lambda: (draw("happy"), say("손도 깨끗이 씻었어요!"))), (2500, lambda: None)]
    sequence(st, then or finish_act)

def run_laps():  # 달리기: 화면을 가로질러 왕복. 팔다리가 부드럽게 번갈아 움직임
    global busy; busy = True; g = gen
    x0, y0 = root.winfo_x(), root.winfo_y(); path = [min(XR, x0 + 320), max(XL, x0 - 320), x0]; stt = dict(i=0, k=0)
    say("달리기 하러 가자! 헉헉"); draw("run")
    def step():
        if g != gen: return
        tx = path[stt["i"]]; cx = root.winfo_x()
        if abs(tx - cx) <= 7:
            stt["i"] += 1
            if stt["i"] >= len(path):
                save["pos"] = [root.winfo_x(), y0]; flush(); draw("happy"); say("후… 완주했다! 숨차요")
                root.after(2500, lambda: g == gen and finish_act()); return
        else:
            root.geometry(f"+{cx + (7 if tx > cx else -7)}+{y0}"); stt["k"] += 1
            if stt["k"] % 2 == 0: draw("run", f=0.5 - 0.5 * math.cos(2 * math.pi * stt["k"] / 18))
        root.after(22, step)
    step()

def workout(kind=None):  # 운동: 역도(덤벨) / 팔벌려뛰기 / 줄넘기 / 달리기 중 하나
    global busy
    kind = kind or random.choice(("dumbbell", "dumbbell", "jack", "rope", "run"))
    if kind == "run": run_laps(); return
    busy = True
    if kind == "jack":
        st = [(0, lambda: (draw("jack"), say("팔 벌려 뛰기 시작! 하나 둘~")))] + anim("jack", 24, frames=10, ms=38, hook=lambda k, i: i == 0 and k % 6 == 5 and say(f"{k + 1}! 힘내자!"))
    elif kind == "rope":
        st = [(0, lambda: (draw("rope"), say("줄넘기 시작~")))] + anim("rope", 36, frames=12, ms=32, saw=True, hook=lambda k, i: i == 0 and k % 10 == 9 and say(f"{k + 1}개!"))
    else:  # 역도: 천천히 들어올려서 버티며 바들바들 떨다가 천천히 내림
        ease = lambda t: t * t * (3 - 2 * t)
        st = [(0, lambda: (draw("gym"), say("운동할 시간이에요! 역도 간다~")))]
        for j in range(10):
            st += [(75, lambda f=ease((i + 1) / 18): draw("gym", f=f)) for i in range(18)]  # 천천히 듦 (끙차…)
            st += [(70, lambda j=j, i=i: (draw("gym", f=1), i == 0 and say(f"{j + 1}… 으으으…"))) for i in range(12)]  # 버티며 바들바들
            st += [(70, lambda f=1 - ease((i + 1) / 14): draw("gym", f=f)) for i in range(14)]  # 천천히 내림
            st += [(250, lambda: draw("gym"))]
    st += [(500, lambda: (draw("happy"), say("운동 끝! 근육 생겼다 (아마도)"))), (2500, lambda: None)]
    sequence(st, finish_act)

def coffee():  # 커피 한 잔: 김이 모락모락, 홀짝홀짝
    global busy; busy = True
    st = [(0, lambda: (draw("coffee"), say("커피 한 잔의 여유~")))]
    for j in range(8):
        ease = lambda t: t * t * (3 - 2 * t)
        st += [(1000, lambda: draw("coffee"))] + [(60, lambda f=ease((i + 1) / 14): draw("coffee", f=f)) for i in range(14)] + [(900, lambda j=j: (draw("coffee", f=1), j == 0 and say("후루룩… 뜨거워!")))] + [(60, lambda f=1 - ease((i + 1) / 14): draw("coffee", f=f)) for i in range(14)]
    st += [(400, lambda: (draw("happy"), say("아~ 이제 잠이 깬다!"))), (2500, lambda: None)]
    sequence(st, finish_act)

MEALS = {9: "아침", 11: "점심", 17: "저녁"}  # 이 시각(시)에 밥을 먹음
def meal(slot=None):  # 밥 먹기: 숟가락이 밥그릇과 입 사이를 부드럽게 오감. 다 먹으면 화장실 → 양치
    global busy; busy = True
    nm = MEALS.get(slot, "밥")
    st = [(0, lambda: (draw("eat"), say(f"{nm} 먹을 시간이다~ 냠냠")))]
    st += anim("eat", 30, frames=16, ms=48, hook=lambda k, i: i == 0 and (k == 10 and say("맛있다~") or k == 22 and say("한 그릇 뚝딱!")))
    st += [(300, lambda: (draw("happy"), say(f"{nm} 잘 먹었습니다! 배불러요"))), (2500, lambda: None)]
    sequence(st, lambda: toilet(then=brush_teeth, after_meal=True))

FORTUNE = {
    5: "오늘은 뭘 해도 술술 풀리는 날! 미뤄둔 일에 손을 대 보세요.", 4: "대체로 순조로워요. 작은 행운이 따라옵니다.",
    3: "평범하지만 안정적인 하루예요. 서두르지 않으면 좋아요.", 2: "살짝 꼬이는 날. 저장(Ctrl+S)을 자주 하세요!", 1: "오늘은 몸을 사리는 날. 큰 결정은 내일로 미뤄요."}
F_MONEY = ["뜻밖의 작은 지출이 있어요", "아끼면 오늘 득을 봐요", "점심값이 굳을지도?", "충동구매만 조심하면 OK", "커피 한 잔의 여유가 생겨요"]
F_PEOPLE = ["동료의 한마디가 힘이 돼요", "먼저 인사하면 좋은 일이 생겨요", "오랜 친구에게 연락이 올지도요", "오해가 풀리는 하루", "칭찬을 아끼지 마세요"]
F_WORK = ["버그가 저절로 사라질 수도 있어요", "재현이 안 되던 이슈의 단서를 찾아요", "리뷰에서 칭찬을 받아요", "빌드가 한 번에 통과해요", "점심 먹고 집중이 잘 돼요", "오늘은 테스트가 다 pass!"]
F_COLOR = ["주황색", "하늘색", "연두색", "보라색", "노란색", "분홍색", "흰색"]
F_SNACK = ["꿀사과", "아이스 아메리카노", "초콜릿", "삼각김밥", "붕어빵", "바나나우유"]
def fortune():  # 오늘의 운세를 쪽지로 전해줌 (같은 날엔 같은 운세)
    global busy
    today = datetime.date.today().isoformat(); rnd = random.Random(today)
    n = rnd.choice([1, 2, 3, 3, 4, 4, 5, 5])
    body = (f"{'★' * n}{'☆' * (5 - n)}  {FORTUNE[n]}\n\n재물: {rnd.choice(F_MONEY)}\n인간관계: {rnd.choice(F_PEOPLE)}\n업무: {rnd.choice(F_WORK)}\n\n"
            f"행운의 색: {rnd.choice(F_COLOR)}\n행운의 숫자: {rnd.randint(1, 45)}\n행운의 간식: {rnd.choice(F_SNACK)}")
    save["fortune_day"] = today; flush(); busy = True
    sequence([(0, lambda: (draw("happy"), say("쪽지 한 장 가져왔어요~"))), (1500, lambda: (sticky(f"오늘의 운세  {today}", body), say("오늘의 운세예요! 읽어보세요"))), (6000, lambda: None)], finish_act)

LIGHTS = ["#ff4d8d", "#ffd34d", "#4dd2ff", "#7dff6b", "#b46bff"]
def bd(m, f=0, sx=1.0, sy=1.0, dx=0, dy=0):  # 브레이크댄스용: 그린 뒤 몸을 뒤집고(sy=-1) 가로로 돌리는(sx=cos) 변형
    draw(m, f=f)
    if abs(sx) < 0.1: sx = 0.1 if sx >= 0 else -0.1
    if sx != 1 or sy != 1: c.scale("body", 120, 182, sx, sy)  # 몸 가운데(세로 182) 기준
    c.move("body", dx, dy)

def lights(i):  # 몸 뒤에서 번쩍이는 클럽 조명
    c.delete("bdfx")
    for k, (x0, y0, x1, y1) in enumerate(((10, 110, 90, 190), (150, 100, 230, 180), (60, 190, 180, 250))):
        c.create_oval(x0, y0, x1, y1, fill=LIGHTS[(i + k) % len(LIGHTS)], outline="", tags="bdfx")
    c.tag_lower("bdfx")

def breakdance():  # 친밀도 100 기념 브레이크댄스: 톱록 → 팽이 돌기 → 헤드스핀 → 프리즈
    global busy; busy = True
    st = [(0, lambda: (draw("happy"), say("애정도 100 달성!! 기깔나게 한 번 춰볼게요~ 음악 주세요 🎶"), hearts("♪", "#4a7bd8"))), (2600, lambda: None)]
    for i in range(32):  # 톱록: 좌우로 흔들며 팔다리 번갈아
        ph = i / 32 * 4 * math.pi
        st.append((85, lambda i=i, ph=ph: (lights(i // 2), bd("jack" if i % 6 < 3 else "run", f=(i // 3) % 2, sx=1 + 0.07 * math.cos(ph * 2), dx=round(22 * math.sin(ph)), dy=-round(4 * abs(math.sin(ph * 2)))), i == 4 and say("자, 간다!"))))
    for i in range(30):  # 서서 팽이처럼 돌면서 점프
        st.append((60, lambda i=i: (lights(i), bd("jack", f=1, sx=math.cos(i * math.pi / 2.2), dy=-round(26 * math.sin(i / 30 * math.pi))), i == 2 and say("윈드밀~!"))))
    for i in range(40):  # 헤드스핀: 거꾸로 뒤집혀 빠르게 회전
        st.append((50, lambda i=i: (lights(i), bd("jack", f=i % 2, sx=math.cos(i * 1.05), sy=-1, dy=-round(5 * abs(math.sin(i / 3)))), i == 3 and say("헤드스핀!!"), i % 10 == 5 and hearts("♪", "#ff5d8f"))))
    st.append((120, lambda: (lights(0), bd("jack", f=1, sy=-1), say("프리즈! 😎"))))
    for i in range(10): st.append((140, lambda i=i: (lights(i), bd("jack", f=i % 2, sy=-1, dx=(3 if i % 2 else -3)))))  # 프리즈 상태로 팔 바들바들
    st.append((300, lambda: (c.delete("bdfx"), draw("happy"), say("짜잔! 오늘부터 우리는 찐친이에요 💕"), hearts(), root.after(500, hearts), root.after(1000, lambda: hearts("✨", "#ffd34d")))))
    st.append((4500, lambda: None))
    def done_():
        save["danced"] = True; flush(); c.delete("bdfx"); finish_act()
    sequence(st, done_)

def stretch_steps():  # 스트레칭: 팔 들고 몸을 위로 쭈욱 늘리기 ×3 → 좌우로 쭈욱 늘리기 → 앞으로 숙이기
    ease = lambda t: t * t * (3 - 2 * t)
    st = [(0, lambda: (draw("happy"), say("스트레칭~ 으아아아 쭈욱~")))]
    for r in range(3):
        for i in range(1, 13): st.append((60, lambda i=i: bd("jack", f=1, sy=1 + 0.28 * ease(i / 12), sx=1 - 0.1 * ease(i / 12), dy=-round(14 * ease(i / 12)))))  # 위로 늘어남 (발은 제자리)
        for i in range(6): st.append((100, lambda i=i: bd("jack", f=1, sy=1.28 + 0.01 * (i % 2), sx=0.9, dy=-14)))  # 끝에서 버팀
        for i in range(1, 7): st.append((60, lambda i=i: bd("jack", f=0, sy=1.28 - 0.28 * i / 6, sx=0.9 + 0.1 * i / 6, dy=-round(14 * (1 - i / 6)))))
    for side in (-1, 1):  # 옆으로 쭈욱
        for i in range(1, 11): st.append((70, lambda i=i, side=side: bd("jack", f=1, sx=1 + 0.2 * ease(i / 10), dx=side * round(22 * ease(i / 10)))))
        for i in range(6): st.append((100, lambda side=side: bd("jack", f=1, sx=1.2, dx=side * 22)))
        for i in range(1, 7): st.append((60, lambda i=i, side=side: bd("jack", f=0, sx=1.2 - 0.2 * i / 6, dx=side * round(22 * (1 - i / 6)))))
    for i in range(1, 9): st.append((80, lambda i=i: bd("run", f=0, sy=1 - 0.12 * ease(i / 8), dy=round(12 * ease(i / 8)))))  # 앞으로 숙여 발끝 닿기
    st += [(900, lambda: None)]
    for i in range(1, 7): st.append((70, lambda i=i: bd("run", f=0, sy=0.88 + 0.12 * i / 6, dy=round(12 * (1 - i / 6)))))
    st += [(300, lambda: (draw("happy"), say("시원하다~ 다시 일하자!"))), (1500, lambda: None)]
    return st

def stretch():
    global busy; busy = True; sequence(stretch_steps(), finish_act)

def groove():  # 서 있다가 흥에 겨워 한 곡 (브레이크댄스보다 가볍게)
    global busy; busy = True
    st = [(0, lambda: (draw("happy"), say("괜히 흥이 나네~ 🎵"), hearts("♪", "#4a7bd8")))]
    for i in range(44):
        ph = i / 44 * 6 * math.pi
        st.append((110, lambda i=i, ph=ph: (bd("jack" if i % 8 < 4 else "run", f=(i // 2) % 2, sx=1 + 0.05 * math.cos(ph * 2), dx=round(14 * math.sin(ph)), dy=-round(5 * abs(math.sin(ph)))), i % 14 == 7 and hearts("♪", "#ff5d8f"))))
    st += [(300, lambda: (draw("happy"), say("헤헤 들켰다 😆"))), (2200, lambda: None)]
    sequence(st, finish_act)

def finish_act():
    global busy
    clear_props(); busy = False; draw("normal"); c.delete("bub")

def ladder_art(cv):
    for x in (8, 52): cv.create_line(x, 2, x, 200, width=6, fill="#a9743a")
    for y in range(14, 200, 22): cv.create_line(8, y, 52, y, width=5, fill="#c4914f")

imgs, fails, pending, ladder_ph, cab_ph = {}, set(), set(), [], []
def want(kind, q, size, ok=None, ex="", shape=None):  # 소품 사진을 미리 받아둠 (한 번 받으면 재사용)
    if not Image: fails.add(kind); return
    if kind in imgs or kind in pending: return
    fails.discard(kind); pending.add(kind); fetch_gift(kind, q, size, ok, ex, shape, 20)

def ladder():  # 사다리 사진을 꺼내 놓고 뒷모습으로 올라가 전망을 보고 뛰어내림
    global busy
    px, py = root.winfo_x(), root.winfo_y()
    if py < 170: return
    busy = True; g = gen
    def go():
        im = None  # 사다리 사진은 검색 결과가 엉뚱해서 그린 사다리만 씀
        w, h = im.size if im else (60, 200)
        def art(cv):
            if im: ladder_ph[:] = [ImageTk.PhotoImage(im)]; cv.create_image(w // 2, h // 2, image=ladder_ph[0])
            else: ladder_art(cv)
        climb = min(144, max(54, h - 90)); dy = climb / 8
        st = [(0, lambda: (prop(w, h, max(0, px + 120 - w // 2), py + 240 - h, art), draw("climb"), say("사다리 타고 올라가 볼게요!")))]
        for i in range(1, 9):
            st.append((300, lambda i=i: (root.geometry(f"+{px}+{round(py - dy * i)}"), draw("climb", f=i % 2))))
        st.append((400, lambda: (draw("happy"), say("전망 좋다~! 세상이 작아 보여요"))))
        st.append((2600, lambda: (say("내려갑니다~ 점프!"), hop(px, py))))
        st.append((900, lambda: None))
        sequence(st, finish_act)
    go()

chair_cache, chair_failed, chair_ph = [], [], []
def chair_art(cv):  # 사진을 못 가져왔을 때 대신 그리는 의자
    cv.create_rectangle(45, 20, 125, 100, fill="#b07a3c", outline="#5b3a17", width=3)
    cv.create_rectangle(40, 100, 130, 122, fill="#c4914f", outline="#5b3a17", width=3)
    for x in (45, 115): cv.create_rectangle(x, 122, x + 12, 165, fill="#a06a2c", outline="#5b3a17", width=3)

def rest():  # 쉴 때: 주머니를 뒤적여 의자(실제 사진)를 꺼내 앉아서 쉼
    global busy
    px, py = root.winfo_x(), root.winfo_y(); busy = True; g = gen
    if not chair_cache:
        mine = next((f for f in ("chair.png", "chair.jpg") if os.path.exists(os.path.join(HERE, f))), None)  # 내가 넣어둔 의자 사진 우선
        if mine and Image: chair_cache.append(cutout(Image.open(os.path.join(HERE, mine)), 170, 60))
    if not chair_cache:
        if Image: chair_failed.clear(); fetch_gift("__chair__", "upholstered chair chrome legs", 170)
        else: chair_failed.append(1)
    def sit_down():
        im = random.choice(chair_cache) if chair_cache else None
        def art(cv):
            if im: chair_ph[:] = [ImageTk.PhotoImage(im)]; cv.create_image(85, 85, image=chair_ph[0])
            else: chair_art(cv)
        prop(170, 170, px + 35, py + 70, art)
        lift = min(86 if im else 57, py)  # 방석 높이까지 올라감 (사진 의자 기준)
        st = [(0, lambda: (draw("happy"), say("짠~ 의자 꺼냈어요!"))),
              (900, lambda: (say("올라앉을게요~"), hop(px, py - lift))),
              (700, lambda: (draw("sit"), say("휴~ 역시 의자가 최고…"))),
              *[(6000, lambda: say(random.choice(TALK))) for _ in range(STAY // 6000)],  # 의자에서 한참 쉼
              (4500, lambda: (draw("happy"), say("잘 쉬었다! 내려갈게요"), hop(px, py))),
              (900, lambda: None)]
        sequence(st, finish_act)
    def rummage(i=0):
        if g != gen: return
        if i >= 6 and (chair_cache or chair_failed or i >= 16): sit_down(); return
        draw("rummage", f=i % 2)
        if i == 0: say("좀 쉴까요~ 주머니에 의자가…")
        if i == 3: say("어디 있더라… 뒤적뒤적")
        root.after(300, rummage, i + 1)
    rummage()

GY = 116  # 밭 흙 중심 y (밭 창 기준)
CROP_EX = " -seedling -seed -seeds -field -plant -plants -garden -flower -truck -lorry -vehicle -tractor -harvester -car -road -market -street -worker -farmer -people -dish -soup -salad -cooked -moth -butterfly -illustration -drawing"
# 심을 것: 이름 → (영어 검색어, 가로/세로 비율 범위, 그림 대체색, 검색 제외어). 채소부터 엉뚱한 것까지 랜덤
CROPS = {"배추": ("napa cabbage", (0.6, 1.8), "#cbe99a", CROP_EX), "당근": ("carrot vegetable", (0.2, 0.9), "#f08a24", CROP_EX), "무": ("daikon radish", (0.25, 1.0), "#f4f4e8", CROP_EX),
         "토마토": ("tomato fruit", (0.7, 1.4), "#e5382b", CROP_EX), "호박": ("pumpkin", (0.8, 1.6), "#f2992e", CROP_EX), "가지": ("eggplant", (0.5, 2.2), "#5b2a6e", CROP_EX),
         "옥수수": ("corn cob", (0.2, 1.0), "#f2d338", CROP_EX), "수박": ("watermelon whole", (0.8, 1.6), "#3f8f3a", CROP_EX), "감자": ("potato tubers", (0.8, 2.0), "#c9a36b", CROP_EX),
         "양파": ("onion bulb", (0.7, 1.5), "#d9a066", CROP_EX),
         "퇴계 이황": ("Yi Hwang Joseon portrait", (0.4, 1.3), "#d8c9a8", ""), "감스트": ("", (0.3, 1.3), "#7a8cc2", ""),  # 무료 사진이 없어서 검색하지 않고 이름표 그림으로
         "세종대왕": ("King Sejong the Great statue", (0.3, 1.3), "#d9b44a", " -banknote -stamp -coin"), "이순신 장군": ("Admiral Yi Sun-sin statue", (0.2, 1.1), "#9a9a9a", " -banknote -ship"),
         "트럭": ("pickup truck", (0.9, 2.5), "#3b6fb5", ""), "피아노": ("upright piano", (0.7, 1.8), "#222222", " -player"), "기린": ("giraffe", (0.3, 1.0), "#e0b050", " -zoo -cage"),
         "펭귄": ("penguin", (0.4, 1.2), "#222222", ""), "냉장고": ("refrigerator", (0.3, 1.0), "#d0d8e0", " -magnet")}
def crop_art(cv, x, g, base, name):  # 작물 한 포기: g<=0.2 싹 → 점점 커져서 g=1.0이면 다 자란 모습
    if g <= 0.2:
        cv.create_line(x, GY, x, GY - 12, width=3, fill="#4f8f2a")
        cv.create_oval(x - 11, GY - 20, x, GY - 8, fill="#7ac143", outline="#3f7d20")
        cv.create_oval(x, GY - 24, x + 11, GY - 10, fill="#8fd150", outline="#3f7d20")
    elif base:
        im = base.copy(); im.thumbnail((int(34 + 52 * g),) * 2)  # 최종 약 86px: 펫 몸집만 한 작물
        cab_ph.append(ImageTk.PhotoImage(im)); cv.create_image(x, GY + 4, image=cab_ph[-1], anchor="s")
    else:  # 사진이 없으면 작물 색으로 둥글게 그림
        h = 30 + 50 * g; w = h * 0.7
        cv.create_oval(x - w / 2 - 4, GY - h * .8, x + w / 2 + 4, GY + 2, fill="#6fb83a", outline="#3f7d20", width=2)
        cv.create_oval(x - w / 2, GY - h, x + w / 2, GY + 2, fill=CROPS[name][2], outline="#5a9a2a", width=2)
        cv.create_text(x, GY - h / 2, text=name, fill="#222", font=("Malgun Gothic", 9, "bold"), width=int(w))

def patch(cv, n, g, base=None, name="배추"):  # 밭: n포기, 자란 정도 g(0~1). base가 있으면 실제 작물 사진
    cv.delete("all"); cab_ph.clear()
    cv.create_oval(0, 100, 260, 130, fill="#7a5230", outline="#4a2f18", width=2)
    for i in range(n): crop_art(cv, 45 + i * 85, g, base, name)

def plant(pick=None):  # 랜덤 작물(실제 사진) 세 포기를 심고 싹 → 다 자란 작물로 키워서 수확
    global busy
    px, py = root.winfo_x(), root.winfo_y(); busy = True; g0 = gen
    name = pick if pick in CROPS else random.choice(list(CROPS)); q, shape, _, ex = CROPS[name]; key = f"__crop_{name}__"
    if q: want(key, q, 120, None, ex, shape)
    else: fails.add(key)
    fx = px + 170 if px + 170 + 260 <= SW else max(0, px + 60 - 260)  # 화면 오른쪽 끝이면 밭을 왼쪽에
    def go():
        base = random.choice(imgs[key]) if imgs.get(key) else None
        cv = []; st = []
        st.append((0, lambda: (draw("farm"), say(f"{name} 심을 거예요~"), cv.append(prop(260, 135, fx, py + 112, lambda c_: patch(c_, 0, 0, base, name))))))
        for k in range(1, 4):
            for j in range(6): st.append((350, lambda j=j: draw("farm", f=j % 2)))
            st.append((200, lambda k=k: (patch(cv[0], k, 0.1, base, name), say(f"{k}포기 심었어요!"))))
        for gr, msg in ((0.3, "싹이 났어요!"), (0.5, "쑥쑥 자라는 중~"), (0.7, "무럭무럭~"), (0.85, "거의 다 컸어요!"), (1.0, "완전히 다 자랐어요!")):
            st.append((900, lambda gr=gr, msg=msg: (patch(cv[0], 3, gr, base, name), say(msg))))
        st.append((700, lambda: (draw("happy"), say(f"대풍작이에요! {name} 수확~"))))
        st.append((3500, lambda: None))
        sequence(st, finish_act)
    def wait(i=0):
        if g0 != gen: return
        if i >= 3 and (key in imgs or key in fails or i >= 40): go(); return
        draw("rummage", f=i % 2)
        if i == 0: say(f"{name} 모종 가져올게요~")
        root.after(300, wait, i + 1)
    wait()

def setsq(nx, ny):  # 몸 비율을 바로 바꿈 (말랑 변형)
    c.scale("body", 120, 235, nx / sq[0], ny / sq[1]); sq[:] = nx, ny

def hop(tx, ty, cb=None, i=0, x0=None, y0=None, g=None):  # 통통: 포물선으로 한 번 뜀 + 착지 반동
    if g is None: g = gen; x0, y0 = root.winfo_x(), root.winfo_y()
    if g != gen: return
    n = 16; i += 1; t = i / n; te = t * t * (3 - 2 * t)  # 16등분 + 가감속
    root.geometry(f"+{round(x0 + (tx - x0) * te)}+{round(y0 + (ty - y0) * te - 40 * t * (1 - t))}")
    hh = 4 * t * (1 - t); setsq(1 - 0.05 * hh, 1 + 0.09 * hh)  # 공중에선 길쭉하게
    if i < n: root.after(18, hop, tx, ty, cb, i, x0, y0, g); return
    boing([(1.05, 0.94), (0.99, 1.02), (1, 1)], ms=60)
    if cb: cb()

def hops(n):  # 제자리에서 통통
    global busy
    if n <= 0: busy = False; return
    busy = True; g = gen
    hop(root.winfo_x(), root.winfo_y(), lambda: g == gen and root.after(70, hops, n - 1))

def goto(tx, ty, cb=None):  # 통통 뛰며 (tx,ty)까지 이동
    global busy
    g = gen; busy = True
    tx, ty = cx(tx), cy(ty)
    def step():
        global busy
        if g != gen: return  # 드래그/명령으로 취소됨
        cx, cy = root.winfo_x(), root.winfo_y(); dx, dy = tx - cx, ty - cy
        if abs(dx) <= 8 and abs(dy) <= 8:
            busy = False; save["pos"] = [cx, cy]; flush()
            if cb: cb()
            return
        hop(cx + max(-70, min(70, dx)), cy + max(-45, min(45, dy)), lambda: root.after(30, step))
    step()

def roam():  # 화면 아무 데나 계속 돌아다님
    if mode != "roam" or drag: return
    goto(random.randint(XL, XR), random.randint(YT, YB), lambda: root.after(random.randint(500, 1500), roam))

def setmode(m):
    global mode, pgen
    mode = m; pgen += 1; stopmove()

def pushup(pg, f=0, n=0):  # 엎드려 뻗쳐: 팔굽혀펴기 반복, 내려갈 때마다 숫자를 셈
    if pg != pgen or mode != "plank": return
    if not drag:
        draw("plank", f=f)
        if f: n += 1; say(f"{n}!")
    root.after(650, pushup, pg, 1 - f, n)

def done(m):  # 가만히 있기 동작 끝: 사용자가 건드려 상태가 바뀌었으면 손대지 않음
    if mood == m and mode == "auto": draw("normal"); c.delete("bub")

ACTS = {"doze": doze, "read": read_book, "game": play_game, "shower": shower, "brush": brush_teeth, "toilet": toilet, "workout": workout, "eat": meal, "coffee": coffee, "work": work, "leave": leave, "dance": breakdance, "stretch": stretch, "groove": groove, "shop": shop, "clinic": lambda: skin_clinic() or shop(), "lift": lambda: workout("dumbbell"), "run": lambda: workout("run"), "jack": lambda: workout("jack"), "rope": lambda: workout("rope")}
root.after(6000, lambda: save["aff"] >= MAX_AFF and not save.get("danced") and not busy and breakdance())  # 이미 100이면 켠 직후 한 번
brk = [time.time() + 20]  # 이 시각까지는 일만 함
def act():  # mode가 auto일 때 알아서 하는 행동: 가만히 / 통통 / 돌아다니기 / 앉기 / 휘파람 / 혼잣말
    if busy or typing or mode != "auto" or mood != "normal": root.after(8000, act); return
    k = random.choice(("still", "hop", "hop", "walk", "sit", "whistle", "talk", "talk", "gift", "doze", "read", "game", "shower", "brush", "toilet", "workout", "coffee"))
    nw = datetime.datetime.now(); mk = nw.date().isoformat() + f"-{nw.hour}"  # 9시·11시·17시에 한 번씩 밥
    if nw.hour in MEALS and mk not in save.get("meals", {}):
        save["meals"] = {k: 1 for k in save.get("meals", {}) if k.startswith(nw.date().isoformat())}; save["meals"][mk] = 1; flush()
        meal(nw.hour); root.after(random.randint(8000, 14000), act); return
    if save.get("fortune_day") != datetime.date.today().isoformat() and save["aff"] >= 3: fortune(); root.after(random.randint(8000, 14000), act); return  # 하루에 한 번 쪽지
    if root.winfo_x() > SW - 60 and not away[0]: root.geometry(f"+{SW - 340}+{root.winfo_y()}")  # 피부과 가다 끊겨 화면 밖에 남았으면 복귀
    if save["coin"] >= SNACK_COST and random.random() < 0.12: shop(); root.after(random.randint(8000, 14000), act); return  # 번 돈은 알아서 씀
    if save["aff"] >= 5 and random.random() < 0.1: bring_gift(); root.after(random.randint(20000, 30000), act); return  # 친밀도 가득 차도 가끔 주워옴
    if random.random() < 0.12: ACTS[random.choice(("groove", "stretch"))](); root.after(random.randint(8000, 14000), act); return  # 서 있다 가끔 춤·스트레칭
    if time.time() < brk[0]: k = "work"  # 평소엔 일함. 딴짓은 시간당 5번쯤 (약 8~13분마다 한 번)
    else: brk[0] = time.time() + random.randint(480, 780)
    if random.random() < 0.04: k = random.choice(("ladder", "plant"))  # 사다리·농사는 가끔만
    if k == "gift" and (save["aff"] < 5 or random.random() < 0.6): k = "talk"  # 친밀도 5 이상일 때 가끔 선물
    if k == "gift": bring_gift()
    elif k in ACTS: ACTS[k]()
    elif k == "hop": hops(random.randint(3, 5))
    elif k == "ladder": ladder()
    elif k == "plant": plant()
    elif k == "walk": goto(root.winfo_x() + random.randint(-300, 300), root.winfo_y() + random.randint(-150, 150))
    elif k == "sit": rest()
    elif k == "whistle":
        draw("whistle"); say("♪ 휘~ 휘휘~ ♬"); hearts("♪", "#4a7bd8"); root.after(1800, hearts, "♬", "#4a7bd8")
        root.after(5000, done, "whistle")
    elif k == "talk":
        say(random.choice(TALK)); root.after(5000, done, "normal")
    root.after(random.randint(8000, 14000), act)

# ---- 대화: 우클릭하면 입력창이 뜸 ----
CMDS = [  # (키워드, 동작) 위에서부터 먼저 맞는 것 적용
    (("퇴근", "집에 가", "집에가", "먼저 갈게"), "leave"), (("일해", "일하", "업무", "코딩", "야근", "출근"), "work"), (("피부과", "피부과"), "clinic"), (("스트레칭", "기지개", "체조"), "stretch"), (("막춤", "흥겨", "신나게"), "groove"), (("춤", "댄스", "브레이크", "비보이"), "dance"), (("쇼핑", "장보", "사러", "소비", "용돈"), "shop"), (("역도", "덤벨"), "lift"), (("달리기", "러닝", "조깅", "달려"), "run"), (("줄넘기",), "rope"), (("팔벌려", "점핑잭"), "jack"), (("커피", "카페", "차한잔"), "coffee"),
    (("밥", "식사", "배고", "먹자", "밥먹"), "eat"), (("샤워", "씻어", "씻자", "목욕"), "shower"), (("양치", "칫솔", "이닦"), "brush"), (("화장실", "똥", "볼일", "응가"), "toilet"), (("운동", "헬스", "덤벨", "근육"), "workout"),
    (("운세", "쪽지", "점쳐", "오늘의운"), "fortune"), (("졸아", "졸려", "자라", "낮잠", "꾸벅"), "doze"), (("책읽", "독서", "책봐"), "read"), (("게임", "겜"), "game"),
    (("뒤돌", "맴매", "때찌", "벌서", "혼나", "사과"), "sorry"),
    (("가만", "멈춰", "정지", "그만"), "still"), (("엎드", "푸시업", "팔굽"), "plank"), (("앉",), "sit"),
    (("일어", "서봐", "서있"), "stand"), (("돌아다", "움직", "뛰어다", "놀러", "산책"), "roam"),
    (("통통", "점프", "폴짝", "뛰어"), "hop"), (("휘파람",), "whistle"),
    (("쉬어", "쉴까", "휴식", "쉬자"), "rest"), (("사다리", "올라가"), "ladder"), (("배추", "농사", "심어", "밭", "작물", "재배", "키워", "기르", "가꿔", "가꾸", "수확", "텃밭", "씨앗", "모종"), "plant"), (("안녕", "하이", "반가"), "hi"), (("사랑", "좋아", "잘했", "고마", "최고", "귀여"), "love"),
]
def qa(text):  # 간단한 질문에 답 (없으면 None)
    t = text.replace(" ", ""); now = datetime.datetime.now()
    m = re.search(r"\(?\d[\d\s+\-*/().x×÷]*\d\)?", text)
    if m:
        e = m.group().replace("x", "*").replace("×", "*").replace("÷", "/")
        if any(o in e for o in "+-*/") and "**" not in e and len(e) < 40:
            try: r = eval(e, {"__builtins__": {}}); return f"{m.group().strip()} = {round(r, 4):g}이에요!"
            except Exception: return "음… 그건 계산이 안 돼요 😵"
    if any(k in t for k in ("몇시", "시간")): return f"지금은 {now:%H시 %M분}이에요!"
    if any(k in t for k in ("며칠", "날짜", "요일")): return f"오늘은 {now:%Y년 %m월 %d일} {'월화수목금토일'[now.weekday()]}요일이에요!"
    if any(k in t for k in ("이름", "누구")): return "저는 Claude예요! 당신 곁에서 코딩 도와주는 작은 펫이에요 🧡"
    if any(k in t for k in ("친밀도", "호감")): return f"친밀도는 {save['aff']}/{MAX_AFF}이에요. 쓰다듬어 주세요 🥺"
    if any(k in t for k in ("옷", "입고", "입었", "선물", "가진", "주머니", "인벤", "가방")):
        bag(); return "가방을 열었어요! 옷은 눌러서 마음대로 입히고 벗길 수 있어요."
    if any(k in t for k in ("기분", "어때")): return "기분 최고예요! 💕" if save["aff"] >= 30 else "나쁘지 않아요… 쓰담쓰담 해주면 더 좋아질 듯!"
    if any(k in t for k in ("도움", "뭐할수", "명령", "할수있")):
        return "이렇게 말해보세요!\n가만있어 / 앉아 / 엎드려 / 뒤돌아 / 일어나 / 돌아다녀 / 통통 / 휘파람 / 쉬어 / 사다리 / 배추\n몇 시야? / 오늘 며칠? / 1+1은? / 친밀도 / 가방(장비·선물)"
    return None

chatq = queue.Queue(); chatting = [False]
def think(i):  # 고민 중: 머리 위 구름 말풍선 + 점이 차례로 깜빡이는 로딩
    c.delete("think")
    if not chatting[0]: return
    o = dict(tags="think")
    cl = ((60, 36, 108, 80), (92, 22, 150, 70), (128, 34, 182, 80), (76, 50, 166, 90))
    for x0, y0, x1, y1 in cl: c.create_oval(x0, y0, x1, y1, fill="white", outline="#8a8a8a", width=2, **o)
    for x0, y0, x1, y1 in cl: c.create_oval(x0 + 3, y0 + 3, x1 - 3, y1 - 3, fill="white", outline="", **o)
    c.create_oval(116, 92, 128, 103, fill="white", outline="#8a8a8a", width=2, **o); c.create_oval(121, 104, 127, 110, fill="white", outline="#8a8a8a", **o)
    c.create_text(120, 52, text="생각 중", font=("Malgun Gothic", 10, "bold"), fill="#555", **o)
    for k in range(3): c.create_oval(104 + 14 * k, 64 - (4 if i % 3 == k else 0), 112 + 14 * k, 72 - (4 if i % 3 == k else 0), fill="#555" if i % 3 == k else "#bbb", outline="", **o)
    root.after(350, think, i + 1)
CHAT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat")
def chat(text):  # 모르는 말: claude -p 를 같은 세션(--resume)으로 이어서 호출. 대화 내용이 계속 기억됨
    if chatting[0]: speak("잠깐만요, 아직 생각 중이에요… 🤔", 3000); return
    chatting[0] = True; c.delete("bub"); think(0); sid = save.get("chat_sid")
    def run():
        import subprocess, shutil
        try:
            os.makedirs(CHAT_DIR, exist_ok=True)
            cmd = [shutil.which("claude") or "claude", "-p", text, "--output-format", "json", "--model", "haiku", "--tools", "",
                   "--append-system-prompt", "너는 사용자의 데스크톱 펫 '클로드'다. 귀엽고 다정한 말투로 한국어 3~5문장, 300자 이내로 충분히 자세히 답한다. 도구는 쓸 수 없다."]
            if sid: cmd += ["--resume", sid]
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=120, cwd=CHAT_DIR, env=dict(os.environ, PET_CHAT="1"), creationflags=0x08000000)
            j = json.loads(r.stdout); chatq.put((j.get("session_id"), (j.get("result") or "").strip() or "음… 할 말을 못 찾았어요"))
        except Exception as e:
            chatq.put((None, "앗, 지금은 대답을 못 하겠어요 (" + type(e).__name__ + ")"))
    threading.Thread(target=run, daemon=True).start()

def talk(text):
    r = qa(text)
    if r: speak(r, 7000); return
    t = text.replace(" ", ""); a_ = next((a for ks, a in CMDS if any(k in t for k in ks)), None)
    if a_ == "still": setmode("still"); draw("normal"); speak("넵! 가만히 있을게요")
    elif a_ == "sit": setmode("sit"); draw("sit"); speak("넵! 앉았어요")
    elif a_ == "plank": setmode("plank"); say("넵! 엎드려 뻗쳐! 하나~"); pushup(pgen)
    elif a_ == "stand": setmode("auto"); draw("normal"); speak("넵! 일어났어요")
    elif a_ == "roam": setmode("roam"); draw("normal"); speak("넵! 돌아다닐게요~"); roam()
    elif a_ == "hop": setmode("auto"); draw("normal"); speak("통통통!"); hops(4)
    elif a_ == "whistle":
        setmode("auto"); draw("whistle"); say("♪ 휘~ 휘휘~ ♬"); hearts("♪", "#4a7bd8"); root.after(5000, done, "whistle")
    elif a_ == "fortune": setmode("auto"); draw("normal"); fortune()
    elif a_ in ACTS: setmode("auto"); draw("normal"); ACTS[a_]()
    elif a_ == "rest": setmode("auto"); draw("normal"); rest()
    elif a_ == "ladder": setmode("auto"); draw("normal"); ladder()
    elif a_ == "plant": setmode("auto"); draw("normal"); plant()
    elif a_ == "sorry": setmode("auto"); show(random.choice(SORRY), "sorry")  # 뒤돌아 엉덩이를 내밂 (클릭하면 때찌)
    elif a_ == "hi": speak("안녕하세요! 오늘도 같이 힘내요 🙌")
    elif a_ == "love": hearts(); speak("헤헤 저도요~ 💕")
    else: chat(text)  # 모르는 말은 하나의 클로드 세션에 이어서 물어봄

typing = False
def ask(e=None):  # 우클릭: 머리 위 말풍선이 입력칸으로 바뀜 (커서 깜빡임). Enter=보내기, Esc=취소
    global typing
    if typing: return
    typing = True; c.delete("bub")
    x0, y0, x1, y1 = 22, 70, 218, 104
    c.create_polygon(112, y1 - 1, 128, y1 - 1, 120, y1 + 13, fill="white", outline="", tags="chat")
    c.create_line(112, y1, 120, y1 + 13, 128, y1, fill="#888", tags="chat")
    c.create_polygon(x0+10, y0, x1-10, y0, x1, y0, x1, y0+10, x1, y1-10, x1, y1, x1-10, y1, x0+10, y1, x0, y1, x0, y1-10, x0, y0+10, x0, y0,
                     smooth=True, fill="white", outline="#888", tags="chat")
    c.create_line(113, y1, 127, y1, fill="white", width=2, tags="chat")
    en = tk.Entry(c, width=24, bd=0, bg="white", fg="#222", font=("Malgun Gothic", 10), highlightthickness=0,
                  insertbackground="#222", insertwidth=2, insertontime=500, insertofftime=350)
    c.create_window(120, 87, window=en, tags="chat")
    def close(_=None):
        global typing
        typing = False; c.delete("chat"); en.destroy()
    def send(_=None):
        t = en.get().strip(); close()
        if t: talk(t)
    en.bind("<Return>", send); en.bind("<Escape>", close)
    root.after(400, lambda: en.winfo_exists() and en.bind("<FocusOut>", close))  # 다른 데 클릭하면 닫힘
    root.after(50, lambda: (root.focus_force(), en.focus_force()))
def do_act(k):  # 메뉴에서 고른 동작: 하던 걸 멈추고 바로 시작
    if drag or typing: return
    stopmove(); setmode("auto"); draw("normal")
    (fortune if k == "fortune" else ACTS[k])()
def set_skin(i):  # 피부톤 변경: 몸·팔다리·테두리 색을 바꾸고 바로 다시 그림
    global ORANGE, OUTL
    ORANGE = SKINS[i][1]; OUTL = darker(ORANGE, 0.66); save["skin"] = i; flush(); draw(pose()); say(f"피부톤을 {SKINS[i][0]}으로 바꿨어요!")

def rmenu(e):  # 우클릭: 목록에서 고르기
    m = tk.Menu(root, tearoff=0, font=("Malgun Gothic", 10))
    sk = tk.Menu(m, tearoff=0, font=("Malgun Gothic", 10))
    for i, (nm, col) in enumerate(SKINS): sk.add_command(label=("● " if i == save.get("skin", 0) else "○ ") + nm, command=lambda i=i: set_skin(i))
    m.add_cascade(label="🎨 피부톤", menu=sk)
    m.add_command(label="💬 말 걸기", command=ask); m.add_command(label="🎒 인벤토리", command=bag); m.add_separator()
    for lb, k in (("💻 일하기", "work"), ("🏠 퇴근하기", "leave"), ("🏋 운동하기", "workout"), ("☕ 커피 마시기", "coffee"), ("📖 책 읽기", "read"), ("🎮 게임하기", "game"), ("😴 졸기", "doze"), ("🍚 밥 먹기", "eat"), ("🚿 샤워하기", "shower"), ("🔮 오늘의 운세", "fortune"), ("🕺 브레이크댄스", "dance")):
        m.add_command(label=lb, command=lambda k=k: do_act(k))
    try: m.tk_popup(e.x_root, e.y_root)
    finally: m.grab_release()
c.bind("<Button-3>", rmenu)

st = dict(x=None, dir=0, rev=0, t=0.0)
def motion(e):  # 머리 쪽에서 좌우로 6번 방향을 바꾸면 쓰담쓰담
    ex, ey = conv(e); now = time.time()
    if drag: return
    if mood in ("sorry", "hit"):  # 뒤돌아 있을 땐 손 대신 방망이
        hand_hide()
        if 40 < ex < 200 and 90 < ey < 240: bat_show(e.x_root, e.y_root, 900)
        else: bat_hide()
        return
    bat_hide()
    if not (40 < ex < 200 and 90 < ey < 140): st.update(x=None, dir=0, rev=0); hand_hide(); return
    hand_show(e.x_root, e.y_root, 700)  # 쓰다듬는 손
    if now - st["t"] > 0.8: st.update(x=None, dir=0, rev=0)
    st["t"] = now
    if st["x"] is None: st["x"] = e.x; return
    dx = e.x - st["x"]
    if abs(dx) < 4: return
    d = 1 if dx > 0 else -1
    if st["dir"] and d != st["dir"]: st["rev"] += 1
    st["dir"], st["x"] = d, e.x
    if st["rev"] >= 6:
        st.update(x=None, dir=0, rev=0); pet()
c.bind("<Motion>", motion)

DONE = ["클로드가 일 다 끝냈대요! 확인해 보세요~ 🎉", "작업 완료! 이제 와서 봐주세요~", "다 됐어요! 칭찬해 주세요 😊"]
cmds = queue.Queue()
HTTPServer.allow_reuse_address = False  # 윈도우에선 True면 중복 실행이 같은 포트를 같이 잡음
class H_(BaseHTTPRequestHandler):
    def do_GET(self):
        cmds.put(self.path.strip("/")); self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
    def log_message(self, *a): pass
def serve():
    HTTPServer(("127.0.0.1", 47321), H_).serve_forever()  # 로컬 전용
threading.Thread(target=serve, daemon=True).start()

def poll():
    while not IMGQ.empty():
        n, im = IMGQ.get()
        if n == "__chair__": chair_cache.append(im) if im else chair_failed.append(1)
        elif n == "__ladder__" or n.startswith("__crop_"): pending.discard(n); imgs.setdefault(n, []).append(im) if im else fails.add(n)
        elif n.startswith("__icon__"):
            if im is not None and min(im.size) >= 30: im.thumbnail((110, 110)); im.save(icon_path(n[8:]))  # 너무 작게 오려진 건 버림
            if len(bagwin) > 1 and bagwin[0] and bagwin[0].winfo_exists(): bagwin[1]()
        elif n.startswith("__outfit__"): give(n[10:], True, im)
        else: give(n, False, im)
    while not chatq.empty():
        sid_, ans = chatq.get(); chatting[0] = False; c.delete("think")
        if sid_ and sid_ != save.get("chat_sid"): save["chat_sid"] = sid_; flush()
        if len(ans) > 70: sticky("클로드의 답변", ans); speak("길어서 쪽지로 적었어요~", 8000)  # 말풍선엔 안 들어가는 긴 답
        else: speak(ans, max(15000, 200 * len(ans)))  # 짧은 답은 말풍선으로, 길수록 오래
    while not cmds.empty():
        k = cmds.get()
        if k == "sorry": setmode("auto"); show(random.choice(SORRY), "sorry")
        elif k == "hi": show("안녕하세요! 오늘도 같이 힘내요 🙌", "happy")
        elif k.split("?")[0] == "done":  # 클로드 세션 작업 완료 알림 (Stop 훅에서 호출, ?t=세션제목)
            t = urllib.parse.parse_qs(k.partition("?")[2]).get("t", [""])[0]
            setmode("auto"); show((f"[{t}] 세션 작업 끝났어요! 확인해 보세요~ 🎉" if t else random.choice(DONE)), "happy", keep=20000)  # 다른 말풍선과 겹치지 않게 20초만
            try: import winsound; winsound.MessageBeep()
            except Exception: pass
        elif k.startswith("plant?"): setmode("auto"); draw("normal"); plant(urllib.parse.parse_qs(k[6:]).get("n", [""])[0])  # 예: /plant?n=퇴계 이황
        elif k == "fortune": setmode("auto"); draw("normal"); fortune()
        elif k in ACTS: setmode("auto"); draw("normal"); ACTS[k]()
        elif k in ("ladder", "plant", "rest", "doze", "read", "game"): setmode("auto"); draw("normal"); {"ladder": ladder, "plant": plant, "rest": rest, "doze": doze, "read": read_book, "game": play_game}[k]()
        elif k.startswith("batv"): bat_show(*root.winfo_pointerxy(), 3000, int(k[4:]))  # 방망이 동작 확인용
        elif k == "bag": bag()  # 가방 열기
        elif k == "quit": root.destroy(); return
    root.after(200, poll)

draw("normal"); poll(); root.after(8000, act); root.mainloop()
