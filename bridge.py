#!/usr/bin/env python3
"""Local bridge: serves static files + Claude CLI API for 拾页."""
import http.server, json, subprocess, os, urllib.parse, random, datetime

PORT = 9527
ROOT = os.path.expanduser("~/Documents/daily-books")
DATA = os.path.join(ROOT, "data")
CLAUDE = os.path.expanduser("~/.local/bin/claude")

BOOK_LIST = """文学: 百年孤独,局外人,卡拉马佐夫兄弟,罪与罚,项塔兰,1984,美丽新世界,了不起的盖茨比,追风筝的人,挪威的森林,半生缘,活着,许三观卖血记,围城,呐喊,红楼梦,情人,一个陌生女人的来信,带小狗的女人,老人与海,不能承受的生命之轻,盲目,霍乱时期的爱情,我与地坛,平凡的世界,人间失格,月亮与六便士,杀死一只知更鸟,麦田里的守望者,小王子,动物农场,悉达多,刀锋,树上的男爵,看不见的城市,白鲸,呼啸山庄
哲学: 存在与时间,西西弗神话,反与正,查拉图斯特拉如是说,沉思录,逻辑哲学论,哲学研究,存在与虚无,规训与惩罚,理想国,道德经,论语,庄子,正义论,人的境况,艾希曼在耶路撒冷,第二性,禅与摩托车维修艺术
社科: 枪炮病菌与钢铁,人类简史,21世纪资本论,国富论,娱乐至死,技术垄断,乌合之众,社会契约论,论自由,菊与刀,历史的终结与最后之人,万历十五年,江城,叫魂,贫穷的本质
科学: 自私的基因,思考快与慢,哥德尔艾舍尔巴赫,时间简史,系统之美,复杂,失控,必然,黑天鹅,反脆弱,心流,进化心理学,人类的误测
商业: 创新者的窘境,从零到一,原则,穷查理宝典,黑客与画家,设计心理学,硅谷钢铁侠,鞋狗,基业长青,信号与噪声"""

PROMPT_TPL = """你是一个书籍推荐生成器。为以下书籍生成详细的中文推荐内容。

要求：
- deep_dive: 500-800字，像跟朋友聊天一样讲这本书
- quotes: 3-5条精选原文金句，附上下文说明
- 中文为主，书名和关键术语保留英文原文

输出严格的JSON格式（不要markdown代码块），结构如下：
{{"date":"{date}","books":[{{"title_zh":"中文书名","title_en":"English Title","author_zh":"作者","author_en":"Author","year":"年份","category":"分类","one_liner":"一句话概括","deep_dive":"深度介绍","quotes":[{{"text":"原文","context":"背景"}}]}}]}}

请为这些书生成内容：{books}"""

def get_used_books():
    used = set()
    if os.path.isdir(DATA):
        for f in os.listdir(DATA):
            if f.endswith('.json') and f != 'index.json':
                try:
                    with open(os.path.join(DATA, f)) as fh:
                        d = json.load(fh)
                        for b in d.get('books', []):
                            used.add(b.get('title_zh', ''))
                except: pass
    return used

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
        available = list(filtered.keys())
    return random.sample(available, min(count, len(available)))

def update_index():
    idx_path = os.path.join(DATA, 'index.json')
    try:
        with open(idx_path) as f:
            dates = json.load(f)
    except:
        dates = []
    today = datetime.date.today().isoformat()
    if today not in dates:
        dates.append(today)
        dates.sort()
    with open(idx_path, 'w') as f:
        json.dump(dates, f)

def run_claude(prompt, callback_date):
    """Run claude -p with full prompt, save output to JSON, push."""
    import threading
    def _run():
        try:
            result = subprocess.run(
                [CLAUDE, "-p", prompt],
                cwd=ROOT, capture_output=True, text=True, timeout=120,
                env={**os.environ, 'NO_COLOR': '1'}
            )
            output = result.stdout.strip()
            # Try to extract JSON from output
            start = output.find('{')
            end = output.rfind('}') + 1
            if start >= 0 and end > start:
                data = json.loads(output[start:end])
                path = os.path.join(DATA, f"{callback_date}.json")
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                update_index()
                # Git push
                subprocess.run(["git", "add", "data/"], cwd=ROOT)
                subprocess.run(["git", "commit", "-m", f"Add books for {callback_date}"], cwd=ROOT)
                subprocess.run(["git", "push"], cwd=ROOT)
                print(f"[done] Generated and pushed for {callback_date}")
            else:
                print(f"[error] No JSON in output: {output[:200]}")
        except Exception as e:
            print(f"[error] {e}")
    threading.Thread(target=_run, daemon=True).start()

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        today = datetime.date.today().isoformat()

        if parsed.path == "/api/health":
            return self._json({"ok": True})

        if parsed.path == "/api/more":
            book = params.get("book", [""])[0]
            if not book:
                return self._json({"error": "missing book"}, 400)
            prompt = PROMPT_TPL.format(date=today, books=book)
            run_claude(prompt, today)
            return self._json({"status": "generating", "book": book})

        if parsed.path == "/api/generate":
            cats_str = params.get("cats", [""])[0].strip()
            cats = [c.strip() for c in cats_str.split()] if cats_str else None
            books = pick_books(cats, 3)
            prompt = PROMPT_TPL.format(date=today, books="、".join(books))
            run_claude(prompt, today)
            return self._json({"status": "generating", "books": books})

        if parsed.path == "/api/status":
            # Check if today's data exists
            path = os.path.join(DATA, f"{today}.json")
            if os.path.exists(path):
                mtime = os.path.getmtime(path)
                return self._json({"ready": True, "mtime": mtime})
            return self._json({"ready": False})

        super().do_GET()

    def _json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, fmt, *args):
        msg = str(args[0]) if args else ''
        if '/api/' in msg:
            print(f"[api] {msg}")

if __name__ == "__main__":
    os.makedirs(DATA, exist_ok=True)
    s = http.server.HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"拾页 running at http://localhost:{PORT}")
    s.serve_forever()
