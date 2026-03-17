#!/usr/bin/env python3
"""Local bridge: serves static files + Claude CLI API for 拾页."""
import http.server, json, subprocess, os, urllib.parse, random, datetime, re

generation_status = {}  # entry_id -> 'running' | 'done' | 'error'


def repair_json(text):
    """Attempt to repair common JSON issues from LLM output."""
    # Strip markdown code fences
    text = re.sub(r'^```(?:json)?\s*\n?', '', text.strip())
    text = re.sub(r'\n?```\s*$', '', text.strip())
    text = text.strip()

    # Remove trailing commas before } or ]
    text = re.sub(r',\s*}', '}', text)
    text = re.sub(r',\s*]', ']', text)

    # Fix unescaped newlines inside strings
    # Replace literal newlines between quotes with \\n
    def _fix_newlines_in_strings(s):
        result = []
        in_string = False
        escape = False
        for ch in s:
            if escape:
                result.append(ch)
                escape = False
                continue
            if ch == '\\' and in_string:
                result.append(ch)
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
            if ch == '\n' and in_string:
                result.append('\\n')
                continue
            result.append(ch)
        return ''.join(result)

    # First try as-is
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try fixing newlines in strings
    fixed = _fix_newlines_in_strings(text)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # Try fixing missing closing brackets
    for suffix in ['}', ']}', '"]}', '"}]}', '"]}]}']:
        try:
            return json.loads(fixed + suffix)
        except json.JSONDecodeError:
            pass

    # Last resort: extract individual book objects and reconstruct
    try:
        book_pattern = re.findall(r'\{[^{}]*"title_zh"[^{}]*\}', fixed)
        if book_pattern:
            books = []
            for m in book_pattern:
                try:
                    books.append(json.loads(m))
                except json.JSONDecodeError:
                    pass
            if books:
                return {"books": books}
    except Exception:
        pass

    # Give up, raise the original error
    return json.loads(text)

PORT = 9527
ROOT = os.path.expanduser("~/Documents/daily-books")
DATA = os.path.join(ROOT, "data")
CLAUDE = os.path.expanduser("~/.local/bin/claude")

BOOK_LIST = """文学: 百年孤独,局外人,卡拉马佐夫兄弟,罪与罚,项塔兰,1984,美丽新世界,了不起的盖茨比,追风筝的人,挪威的森林,半生缘,活着,许三观卖血记,围城,呐喊,红楼梦,情人,一个陌生女人的来信,带小狗的女人,老人与海,不能承受的生命之轻,盲目,霍乱时期的爱情,我与地坛,平凡的世界,人间失格,月亮与六便士,杀死一只知更鸟,麦田里的守望者,小王子,动物农场,悉达多,刀锋,树上的男爵,看不见的城市,白鲸,呼啸山庄,三体,白夜行,傲慢与偏见,简爱,德米安,变形记,审判,城堡,荒原狼,玻璃球游戏,战争与和平,安娜·卡列尼娜,大师和玛格丽特,洛丽塔,在路上,第二十二条军规,发条橙,华氏451度,基地,银河系搭车客指南,你一生的故事,神曲,堂吉诃德,尤利西斯,追忆似水年华,恶之花,日瓦戈医生,静静的顿河,金阁寺,窗边的小豆豆,飞越疯人院,天龙八部,白鹿原,长恨歌,黄金时代,繁花,额尔古纳河右岸,秋园,喧哗与骚动,等待戈多,恶心,鼠疫,第三个警察,都柏林人,到灯塔去,达洛维夫人,弗兰肯斯坦,德古拉,双城记,远大前程,雾都孤儿,理智与情感,诺桑觉寺,爱玛,包法利夫人,高老头,悲惨世界,红与黑,茶花女,基督山伯爵,罗生门,雪国,伊豆的舞女,海边的卡夫卡,舞舞舞,世界尽头与冷酷仙境,奇鸟行状录,兄弟,在细雨中呼喊,第七天,文城,受活,秦腔,废都,尘埃落定,生死疲劳,蛙,丰乳肥臀,檀香刑,解忧杂货店,嫌疑人X的献身,沉默的羔羊,达芬奇密码,指环王,霍比特人,纳尼亚传奇,冰与火之歌,沙丘,安德的游戏,神经漫游者,雪崩,献给阿尔吉侬的花束,午夜之子,微暗的火,第五屠宰场,太阳照常升起,愤怒的葡萄,永别了武器,丧钟为谁而鸣,白牙,野性的呼唤,夜色温柔,了不起的狐狸爸爸,春雪,细雪,源氏物语,使女的故事,钟形罩,天才的编辑,苔丝,米德尔马契,看得见风景的房间,发条女孩,遗落的南境,克拉拉与太阳,地下铁道
哲学: 存在与时间,西西弗神话,反与正,查拉图斯特拉如是说,沉思录,逻辑哲学论,哲学研究,存在与虚无,规训与惩罚,理想国,道德经,论语,庄子,正义论,人的境况,艾希曼在耶路撒冷,第二性,禅与摩托车维修艺术,纯粹理性批判,作为意志和表象的世界,悲剧的诞生,善恶的彼岸,单向度的人,消费社会,模拟与仿真,千高原,论自然,伦理学,恐惧与战栗,存在主义是一种人道主义,什么是哲学,中国哲学简史,权力意志,偶像的黄昏,人性的全景论,判断力批判,精神现象学,小逻辑,实用主义,科学革命的结构,开放社会及其敌人,无政府主义国家与乌托邦,动物解放,正义的理念,论人类不平等的起源,利维坦,君主论,功利主义,论法的精神,人性论,道德形而上学基础,论确实性,哲学的慰藉,苏菲的世界,大问题,哲学的故事
社科: 枪炮病菌与钢铁,人类简史,21世纪资本论,国富论,娱乐至死,技术垄断,社会契约论,论自由,菊与刀,历史的终结与最后之人,万历十五年,江城,叫魂,贫穷的本质,想象的共同体,文明的冲突,论美国的民主,旧制度与大革命,资本论,新教伦理与资本主义精神,乡土中国,金枝,忧郁的热带,格调,第四消费时代,未来简史,债:第一个5000年,美国大城市的死与生,正义之心,公正,路西法效应,服从权威,独裁者手册,论革命,极权主义的起源,文化的解释,规模,世界秩序,大国的兴衰,论中国,大外交,一千零一夜,全球通史,地理与世界霸权,第三波,社会学的想象力,理解媒介,景观社会,监视资本主义时代,国家为什么会失败,人口浪潮,丝绸之路,东方化,独自打保龄,信任,我们为什么要睡觉
科学: 自私的基因,思考快与慢,哥德尔艾舍尔巴赫,时间简史,系统之美,复杂,失控,必然,黑天鹅,反脆弱,心流,进化心理学,人类的误测,混沌,费曼物理学讲义,上帝掷骰子吗,从一到无穷大,万物简史,基因传,癌症传,免疫,人体的故事,大脑传,生命是什么,宇宙的琴弦,优雅的宇宙,数学之美,量子力学史话,相对论,物理学的进化,最后的演讲,科学的旅程,上帝的手术刀,基因组,病毒星球,人类存在的意义,生命之网,数学简史,皇帝新脑,物理世界奇遇记,人工智能简史,确定性的终结,看不见的视觉,协同学,深度学习,生命3.0,规模化生物学
商业: 创新者的窘境,从零到一,原则,穷查理宝典,黑客与画家,设计心理学,硅谷钢铁侠,鞋狗,基业长青,信号与噪声,精益创业,重新定义公司,引爆点,异类,刻意练习,纳瓦尔宝典,清单革命,非暴力沟通,高效能人士的七个习惯,思考的框架,学会提问,麦肯锡方法,定位,竞争战略,长尾理论,蓝海战略,增长黑客,商业的本质,谁说大象不能跳舞,重来,硅谷之火,浪潮之巅,数字化生存,赢,卓有成效的管理者,创新与企业家精神,第五项修炼,影响力变现,奈飞文化手册,商业冒险,门口的野蛮人,伟大的博弈
心理: 乌合之众,社会性动物,影响力,亲密关系,被讨厌的勇气,少有人走的路,自卑与超越,梦的解析,爱的艺术,逃避自由,我们内心的冲突,人性的弱点,情绪勒索,非暴力沟通,正念的奇迹,当下的力量,活出生命的意义,身体从未忘记,也许你该找个人聊聊,态度改变与社会影响,决策与判断,情商,沟通的艺术,人格心理学,发展心理学,社会心理学,认知天性,超越自由与尊严,象与骑象人,心理学与生活,思维的版图,选择的悖论,拖延心理学,怪诞行为学,思辨与立场,心理学导论,错觉的法则,噪声
传记: 史蒂夫·乔布斯传,富兰克林自传,居里夫人传,我的奋斗,当呼吸化为空气,维特根斯坦传,爱因斯坦传,达·芬奇传,成为波伏瓦,苏东坡传,曾国藩传,邓小平时代,切·格瓦拉传,甘地自传,褚时健传,渴望生活:梵高传,忏悔录,特斯拉传,拿破仑传,毛泽东传,丘吉尔传,林肯传,海明威传,卡夫卡传,普京传,马斯克传,人类群星闪耀时,巴菲特传,别闹了费曼先生,图灵传,玻尔传,凯恩斯传,维多利亚女王传,李光耀回忆录,基辛格传,知行合一王阳明
艺术: 艺术的故事,美的历程,论摄影,观看之道,艺术与错觉,什么是艺术,设计中的设计,写给大家看的设计书,色彩的秘密生活,建筑的永恒之道,音乐的极境,聆听音乐,艺术与视知觉,现代艺术150年,什么是当代艺术,后现代主义,建筑十书,空间诗学,日本侘寂,摄影的艺术,艺术哲学,西方美学史,中国书法史,中国画论辑要,印象派的敌人,加德纳艺术通史,如何看一幅画,书法有法,电影艺术
自然: 寂静的春天,物种起源,所罗门王的指环,昆虫记,看不见的森林,一平方英寸的寂静,荒野之声,博物学家的神秘动物图鉴,植物的欲望,半个地球,万物有灵且美,大灭绝时代,第六次大灭绝,地球上最后的夜晚,看不见的大自然,生命的跃升,三体问题天文,万物的终结,时间的秩序,树的秘密生命,土壤的故事,海洋的极端生命,缤纷的生命,大自然的猎人,杂草的故事,鸟的天赋
数学: 数学:确定性的丧失,素数的音乐,博弈论,如何解题,统计学的世界,信息简史,算法之美,千年难题,怎样解题,逻辑的引擎,费马大定理,数学女孩,天才的拓荒者,数学沉思录,概率论沉思录,几何原本,数学分析八讲,陶哲轩实分析,数论导引,从惊讶到思考,数学与猜想,什么是数学"""

EXTEND_TPL = """为《{book}》生成补充阅读内容。中文回答，输出严格JSON（不要markdown代码块）：
{{"themes":"3-5个深层主题，每个主题2-3句话展开，用\\n分段","questions":"3个引发思考的问题，帮助读者深入理解，用\\n分隔","author_story":"关于作者的一个有趣故事或背景（150-200字）","related":"3本相关推荐书籍，每本一句话说明为什么相关，用\\n分隔"}}"""

PROMPT_TPL = """为以下书籍生成中文推荐。deep_dive 300-500字像聊天口吻，quotes 2-3条金句。输出严格JSON（不要markdown代码块）：
{{"date":"{date}","books":[{{"title_zh":"中文书名","title_en":"English Title","author_zh":"作者","author_en":"Author","year":"年份","category":"分类","one_liner":"一句话概括","deep_dive":"深度介绍","quotes":[{{"text":"原文","context":"背景"}}]}}]}}

书籍：{books}"""

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
    generation_status[entry_id] = 'running'
    def _run():
        for attempt in range(2):
            try:
                print(f"[run] attempt {attempt+1} for {entry_id}", flush=True)
                result = subprocess.run(
                    [CLAUDE, "-p", "--model", "haiku", prompt],
                    cwd=ROOT, capture_output=True, text=True, timeout=300,
                    env={**os.environ, 'NO_COLOR': '1'}
                )
                output = result.stdout.strip()
                # Save raw output for debugging
                with open(os.path.join(DATA, f".debug_{entry_id}.txt"), 'w') as df:
                    df.write(output)
                start = output.find('{')
                end = output.rfind('}') + 1
                if start >= 0 and end > start:
                    data = repair_json(output[start:end])
                    if 'books' not in data:
                        raise ValueError("JSON missing 'books' key")
                    data['id'] = entry_id
                    path = os.path.join(DATA, f"{entry_id}.json")
                    with open(path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    update_index(entry_id)
                    subprocess.run(["git", "add", "data/"], cwd=ROOT)
                    subprocess.run(["git", "commit", "-m", f"Add books {entry_id}"], cwd=ROOT)
                    subprocess.run(["git", "push"], cwd=ROOT)
                    generation_status[entry_id] = 'done'
                    print(f"[done] {entry_id}", flush=True)
                    return  # success
                else:
                    print(f"[retry] No JSON found, attempt {attempt+1}", flush=True)
            except Exception as e:
                print(f"[retry] {e}, attempt {attempt+1}", flush=True)
        generation_status[entry_id] = 'error'
        print(f"[error] All attempts failed for {entry_id}", flush=True)
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
                    [CLAUDE, "-p", "--model", "haiku", prompt],
                    cwd=ROOT, capture_output=True, text=True, timeout=180,
                    env={**os.environ, 'NO_COLOR': '1'}
                )
                output = result.stdout.strip()
                start = output.find('{')
                end = output.rfind('}') + 1
                if start >= 0 and end > start:
                    ext = repair_json(output[start:end])
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

        if parsed.path == "/api/surprise":
            used = list(get_used_books())
            # Only pass last 20 to keep prompt short
            recent = ','.join(used[-20:]) if used else '无'
            prompt = f"""自选3本好书并生成推荐内容。要求：选冷门经典、近年新书、非虚构各一本，不同国家作者。不要选这些书：{recent}

输出严格JSON（不要markdown代码块）：
{{"date":"{today}","books":[{{"title_zh":"中文书名","title_en":"English Title","author_zh":"作者","author_en":"Author","year":"年份","category":"分类","one_liner":"一句话概括","deep_dive":"500-800字深度介绍，像跟朋友聊天","quotes":[{{"text":"原文金句","context":"背景"}}]}}]}}"""
            eid = run_claude(prompt)
            print(f"[surprise] excluded {len(used)} used books", flush=True)
            return self._json({"status": "generating", "id": eid, "mode": "surprise"})

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
                if generation_status.get(eid) == 'error':
                    return self._json({"ready": False, "error": True, "id": eid})
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
