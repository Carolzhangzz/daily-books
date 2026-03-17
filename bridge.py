#!/usr/bin/env python3
"""Local bridge: serves static files + Claude CLI API for 拾页."""
import http.server, json, subprocess, os, urllib.parse, random, datetime

PORT = 9527
ROOT = os.path.expanduser("~/Documents/daily-books")
DATA = os.path.join(ROOT, "data")
CLAUDE = os.path.expanduser("~/.local/bin/claude")

BOOK_LIST = """文学: 百年孤独,局外人,卡拉马佐夫兄弟,罪与罚,项塔兰,1984,美丽新世界,了不起的盖茨比,追风筝的人,挪威的森林,半生缘,活着,许三观卖血记,围城,呐喊,红楼梦,情人,一个陌生女人的来信,带小狗的女人,老人与海,不能承受的生命之轻,盲目,霍乱时期的爱情,我与地坛,平凡的世界,人间失格,月亮与六便士,杀死一只知更鸟,麦田里的守望者,小王子,动物农场,悉达多,刀锋,树上的男爵,看不见的城市,白鲸,呼啸山庄,三体,白夜行,傲慢与偏见,简爱,德米安,变形记,审判,城堡,荒原狼,玻璃球游戏,战争与和平,安娜·卡列尼娜,大师和玛格丽特,洛丽塔,在路上,第二十二条军规,发条橙,华氏451度,基地,银河系搭车客指南,你一生的故事,神曲,堂吉诃德,尤利西斯,追忆似水年华,恶之花,日瓦戈医生,静静的顿河,金阁寺,窗边的小豆豆,飞越疯人院,天龙八部,白鹿原,长恨歌,黄金时代,繁花,额尔古纳河右岸,秋园
哲学: 存在与时间,西西弗神话,反与正,查拉图斯特拉如是说,沉思录,逻辑哲学论,哲学研究,存在与虚无,规训与惩罚,理想国,道德经,论语,庄子,正义论,人的境况,艾希曼在耶路撒冷,第二性,禅与摩托车维修艺术,纯粹理性批判,作为意志和表象的世界,悲剧的诞生,善恶的彼岸,单向度的人,消费社会,模拟与仿真,千高原,论自然,伦理学,恐惧与战栗,存在主义是一种人道主义,什么是哲学,中国哲学简史
社科: 枪炮病菌与钢铁,人类简史,21世纪资本论,国富论,娱乐至死,技术垄断,社会契约论,论自由,菊与刀,历史的终结与最后之人,万历十五年,江城,叫魂,贫穷的本质,想象的共同体,文明的冲突,论美国的民主,旧制度与大革命,资本论,新教伦理与资本主义精神,乡土中国,金枝,忧郁的热带,格调,第四消费时代,未来简史,债:第一个5000年,美国大城市的死与生,正义之心,公正
科学: 自私的基因,思考快与慢,哥德尔艾舍尔巴赫,时间简史,系统之美,复杂,失控,必然,黑天鹅,反脆弱,心流,进化心理学,人类的误测,混沌,费曼物理学讲义,上帝掷骰子吗,从一到无穷大,万物简史,基因传,癌症传,免疫,人体的故事,大脑传,生命是什么,宇宙的琴弦,优雅的宇宙,数学之美
商业: 创新者的窘境,从零到一,原则,穷查理宝典,黑客与画家,设计心理学,硅谷钢铁侠,鞋狗,基业长青,信号与噪声,精益创业,重新定义公司,引爆点,异类,刻意练习,纳瓦尔宝典,清单革命,非暴力沟通,高效能人士的七个习惯,思考的框架,学会提问,麦肯锡方法
心理: 乌合之众,社会性动物,影响力,亲密关系,被讨厌的勇气,少有人走的路,自卑与超越,梦的解析,爱的艺术,逃避自由,我们内心的冲突,人性的弱点,情绪勒索,非暴力沟通,正念的奇迹,当下的力量,活出生命的意义,身体从未忘记,也许你该找个人聊聊
传记: 史蒂夫·乔布斯传,富兰克林自传,居里夫人传,我的奋斗,当呼吸化为空气,维特根斯坦传,爱因斯坦传,达·芬奇传,成为波伏瓦,苏东坡传,曾国藩传,邓小平时代,切·格瓦拉传,甘地自传,褚时健传,渴望生活:梵高传,忏悔录
艺术: 艺术的故事,美的历程,论摄影,观看之道,艺术与错觉,什么是艺术,设计中的设计,写给大家看的设计书,色彩的秘密生活,建筑的永恒之道,音乐的极境,聆听音乐
自然: 寂静的春天,物种起源,所罗门王的指环,昆虫记,看不见的森林,一平方英寸的寂静,荒野之声,博物学家的神秘动物图鉴,植物的欲望,半个地球,万物有灵且美
数学: 数学:确定性的丧失,素数的音乐,博弈论,如何解题,统计学的世界,信息简史,算法之美,千年难题,怎样解题,逻辑的引擎"""

EXTEND_TPL = """为《{book}》生成补充阅读内容。中文回答，输出严格JSON（不要markdown代码块）：
{{"themes":"3-5个深层主题，每个主题2-3句话展开，用\\n分段","questions":"3个引发思考的问题，帮助读者深入理解，用\\n分隔","author_story":"关于作者的一个有趣故事或背景（150-200字）","related":"3本相关推荐书籍，每本一句话说明为什么相关，用\\n分隔"}}"""

PROMPT_TPL = """你是一个书籍推荐生成器。为以下书籍生成详细的中文推荐内容。

要求：
- deep_dive: 500-800字，像跟朋友聊天一样讲这本书
- quotes: 3-5条精选原文金句，附上下文说明
- 中文为主，书名和关键术语保留英文原文

输出严格的JSON格式（不要markdown代码块），结构如下：
{{"date":"{date}","books":[{{"title_zh":"中文书名","title_en":"English Title","author_zh":"作者","author_en":"Author","year":"年份","category":"分类","one_liner":"一句话概括","deep_dive":"深度介绍","quotes":[{{"text":"原文","context":"背景"}}]}}]}}

请为这些书生成内容：{books}"""

def get_used_books():
    """Get all books that have been generated + books marked as read."""
    used = set()
    # From generated data files
    if os.path.isdir(DATA):
        for f in os.listdir(DATA):
            if f.endswith('.json') and f != 'index.json':
                try:
                    with open(os.path.join(DATA, f)) as fh:
                        d = json.load(fh)
                        for b in d.get('books', []):
                            used.add(b.get('title_zh', ''))
                except: pass
    # From bookshelf (read books)
    notes_path = os.path.join(ROOT, "notes.json")
    # Also check bookshelf in a shelf.json if it exists
    return used

def get_total_book_count():
    count = 0
    for line in BOOK_LIST.strip().split('\n'):
        _, books = line.split(': ', 1)
        count += len(books.split(','))
    return count

def pick_books(cats=None, count=3):
    all_books = {}
    for line in BOOK_LIST.strip().split('\n'):
        cat, books = line.split(': ', 1)
        for b in books.split(','):
            all_books[b.strip()] = cat.strip()
    if cats:
        filtered = {b: c for b, c in all_books.items() if c in cats}
    else:
        filtered = all_books
    used = get_used_books()
    available = [b for b in filtered if b not in used]
    if len(available) < count:
        # Only fall back if we've exhausted most of the list (>80%)
        if len(used) > get_total_book_count() * 0.8:
            available = list(filtered.keys())  # reset
        else:
            # Include some used books to fill the gap
            extra = [b for b in filtered if b not in available]
            random.shuffle(extra)
            available += extra[:count - len(available)]
    return random.sample(available, min(count, len(available)))

def make_id():
    now = datetime.datetime.now()
    return now.strftime("%Y-%m-%d_%H%M")

def update_index(entry_id):
    idx_path = os.path.join(DATA, 'index.json')
    try:
        with open(idx_path) as f:
            entries = json.load(f)
    except:
        entries = []
    if entry_id not in entries:
        entries.append(entry_id)
        entries.sort()
    with open(idx_path, 'w') as f:
        json.dump(entries, f)

def run_claude(prompt):
    """Run claude -p with full prompt, save output to JSON, push."""
    import threading
    entry_id = make_id()
    def _run():
        try:
            result = subprocess.run(
                [CLAUDE, "-p", prompt],
                cwd=ROOT, capture_output=True, text=True, timeout=120,
                env={**os.environ, 'NO_COLOR': '1'}
            )
            output = result.stdout.strip()
            start = output.find('{')
            end = output.rfind('}') + 1
            if start >= 0 and end > start:
                data = json.loads(output[start:end])
                data['id'] = entry_id
                path = os.path.join(DATA, f"{entry_id}.json")
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                update_index(entry_id)
                subprocess.run(["git", "add", "data/"], cwd=ROOT)
                subprocess.run(["git", "commit", "-m", f"Add books {entry_id}"], cwd=ROOT)
                subprocess.run(["git", "push"], cwd=ROOT)
                print(f"[done] {entry_id}")
            else:
                print(f"[error] No JSON in output: {output[:200]}")
        except Exception as e:
            print(f"[error] {e}")
    threading.Thread(target=_run, daemon=True).start()
    return entry_id

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        today = datetime.date.today().isoformat()

        if parsed.path == "/api/health":
            return self._json({"ok": True})

        if parsed.path == "/api/extend":
            book = params.get("book", [""])[0]
            if not book:
                return self._json({"error": "missing book"}, 400)
            prompt = EXTEND_TPL.format(book=book)
            try:
                result = subprocess.run(
                    [CLAUDE, "-p", prompt],
                    cwd=ROOT, capture_output=True, text=True, timeout=90,
                    env={**os.environ, 'NO_COLOR': '1'}
                )
                output = result.stdout.strip()
                start = output.find('{')
                end = output.rfind('}') + 1
                if start >= 0 and end > start:
                    ext = json.loads(output[start:end])
                    return self._json({"ok": True, "book": book, "extended": ext})
                return self._json({"error": "no JSON in response"}, 500)
            except subprocess.TimeoutExpired:
                return self._json({"error": "timeout"}, 504)
            except Exception as e:
                return self._json({"error": str(e)}, 500)

        if parsed.path == "/api/more":
            book = params.get("book", [""])[0]
            if not book:
                return self._json({"error": "missing book"}, 400)
            prompt = PROMPT_TPL.format(date=today, books=book)
            eid = run_claude(prompt)
            return self._json({"status": "generating", "id": eid, "book": book})

        if parsed.path == "/api/generate":
            cats_str = params.get("cats", [""])[0].strip()
            cats = [c.strip() for c in cats_str.split()] if cats_str else None
            books = pick_books(cats, 3)
            used = get_used_books()
            print(f"[gen] picked: {books} | skipped {len(used)} used books", flush=True)
            prompt = PROMPT_TPL.format(date=today, books="、".join(books))
            eid = run_claude(prompt)
            return self._json({"status": "generating", "id": eid, "books": books})

        if parsed.path == "/api/status":
            eid = params.get("id", [""])[0]
            if eid:
                path = os.path.join(DATA, f"{eid}.json")
                if os.path.exists(path):
                    return self._json({"ready": True, "id": eid})
                return self._json({"ready": False, "id": eid})
            return self._json({"ready": False})

        if parsed.path == "/api/notes":
            notes_path = os.path.join(ROOT, "notes.json")
            try:
                with open(notes_path, encoding='utf-8') as f:
                    return self._json(json.load(f))
            except:
                return self._json([])

        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/save-notes":
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                notes = json.loads(body)
                notes_path = os.path.join(ROOT, "notes.json")
                with open(notes_path, 'w', encoding='utf-8') as f:
                    json.dump(notes, f, ensure_ascii=False, indent=2)
                self._json({"ok": True})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return
        self._json({"error": "not found"}, 404)

    def _json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, fmt, *args):
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {fmt % args}")

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
    os.makedirs(DATA, exist_ok=True)
    s = http.server.HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"拾页 running at http://localhost:{PORT}", flush=True)
    s.serve_forever()
