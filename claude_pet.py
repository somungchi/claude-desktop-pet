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

SAVE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pet_save.json")
MAX_AFF = 100
GIFT_EVERY = 20  # 친밀도가 이 값의 배수를 넘을 때마다 선물
GIFTS = [("황금 목걸이", "gold necklace"), ("지렁이", "earthworm"), ("꿀사과", "honeycrisp apple"),
         ("황금 변기", "golden toilet"), ("초대형 오리 인형", "rubber duck"), ("감자", "potato"),
         ("마른 멸치", "dried anchovy"), ("우승 트로피", "trophy"), ("금괴", "gold bar"), ("도넛", "donut"),
         ("컵라면", "instant noodles cup"), ("후라이드 치킨", "fried chicken"), ("피자 한 판", "pizza"),
         ("공룡 화석", "dinosaur fossil"), ("삽", "shovel"), ("고구마", "sweet potato"),
         ("두루마리 휴지", "toilet paper roll"), ("다이아몬드", "diamond")]  # 선물 이미지는 Wikimedia Commons 검색
OUTFITS = ["파티모자", "왕관", "선글라스", "빨간 목도리", "리본"]
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

def limbs(m, f, arm):  # 팔다리 위치. struggle(잡혀서 발버둥)이면 프레임 f에 따라 번갈아 휘두름
    if m == "struggle":
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

def wear(o, front):
    for n in save["outfit"]:
        if n == "파티모자":  # 줄무늬 고깔 + 챙 + 방울
            c.create_polygon(95, 92, 120, 36, 145, 92, fill="#6c8cff", outline=DARK, width=2, **o)
            for y1, y2 in ((58, 66), (74, 82)):  # 노란 줄무늬
                h1, h2 = (y1 - 36) / 56 * 25, (y2 - 36) / 56 * 25
                c.create_polygon(120 - h1, y1, 120 + h1, y1, 120 + h2, y2, 120 - h2, y2, fill="#ffe14d", outline="", **o)
            c.create_rectangle(93, 88, 147, 95, fill="#4b66d6", outline=DARK, width=2, **o)
            c.create_oval(112, 28, 128, 44, fill="#ff7fb0", outline=DARK, **o)
            c.create_oval(116, 31, 120, 35, fill="white", outline="", **o)
        elif n == "왕관":  # 보석 박힌 왕관
            c.create_polygon(85, 94, 85, 60, 102, 78, 120, 52, 138, 78, 155, 60, 155, 94, fill="#f5c518", outline=DARK, width=2, **o)
            c.create_rectangle(85, 82, 155, 94, fill="#d9a400", outline=DARK, width=2, **o)
            for gx, col in ((97, "#e23b3b"), (120, "#3b82e2"), (143, "#e23b3b")):
                c.create_oval(gx - 5, 84, gx + 5, 93, fill=col, outline=DARK, **o)
            for px, py in ((85, 60), (120, 52), (155, 60)):  # 꼭대기 진주
                c.create_oval(px - 4, py - 5, px + 4, py + 3, fill="white", outline=DARK, **o)
            c.create_line(92, 70, 98, 82, fill="#fff2a8", width=2, **o)
        elif n == "선글라스" and front:  # 번쩍이는 렌즈 + 다리
            c.create_line(84, 122, 62, 118, fill="#222", width=3, **o); c.create_line(156, 122, 178, 118, fill="#222", width=3, **o)
            c.create_oval(82, 112, 108, 138, fill="#1a1a1a", outline="#555", width=2, **o)
            c.create_oval(132, 112, 158, 138, fill="#1a1a1a", outline="#555", width=2, **o)
            c.create_arc(106, 114, 134, 130, start=0, extent=180, style="arc", width=3, outline="#222", **o)
            for gx in (89, 139): c.create_line(gx, 118, gx + 6, 114, fill="white", width=2, **o)
        elif n == "빨간 목도리":  # 줄무늬 + 매듭 + 꼬리 + 술
            c.create_rectangle(58, 98, 182, 114, fill="#d63a3a", outline=DARK, width=2, **o)
            for sx in range(66, 180, 16): c.create_line(sx, 99, sx, 113, fill="white", width=3, **o)
            c.create_rectangle(148, 114, 166, 156, fill="#d63a3a", outline=DARK, width=2, **o)
            for sy in (124, 138): c.create_line(149, sy, 165, sy, fill="white", width=3, **o)
            for fx in range(150, 166, 4): c.create_line(fx, 156, fx, 163, fill="#d63a3a", width=2, **o)
            c.create_oval(140, 100, 158, 120, fill="#b52b2b", outline=DARK, width=2, **o)
        elif n == "리본":  # 물방울 리본: 양쪽 고리 + 매듭 + 꼬리
            c.create_polygon(152, 100, 160, 120, 166, 116, fill="#ff7fb0", outline=DARK, **o)
            c.create_polygon(152, 100, 144, 120, 138, 116, fill="#ff7fb0", outline=DARK, **o)
            c.create_oval(152, 74, 180, 104, fill="#ff7fb0", outline=DARK, width=2, **o)
            c.create_oval(124, 74, 152, 104, fill="#ff7fb0", outline=DARK, width=2, **o)
            for dx, dy in ((165, 84), (137, 84), (165, 94), (137, 94)): c.create_oval(dx - 2, dy - 2, dx + 2, dy + 2, fill="white", outline="", **o)
            c.create_oval(144, 83, 160, 97, fill="#ff4f93", outline=DARK, width=2, **o)

def draw(m, gift=None, f=0):
    if m == "plank": return draw_plank(f)
    global mood; mood = m
    c.delete("body")
    o = dict(tags="body")
    arm = (178, 122, 226, 142) if gift else (178, 130, 200, 160)  # 선물 줄 땐 팔을 쭉 뻗음
    for box in limbs(m, f, arm):
        c.create_rectangle(*box, fill=ORANGE, outline=DARK, width=2, **o)
    c.create_rectangle(60, 90, 180, 205, fill=ORANGE, outline=DARK, width=2, **o)
    if m == "sit":  # 앉기: 다리를 앞으로 뻗음
        c.delete("body"); o = dict(tags="body")
        for box in [(40, 130, 62, 160), (178, 130, 200, 160), (62, 205, 112, 222), (128, 205, 178, 222)]:
            c.create_rectangle(*box, fill=ORANGE, outline=DARK, width=2, **o)
        c.create_rectangle(60, 90, 180, 205, fill=ORANGE, outline=DARK, width=2, **o)
    front = m not in ("sorry", "hit")
    if not front:  # 뒤돌아서 엉덩이를 내밀기 (얼굴 없음)
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
        c.create_rectangle(*box, fill=ORANGE, outline=DARK, width=2, **o)
    c.create_rectangle(50, 160 + d, 180, 202 + d, fill=ORANGE, outline=DARK, width=2, **o)
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
def cutout(im, size=150):  # 배경(흰색 등)을 지워 오려낸 스티커처럼 + 반투명 없애기(투명색 창이라)
    im = im.convert("RGBA")
    if im.getchannel("A").getextrema()[0] == 255:
        for xy in ((0, 0), (im.width - 1, 0), (0, im.height - 1), (im.width - 1, im.height - 1)):
            ImageDraw.floodfill(im, xy, (255, 0, 255, 0), thresh=45)
    im.putalpha(im.getchannel("A").point(lambda v: 255 if v > 128 else 0))
    im.thumbnail((size, size)); return im

def fetch_gift(name, q):
    def run():
        try:
            u = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(dict(
                action="query", generator="search", gsrnamespace=6, gsrsearch=q + " filetype:bitmap", gsrlimit=12,
                prop="imageinfo", iiprop="url|mime", iiurlwidth=400, format="json"))
            pages = list(json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=15))["query"]["pages"].values())
            random.shuffle(pages)
            for p in pages:
                ii = p["imageinfo"][0]
                if ii["mime"] in ("image/jpeg", "image/png", "image/gif", "image/webp"):
                    b = urllib.request.urlopen(urllib.request.Request(ii["thumburl"], headers=UA), timeout=15).read()
                    IMGQ.put((name, cutout(Image.open(io.BytesIO(b))))); return
        except Exception:
            pass
        IMGQ.put((name, None))  # 실패하면 이모지 상자로
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
    place = random.choice(PLACES)
    show(f"친밀도 {save['aff']}! {place} 이거 주웠어요. 받아주세요!" + ("" if outfit else f" → {item}"),
         "happy", "👕" if outfit else (" " if img else "🎁"))
    if img:  # 몸보다 큰 선물을 번쩍 들어 보여줌
        gift_ph[:] = [ImageTk.PhotoImage(img)]; c.create_image(268, 188, image=gift_ph[0], tags="giftimg")
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
        if left and random.random() < 0.5: give(random.choice(left), True)
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

def stopmove():  # 진행 중인 이동/점프를 모두 취소
    global gen, busy
    gen += 1; busy = False

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
    if busy or mode != "auto" or mood != "normal": root.after(8000, act); return
    k = random.choice(("still", "hop", "hop", "walk", "sit", "whistle", "talk", "talk"))
    if k == "hop": hops(random.randint(3, 5))
    elif k == "walk": goto(root.winfo_x() + random.randint(-300, 300), root.winfo_y() + random.randint(-150, 150))
    elif k == "sit":
        draw("sit"); say("휴~ 잠깐 앉을게요"); root.after(4500, lambda: mood == "sit" and say(random.choice(TALK)))
        root.after(11000, done, "sit")
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
    (("안녕", "하이", "반가"), "hi"), (("사랑", "좋아", "잘했", "고마", "최고", "귀여"), "love"),
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
        return "이렇게 말해보세요!\n가만있어 / 앉아 / 엎드려 / 일어나 / 돌아다녀 / 통통 / 휘파람\n몇 시야? / 오늘 며칠? / 1+1은? / 친밀도 / 옷 / 선물"
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
    elif a_ == "hi": speak("안녕하세요! 오늘도 같이 힘내요 🙌")
    elif a_ == "love": hearts(); speak("헤헤 저도요~ 💕")
    else: speak("음… 잘 모르겠어요 (갸우뚱)\n'가만있어', '앉아', '엎드려', '돌아다녀', '일어나' 라고 해보세요! ('도움말'도 물어보세요)", 7000)

chat = []
def ask(e=None):
    if chat: chat[0].lift(); chat[0].focus_force(); return
    w = tk.Toplevel(root); chat.append(w); w.title("Claude에게 말하기"); w.attributes("-topmost", True)
    w.geometry(f"+{max(0, root.winfo_x() - 270)}+{min(SH - 80, root.winfo_y() + H - 60)}")
    en = tk.Entry(w, width=32, font=("Malgun Gothic", 11)); en.pack(padx=8, pady=8)
    def close(_=None): chat.clear(); w.destroy()
    def send(_=None):
        if en.get().strip(): talk(en.get())
        close()
    en.bind("<Return>", send); en.bind("<Escape>", close); w.protocol("WM_DELETE_WINDOW", close)
    w.after(80, lambda: (w.focus_force(), en.focus_force()))
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
        n, im = IMGQ.get(); give(n, False, im)
    while not cmds.empty():
        k = cmds.get()
        if k == "sorry": setmode("auto"); show(random.choice(SORRY), "sorry")
        elif k == "hi": show("안녕하세요! 오늘도 같이 힘내요 🙌", "happy")
        elif k == "quit": root.destroy(); return
    root.after(200, poll)

draw("normal"); poll(); root.after(8000, act); root.mainloop()
