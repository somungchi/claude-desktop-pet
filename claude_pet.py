"""Claude 펫: 화면 오른쪽 밖에서 튀어나와 사과하는 데스크톱 마스코트.
실행: pythonw claude_pet.py   (콘솔 없이)  /  python claude_pet.py
호출: curl http://127.0.0.1:47321/sorry   (사과하며 등장)  /hi (인사)  /quit (종료)
상주 중엔 가끔 앉거나 휘파람 불거나 혼잣말함. 대화: 펫을 우클릭하면 입력창(가만있어/앉아/엎드려/돌아다녀/일어나/통통 등). 조작: 머리를 잡고 끌면 원하는 곳에 둠, 가끔 좌우로 저벅저벅 걸음. 머리 쪽에서 마우스를 좌우로 왔다갔다 = 쓰담쓰담(친밀도+3), 뒤돌았을 때 엉덩이 클릭 = 때찌(아야!)
"""
import datetime, io, json, os, queue, random, re, threading, time, tkinter as tk
import urllib.parse, urllib.request
try:
    from PIL import Image, ImageDraw, ImageTk  # 선물 이미지용 (없으면 이모지로 대체)
except ImportError:
    Image = None
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
SAVE = os.path.join(HERE, "pet_save.json")
MAX_AFF = 100
GIFT_EVERY = 20  # 친밀도가 이 값의 배수를 넘을 때마다 선물
GIFTS = [("황금 목걸이", "gold necklace"), ("지렁이", "earthworm"), ("꿀사과", "honeycrisp apple"),
         ("황금 변기", "golden toilet"), ("초대형 오리 인형", "rubber duck"), ("감자", "potato"),
         ("마른 멸치", "dried anchovy"), ("우승 트로피", "trophy"), ("금괴", "gold bar"), ("도넛", "donut"),
         ("컵라면", "instant noodles cup"), ("후라이드 치킨", "fried chicken"), ("피자 한 판", "pizza"),
         ("공룡 화석", "dinosaur fossil"), ("삽", "shovel"), ("고구마", "sweet potato"),
         ("두루마리 휴지", "toilet paper roll"), ("다이아몬드", "diamond")]  # 선물 이미지는 Wikimedia Commons 검색
OUTFITS = ["밀짚모자", "선글라스", "중절모", "티아라"]  # 옷은 그림으로 그림 (사진은 어색해서 안 씀)
PLACES = ["길가 쓰레기통에서", "옆집 빨랫줄에서", "분실물 센터에서", "택배 상자 밑에서", "공원 벤치에서", "제 주머니를 뒤졌더니"]
SORRY = ["죄송해요… 제가 실수했어요 ㅠㅠ", "앗, 제가 틀렸어요. 벌 받을게요!", "잘못했어요… 엉덩이 때찌 해주세요 🥺"]
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
px, py = save.get("pos", [SW - W, Y])
px, py = max(0, min(SW - W, px)), max(0, min(SH - H, py))  # 화면 밖에 저장돼 있으면 안으로
root.geometry(f"{W}x{H}+{px}+{py}")  # 항상 화면에 상주
hide_id, mood, busy = None, "normal", False
mode, gen, pgen = "auto", 0, 0  # mode: auto(알아서) / roam(계속 움직임) / still / sit / plank  # busy: 끄는 중이거나 걷는 중
ORANGE, DARK = "#D97757", "#3b2a22"
sq = [1.0, 1.0]  # 말랑 변형(가로, 세로 배율)

def rrect(x0, y0, x1, y1, r=8, **kw):  # 모서리가 둥근 사각형 (smooth 다각형)
    pts = [x0+r, y0, x1-r, y0, x1, y0, x1, y0+r, x1, y1-r, x1, y1, x1-r, y1, x0+r, y1, x0, y1, x0, y1-r, x0, y0+r, x0, y0]
    return c.create_polygon(pts, smooth=True, **kw)

def limbs(m, f, arm):  # 팔다리 위치. struggle(잡혀서 발버둥)이면 프레임 f에 따라 번갈아 휘두름
    if m in ("struggle", "climb", "farm", "rummage"):
        return [(40, 100, 62, 130) if f == 0 else (40, 150, 62, 180),
                (178, 150, 200, 180) if f == 0 else (178, 100, 200, 130),
                (66, 205, 88, 234) if f == 0 else (90, 200, 112, 224),
                (152, 200, 174, 224) if f == 0 else (128, 205, 150, 234)]
    return [(40, 130, 62, 160), arm, (80, 200, 102, 232), (138, 200, 160, 232)]

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
        c.create_polygon([v for px, py in pts for v in (x + px, y + py)], fill="#5aa9e6", outline=DARK, width=2, **o)
        c.create_line(x - 3, y - 12, x, y - 8, x + 3, y - 12, fill=DARK, width=2, **o)
    else:
        c.create_rectangle(x - 15, y - 8, x + 15, y + 14, fill="#ff6b6b", outline=DARK, width=2, **o)
        c.create_rectangle(x - 17, y - 14, x + 17, y - 6, fill="#ff8f8f", outline=DARK, width=2, **o)
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
    path = os.path.join(OUTFIT_DIR, n + ".png")
    if not (Image and os.path.exists(path)): return None
    im = Image.open(path).convert("RGBA"); w = max(1, int(OUTFIT_SPEC[n][0] * S)); h = max(1, int(im.height * w / im.width))
    worn_ph[n] = ImageTk.PhotoImage(im.resize((w, h), Image.LANCZOS)); return worn_ph[n]

def wear(o, front):  # 입은 옷: 사진 누끼 우선, 없으면 그림 (선글라스는 앞모습일 때만)
    for n in save["outfit"]:
        ph = worn_image(n)
        if ph:
            if not (n == "선글라스" and not front):
                _, anchor, x, y = OUTFIT_SPEC[n]; c.create_image(x, y, image=ph, anchor=anchor, **o)
            continue
        if n == "밀짚모자":  # 챙 넓은 밀짚모자: 챙 + 둥근 머리 + 빨간 띠 + 결
            c.create_oval(58, 84, 182, 106, fill="#e8c874", outline=DARK, width=2, **o)
            c.create_arc(86, 54, 154, 100, start=0, extent=180, style="chord", fill="#f0d58a", outline=DARK, width=2, **o)
            c.create_rectangle(87, 84, 153, 92, fill="#c0392b", outline=DARK, **o)
            for x in range(92, 150, 10): c.create_line(x, 62 + abs(x - 120) // 4, x, 82, fill="#d4b05c", **o)
        elif n == "중절모":  # 챙 + 눌린 크라운 + 검은 띠
            c.create_oval(72, 86, 168, 102, fill="#55555f", outline=DARK, width=2, **o)
            c.create_polygon(92, 90, 92, 66, 104, 58, 120, 66, 136, 58, 148, 66, 148, 90, fill="#6b6b78", outline=DARK, width=2, **o)
            c.create_rectangle(92, 80, 148, 90, fill="#222", outline=DARK, **o)
            c.create_rectangle(134, 78, 144, 92, fill="#c0392b", outline=DARK, **o)
        elif n == "티아라":  # 작은 은색 티아라 + 보석
            c.create_polygon(94, 90, 98, 74, 108, 84, 120, 64, 132, 84, 142, 74, 146, 90, fill="#e8e8f0", outline=DARK, width=2, **o)
            c.create_rectangle(94, 88, 146, 95, fill="#cfcfe0", outline=DARK, width=2, **o)
            c.create_oval(115, 67, 125, 77, fill="#ff5d8f", outline=DARK, **o)
            for gx in (98, 142): c.create_oval(gx - 3, 71, gx + 3, 77, fill="#5ab4f0", outline=DARK, **o)
        elif n == "선글라스" and front:  # 번쩍이는 렌즈 + 다리
            c.create_line(84, 122, 62, 118, fill="#222", width=3, **o); c.create_line(156, 122, 178, 118, fill="#222", width=3, **o)
            c.create_oval(82, 112, 108, 138, fill="#1a1a1a", outline="#555", width=2, **o)
            c.create_oval(132, 112, 158, 138, fill="#1a1a1a", outline="#555", width=2, **o)
            c.create_arc(106, 114, 134, 130, start=0, extent=180, style="arc", width=3, outline="#222", **o)
            for gx in (89, 139): c.create_line(gx, 118, gx + 6, 114, fill="white", width=2, **o)

def draw(m, gift=None, f=0):
    if m == "plank": return draw_plank(f)
    global mood; mood = m
    c.delete("body")
    o = dict(tags="body")
    arm = (178, 122, 226, 142) if gift else (178, 130, 200, 160)  # 선물 줄 땐 팔을 쭉 뻗음
    for box in limbs(m, f, arm):
        rrect(*box, r=10, fill=ORANGE, outline=DARK, width=2, **o)
    rrect(60, 90, 180, 205, r=24, fill=ORANGE, outline=DARK, width=2, **o)
    if m == "sit":  # 앉기: 다리를 앞으로 뻗음
        c.delete("body"); o = dict(tags="body")
        for box in [(40, 130, 62, 160), (178, 130, 200, 160), (62, 205, 112, 222), (128, 205, 178, 222)]:
            rrect(*box, r=10, fill=ORANGE, outline=DARK, width=2, **o)
        rrect(60, 90, 180, 205, r=24, fill=ORANGE, outline=DARK, width=2, **o)
    front = m not in ("sorry", "hit", "climb")
    if not front:  # 뒤돌아서 엉덩이를 내밀기 (얼굴 없음)
        if m != "climb":  # 사다리 오를 땐 뒷모습만 (엉덩이 볼터치 없음)
            c.create_oval(66, 140, 120, 205, fill="#f4a7a0", outline=DARK, width=2, **o)
            c.create_oval(120, 140, 174, 205, fill="#f4a7a0", outline=DARK, width=2, **o)
        if m == "hit":
            anger(120, 172, o)
    else:
        for ex in (95, 145):
            if m == "struggle":  # > <
                k = 1 if ex < 120 else -1
                c.create_line(ex-8*k, 114, ex+8*k, 125, ex-8*k, 136, width=3, fill=DARK, **o)
            elif m == "happy":  # ^ ^
                c.create_arc(ex-9, 118, ex+9, 142, start=0, extent=180, style="arc", width=3, outline=DARK, **o)
            else:
                c.create_oval(ex-6, 118, ex+6, 138, fill=DARK, **o)
        if m == "whistle":  # 휘파람 입
            c.create_oval(113, 146, 127, 160, fill=DARK, **o)
    if m == "struggle":  # 머리 꼬집힘: 머리 위가 쭉 늘어남 + 벌린 입
        c.create_polygon(100, 92, 120, 62, 140, 92, fill=ORANGE, outline=DARK, width=2, **o)
        c.create_line(101, 91, 139, 91, fill=ORANGE, width=3, **o)
        c.create_oval(110, 144, 130, 164, fill="#7a2e2e", outline=DARK, **o)
        anger(152, 74, o)
    if m == "farm":  # 괭이질
        y = 25 * f
        c.create_line(205, 108 + y, 232, 160 + y, width=4, fill="#8b5a2b", **o)
        c.create_polygon(226, 156 + y, 246, 160 + y, 238, 172 + y, fill="#b0b0b0", outline=DARK, **o)
    wear(o, front)
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
        rrect(*box, r=10, fill=ORANGE, outline=DARK, width=2, **o)
    rrect(50, 160 + d, 180, 202 + d, r=18, fill=ORANGE, outline=DARK, width=2, **o)
    c.create_line(150, 172 + d, 162, 180 + d, 150, 188 + d, width=3, fill=DARK, **o)  # > 힘든 눈
    sweat(192, 150 + d, o)
    finish()

sayn = 0
def speak(msg, ms=5000):  # 말하고 잠시 뒤 말풍선 지움 (그 사이 다른 말이 나왔으면 건드리지 않음)
    say(msg); n = sayn; root.after(ms, lambda: sayn == n and c.delete("bub"))

def say(msg):  # 머리 바로 위에 꼬리 달린 둥근 말풍선
    global sayn; sayn += 1
    msg = re.sub(r"[\U00010000-\U0010ffff\ufe0f]", "", msg).strip()  # 이모지는 깨져서 뺌
    c.delete("bub")
    t = c.create_text(120, 100, anchor="s", text=msg, width=190, font=("Malgun Gothic", 10), tags="bub")
    x0, y0, x1, y1 = c.bbox(t); x0, y0, x1, y1 = x0-9, y0-6, x1+9, y1+6; r = 10
    c.create_polygon(112, y1-1, 128, y1-1, 120, y1+13, fill="white", outline="", tags="bub")
    c.create_line(112, y1, 120, y1+13, 128, y1, fill="#888", tags="bub")
    bg = c.create_polygon(x0+r, y0, x1-r, y0, x1, y0, x1, y0+r, x1, y1-r, x1, y1, x1-r, y1, x0+r, y1, x0, y1,
                          x0, y1-r, x0, y0+r, x0, y0, smooth=True, fill="white", outline="#888", tags="bub")
    c.create_line(113, y1, 127, y1, fill="white", width=2, tags="bub")
    c.tag_lower(bg, t)
    c.tag_raise(t)

def show(msg, m, gift=None):
    global hide_id
    draw(m, gift); say(msg)
    if hide_id: root.after_cancel(hide_id)
    hide_id = root.after(60000 if m in ("sorry", "hit") else 9000, hide)

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
        save["outfit"].append(item); draw("happy"); flush()
    def done():
        c.delete("giftimg")
        if outfit:
            say("잠깐만요, 갈아입고 올게요! (탈의실)")
            curtain(swap, lambda: say(f"짜잔~ {item} 입어봤어요! 어때요?"))
        else:
            save["inv"][item] = save["inv"].get(item, 0) + 1; draw("happy"); say(f"{item}, 잘 간직해 주세요!"); flush()
    root.after(3500, done)

def pet():
    before = save["aff"] // GIFT_EVERY
    save["aff"] = min(MAX_AFF, save["aff"] + 1)
    hearts()
    if save["aff"] // GIFT_EVERY > before:
        left = [x for x in OUTFITS if x not in save["outfit"]]
        if left and random.random() < 0.5:
            n = random.choice(left)
            if Image: speak("앗, 입을 걸 주워왔어요… 잠깐만요!"); fetch_gift("__outfit__" + n, OUTFIT_Q[n], 300, None, OUTFIT_EX, OUTFIT_SHAPE[n])
            else: give(n, True)
        elif Image:
            name, q = random.choice(GIFTS); speak("앗, 뭔가 주워왔어요… 잠깐만요!"); fetch_gift(name, q)
        else: give(random.choice(GIFTS)[0], False)
    else:
        show(random.choice(PET), "happy")
    flush()

drag = {}
def press(e):
    ex, ey = conv(e)
    if mood in ("sorry", "hit") and 40 < ex < 200 and 140 < ey < 235:  # 엉덩이 때찌
        show(random.choice(HIT), "hit")
        root.after(1200, lambda: draw("sorry"))
    elif 40 < ex < 200 and 90 < ey < 140:  # 머리채 잡기
        global busy
        stopmove(); busy = True
        drag.update(mx=e.x_root, my=e.y_root, x=root.winfo_x(), y=root.winfo_y(), m=mood)
        flail()
def move(e):
    global busy
    if not drag: return
    busy = True
    nx = max(0, min(SW - W, drag["x"] + e.x_root - drag["mx"]))
    ny = max(0, min(SH - H, drag["y"] + e.y_root - drag["my"]))
    root.geometry(f"+{nx}+{ny}")
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
        prev = drag["m"]; drag.clear(); busy = False
        save["pos"] = [root.winfo_x(), root.winfo_y()]; flush()
        sq[:] = [1.0, 1.0]; draw("sorry" if prev in ("sorry", "hit") else pose()); boing(LAND)
        if mode == "roam": roam()
c.bind("<Button-1>", press); c.bind("<B1-Motion>", move); c.bind("<ButtonRelease-1>", release)

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
    want("__ladder__", "wooden ladder", 230, lambda im: im.height > im.width * 1.2)
    def go():
        im = random.choice(imgs["__ladder__"]) if imgs.get("__ladder__") else None
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
    def wait(i=0):
        if g != gen: return
        if i >= 3 and ("__ladder__" in imgs or "__ladder__" in fails or i >= 40): go(); return
        draw("rummage", f=i % 2)
        if i == 0: say("사다리 가져올게요~")
        root.after(300, wait, i + 1)
    wait()

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
              (4500, lambda: say(random.choice(TALK))),
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
def cabbage_art(cv, x, g, base):  # 배추 한 포기: g<=0.2 싹 → 점점 커져서 g=1.0이면 다 자란 배추
    if g <= 0.2:
        cv.create_line(x, GY, x, GY - 12, width=3, fill="#4f8f2a")
        cv.create_oval(x - 11, GY - 20, x, GY - 8, fill="#7ac143", outline="#3f7d20")
        cv.create_oval(x, GY - 24, x + 11, GY - 10, fill="#8fd150", outline="#3f7d20")
    elif base:
        im = base.copy(); im.thumbnail((int(34 + 52 * g),) * 2)  # 최종 약 86px: 펫 몸집만 한 완전한 배추
        cab_ph.append(ImageTk.PhotoImage(im)); cv.create_image(x, GY + 4, image=cab_ph[-1], anchor="s")
    else:  # 사진이 없으면 길쭉한 배추를 그림
        h = 30 + 50 * g; w = h * 0.7
        cv.create_oval(x - w / 2 - 4, GY - h * .8, x + w / 2 + 4, GY + 2, fill="#6fb83a", outline="#3f7d20", width=2)
        cv.create_oval(x - w / 2, GY - h, x + w / 2, GY + 2, fill="#cbe99a", outline="#5a9a2a", width=2)
        cv.create_oval(x - w / 3, GY - h * .95, x + w / 3, GY - 4, fill="#eef8d0", outline="")
        cv.create_line(x, GY - h * .9, x, GY - 2, fill="#8fb85a")

def patch(cv, n, g, base=None):  # 배추밭: n포기, 자란 정도 g(0~1). base가 있으면 실제 배추 사진
    cv.delete("all"); cab_ph.clear()
    cv.create_oval(0, 100, 260, 130, fill="#7a5230", outline="#4a2f18", width=2)
    for i in range(n): cabbage_art(cv, 45 + i * 85, g, base)

def plant():  # 배추(실제 사진) 세 포기를 심고 싹 → 완전한 배추로 키워서 수확
    global busy
    px, py = root.winfo_x(), root.winfo_y(); busy = True; g0 = gen
    want("__cabbage__", "napa cabbage", 120, None, " -seedling -seed -field -plant -garden -flower", (0.6, 1.8))
    fx = px + 170 if px + 170 + 260 <= SW else max(0, px + 60 - 260)  # 화면 오른쪽 끝이면 밭을 왼쪽에
    def go():
        base = random.choice(imgs["__cabbage__"]) if imgs.get("__cabbage__") else None
        cv = []; st = []
        st.append((0, lambda: (draw("farm"), say("배추 심을 거예요~"), cv.append(prop(260, 135, fx, py + 112, lambda c_: patch(c_, 0, 0, base))))))
        for k in range(1, 4):
            for j in range(6): st.append((350, lambda j=j: draw("farm", f=j % 2)))
            st.append((200, lambda k=k: (patch(cv[0], k, 0.1, base), say(f"{k}포기 심었어요!"))))
        for gr, msg in ((0.3, "싹이 났어요!"), (0.5, "쑥쑥 자라는 중~"), (0.7, "무럭무럭~"), (0.85, "거의 다 컸어요!"), (1.0, "완전히 다 자랐어요!")):
            st.append((900, lambda gr=gr, msg=msg: (patch(cv[0], 3, gr, base), say(msg))))
        st.append((700, lambda: (draw("happy"), say("대풍작이에요! 배추 수확~"))))
        st.append((3500, lambda: None))
        sequence(st, finish_act)
    def wait(i=0):
        if g0 != gen: return
        if i >= 3 and ("__cabbage__" in imgs or "__cabbage__" in fails or i >= 40): go(); return
        draw("rummage", f=i % 2)
        if i == 0: say("배추 모종 가져올게요~")
        root.after(300, wait, i + 1)
    wait()

def hop(tx, ty, cb=None, i=0, x0=None, y0=None, g=None):  # 통통: 포물선으로 한 번 뜀 + 착지 반동
    if g is None: g = gen; x0, y0 = root.winfo_x(), root.winfo_y(); boing([(0.97, 1.04), (1, 1)], ms=50)
    if g != gen: return
    n = 8; i += 1; t = i / n
    root.geometry(f"+{round(x0 + (tx - x0) * t)}+{round(y0 + (ty - y0) * t - 40 * t * (1 - t))}")
    if i < n: root.after(35, hop, tx, ty, cb, i, x0, y0, g); return
    boing([(1.05, 0.94), (0.99, 1.02), (1, 1)], ms=60)
    if cb: cb()

def hops(n):  # 제자리에서 통통
    global busy
    if n <= 0: busy = False; return
    busy = True; g = gen
    hop(root.winfo_x(), root.winfo_y(), lambda: g == gen and root.after(120, hops, n - 1))

def goto(tx, ty, cb=None):  # 통통 뛰며 (tx,ty)까지 이동
    global busy
    g = gen; busy = True
    tx, ty = max(0, min(SW - W, tx)), max(0, min(SH - H, ty))
    def step():
        global busy
        if g != gen: return  # 드래그/명령으로 취소됨
        cx, cy = root.winfo_x(), root.winfo_y(); dx, dy = tx - cx, ty - cy
        if abs(dx) <= 8 and abs(dy) <= 8:
            busy = False; save["pos"] = [cx, cy]; flush()
            if cb: cb()
            return
        hop(cx + max(-70, min(70, dx)), cy + max(-45, min(45, dy)), lambda: root.after(100, step))
    step()

def roam():  # 화면 아무 데나 계속 돌아다님
    if mode != "roam" or drag: return
    goto(random.randint(0, SW - W), random.randint(0, SH - H), lambda: root.after(random.randint(500, 1500), roam))

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

def act():  # mode가 auto일 때 알아서 하는 행동: 가만히 / 통통 / 돌아다니기 / 앉기 / 휘파람 / 혼잣말
    if busy or typing or mode != "auto" or mood != "normal": root.after(8000, act); return
    k = random.choice(("still", "hop", "hop", "walk", "sit", "whistle", "talk", "talk", "ladder", "plant"))
    if k == "hop": hops(random.randint(3, 5))
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
    (("가만", "멈춰", "정지", "그만"), "still"), (("엎드", "푸시업", "팔굽"), "plank"), (("앉",), "sit"),
    (("일어", "서봐", "서있"), "stand"), (("돌아다", "움직", "뛰어다", "놀러", "산책"), "roam"),
    (("통통", "점프", "폴짝", "뛰어"), "hop"), (("휘파람",), "whistle"),
    (("쉬어", "쉴까", "휴식", "쉬자"), "rest"), (("사다리", "올라가"), "ladder"), (("배추", "농사", "심어", "밭"), "plant"), (("안녕", "하이", "반가"), "hi"), (("사랑", "좋아", "잘했", "고마", "최고", "귀여"), "love"),
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
    if any(k in t for k in ("옷", "입고", "입었")):
        return "지금 입은 옷: " + ", ".join(save["outfit"]) if save["outfit"] else "아직 맨몸이에요… 선물로 옷 주워올게요!"
    if any(k in t for k in ("선물", "가진", "주머니", "인벤")):
        return "제 주머니: " + ", ".join(f"{k} x{v}" for k, v in save["inv"].items()) if save["inv"] else "주머니가 텅 비었어요… 친밀도를 올려주세요!"
    if any(k in t for k in ("기분", "어때")): return "기분 최고예요! 💕" if save["aff"] >= 30 else "나쁘지 않아요… 쓰담쓰담 해주면 더 좋아질 듯!"
    if any(k in t for k in ("도움", "뭐할수", "명령", "할수있")):
        return "이렇게 말해보세요!\n가만있어 / 앉아 / 엎드려 / 일어나 / 돌아다녀 / 통통 / 휘파람 / 쉬어 / 사다리 / 배추\n몇 시야? / 오늘 며칠? / 1+1은? / 친밀도 / 옷 / 선물"
    return None

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
    elif a_ == "rest": setmode("auto"); draw("normal"); rest()
    elif a_ == "ladder": setmode("auto"); draw("normal"); ladder()
    elif a_ == "plant": setmode("auto"); draw("normal"); plant()
    elif a_ == "hi": speak("안녕하세요! 오늘도 같이 힘내요 🙌")
    elif a_ == "love": hearts(); speak("헤헤 저도요~ 💕")
    else: speak("음… 잘 모르겠어요 (갸우뚱)\n'가만있어', '앉아', '엎드려', '돌아다녀', '일어나' 라고 해보세요! ('도움말'도 물어보세요)", 7000)

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
c.bind("<Button-3>", ask)

st = dict(x=None, dir=0, rev=0, t=0.0)
def motion(e):  # 머리 쪽에서 좌우로 6번 방향을 바꾸면 쓰담쓰담
    ex, ey = conv(e); now = time.time()
    if not (40 < ex < 200 and 90 < ey < 140): st.update(x=None, dir=0, rev=0); return
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
        elif n in ("__ladder__", "__cabbage__"): pending.discard(n); imgs.setdefault(n, []).append(im) if im else fails.add(n)
        elif n.startswith("__outfit__"): give(n[10:], True, im)
        else: give(n, False, im)
    while not cmds.empty():
        k = cmds.get()
        if k == "sorry": setmode("auto"); show(random.choice(SORRY), "sorry")
        elif k == "hi": show("안녕하세요! 오늘도 같이 힘내요 🙌", "happy")
        elif k == "quit": root.destroy(); return
    root.after(200, poll)

draw("normal"); poll(); root.after(8000, act); root.mainloop()
