#!/usr/bin/env python3
"""Pull the latest AI news into news.json. Run daily by .github/workflows/update.yml.

An AI model on a FREE tier writes the one-line summaries and picks the weekly/monthly selects
(default: Google Gemini via a free AI Studio key). If no AI is reachable it falls back to each feed's own excerpt.
"""
import datetime as dt, hashlib, html, json, os, re, sys, time
import feedparser, requests

KEEP_DAYS = 45            # how long stories stay in news.json (Monthly needs ~31)
PER_FEED = 8              # newest N stories taken from each feed per run
UA = {"User-Agent": "ai-news-hub/1.0 (+github actions)"}
gnews = lambda q: f"https://news.google.com/rss/search?q={requests.utils.quote(q)}+when:2d&hl=en-US&gl=US&ceid=US:en"

# (url, source label, colour class, topic or None to guess from keywords)
FEEDS = [
    ("https://techcrunch.com/category/artificial-intelligence/feed/", "TechCrunch", "tc", None),
    ("https://news.mit.edu/topic/mitartificial-intelligence2-rss.xml", "MIT News", "mit", None),
    ("https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss", "IEEE Spectrum", "ieee", None),
    ("https://blog.google/technology/ai/rss/", "Google AI Blog", "", "gemini"),
    ("https://vllm.ai/blog/rss.xml", "vLLM Blog", "", "engines"),
    ("https://huggingface.co/blog/feed.xml", "Hugging Face", "", None),
    ("http://export.arxiv.org/api/query?search_query=cat:cs.LG+AND+(abs:%22LLM+inference%22+OR+abs:quantization+OR+abs:%22KV+cache%22+OR+abs:%22mixture+of+experts%22+OR+abs:offloading)&sortBy=submittedDate&sortOrder=descending&max_results=12", "arXiv", "", "papers"),
    (gnews("Anthropic Claude"), None, "", "anthropic"),
    (gnews("Palantir AI"), None, "", "palantir"),
    (gnews("Google Gemini model"), None, "", "gemini"),
    (gnews('"new model" LLM release'), None, "", "models"),
    (gnews("LLM inference without GPU OR quantization OR CPU"), None, "", "eff"),
]

RULES = [  # first match wins
    ("anthropic", r"\banthropic\b|\bclaude\b"),
    ("palantir", r"\bpalantir\b"),
    ("gemini", r"\bgemini\b|deepmind|google ai"),
    ("engines", r"\bvllm\b|sglang|llama\.cpp|tensorrt|inference engine|kernel"),
    ("eff", r"quantiz|\bgpu\b|\bcpu\b|\bchip\b|nvidia|huawei|\bamd\b|inference cost|memory"),
    ("models", r"\bgpt-?\d|\bllama\b|\bqwen\b|deepseek|\bkimi\b|mistral|open[- ]weight|new model|releases? .*model"),
    ("papers", r"arxiv|\bpaper\b|researchers"),
    ("impl", r"deploy|rollout|launch|feature|agent|customers?|integrat|partnership"),
]

def clean(t, n=190):
    t = html.unescape(re.sub(r"<[^>]+>", " ", t or ""))
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= n else t[: n - 1].rsplit(" ", 1)[0] + "…"

def topic_for(text):
    for t, rx in RULES:
        if re.search(rx, text, re.I):
            return t
    return "industry"

def fetch_feed(url, src, cls, topic):
    out = []
    try:
        r = requests.get(url, headers=UA, timeout=30); r.raise_for_status()
    except Exception as e:
        print(f"skip {url[:60]}… ({e})", file=sys.stderr); return out
    for e in feedparser.parse(r.content).entries[:PER_FEED]:
        link, title = e.get("link"), clean(e.get("title"), 160)
        if not link or not title: continue
        when = e.get("published_parsed") or e.get("updated_parsed") or time.gmtime()
        source = src or clean((e.get("source") or {}).get("title") or "News", 40)
        if src is None:                                   # Google News appends " - Publisher"
            title = re.sub(r"\s+-\s+[^-]+$", "", title)
        summ = clean(e.get("summary"))
        if src is None or not summ or summ.lower().startswith(title.lower()[:40]):
            summ = ""
        out.append({"id": hashlib.sha1(link.encode()).hexdigest()[:10], "t": topic or topic_for(title + " " + summ),
                    "c": cls, "src": source, "d": time.strftime("%Y-%m-%d", when), "title": title,
                    "sum": summ, "url": link, "wp": False, "mp": False})
    return out

def hf_papers():
    try:
        rows = requests.get("https://huggingface.co/api/daily_papers", headers=UA, timeout=30).json()[:8]
    except Exception as e:
        print(f"skip HF papers ({e})", file=sys.stderr); return []
    out = []
    for r in rows:
        p = r.get("paper", {}); pid = p.get("id")
        if not pid: continue
        url = f"https://huggingface.co/papers/{pid}"
        out.append({"id": hashlib.sha1(url.encode()).hexdigest()[:10], "t": "papers", "c": "", "src": "HF Papers",
                    "d": (r.get("publishedAt") or dt.date.today().isoformat())[:10], "title": clean(p.get("title"), 160),
                    "sum": clean(p.get("summary")), "url": url, "wp": False, "mp": False})
    return out

# Free AI tiers. All speak the same "OpenAI-compatible" chat API, so switching is one setting (AI_PROVIDER).
# Model names change often: if a provider retires one, set AI_MODEL to a current id (comma-separated = tried in order).
PROVIDERS = {
    # GitHub Models was retired on 30 July 2026, so a free key from one of these is needed:
    "gemini":     ("https://generativelanguage.googleapis.com/v1beta/openai", "AI_API_KEY", "gemini-flash-latest,gemini-3.8-flash,gemini-3.7-flash"),
    "groq":       ("https://api.groq.com/openai/v1", "AI_API_KEY", "llama-3.3-70b-versatile"),
    "openrouter": ("https://openrouter.ai/api/v1", "AI_API_KEY", "openrouter/free,meta-llama/llama-3.3-70b-instruct:free"),
    "cerebras":   ("https://api.cerebras.ai/v1", "AI_API_KEY", "llama-3.3-70b"),
    "mistral":    ("https://api.mistral.ai/v1", "AI_API_KEY", "mistral-small-latest"),
}

def ask_ai(prompt):
    """Return the model's text reply, or None if no provider is set up / every model failed."""
    name = (os.environ.get("AI_PROVIDER") or "gemini").strip().lower()
    if name == "none": return None
    if name == "anthropic":                                    # paid, kept for anyone who prefers it
        key = os.environ.get("AI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
        if not key: return None
        for model in (os.environ.get("AI_MODEL") or "claude-haiku-4-5").split(","):
            try:
                r = requests.post("https://api.anthropic.com/v1/messages", timeout=120,
                                  headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                                  json={"model": model.strip(), "max_tokens": 4000, "messages": [{"role": "user", "content": prompt}]})
                r.raise_for_status(); return r.json()["content"][0]["text"]
            except Exception as e: print(f"AI: {model} failed ({e})", file=sys.stderr)
        return None
    if name not in PROVIDERS:
        print(f"AI: unknown AI_PROVIDER '{name}'", file=sys.stderr); return None
    base, key_env, models = PROVIDERS[name]
    base = os.environ.get("AI_BASE_URL") or base
    key = os.environ.get(key_env)
    if not key:
        print(f"AI: no {key_env} set, using feed excerpts", file=sys.stderr); return None
    for model in (os.environ.get("AI_MODEL") or models).split(","):
        for attempt in (1, 2, 3):                          # free tiers return 429/503 when busy: wait and retry
            try:
                r = requests.post(base.rstrip("/") + "/chat/completions", timeout=120,
                                  headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                                  json={"model": model.strip(), "temperature": 0.2, "messages": [{"role": "user", "content": prompt}]})
                if r.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                    print(f"AI: {model} busy ({r.status_code}), retrying in {30*attempt}s", file=sys.stderr); time.sleep(30 * attempt); continue
                r.raise_for_status()
                print(f"AI: used {name}/{model.strip()}"); return r.json()["choices"][0]["message"]["content"]
            except Exception as e:
                print(f"AI: {model} failed ({e})", file=sys.stderr); break
    return None

def ai_pass(new):
    """Optional: one AI call writes summaries and chooses selects for today's new stories."""
    if not new: return False
    new = new[:30]                                             # small batches keep free tiers happy
    listing = "\n".join(f'{i}. [{a["src"]}] {a["title"]} :: {a["sum"]}' for i, a in enumerate(new))
    prompt = ("You edit a technical AI news hub. For each numbered story write one plain, specific sentence (max 25 words, "
              "no hype, do not invent facts beyond the title and excerpt). Then choose selects: `week` = the ~6 most important "
              "stories, `month` = the ~2 that matter most this month (subset of week). Prefer concrete technical news over "
              "opinion and stock coverage.\n"
              'Reply with JSON only: {"sum": {"0": "..."}, "week": [0], "month": [0]}\n\n' + listing)
    text = ask_ai(prompt)
    if not text: return False
    try:
        data = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
    except Exception as e:
        print(f"AI: reply was not valid JSON, using feed excerpts ({e})", file=sys.stderr); return False
    for k, v in data.get("sum", {}).items():
        if k.isdigit() and int(k) < len(new) and isinstance(v, str): new[int(k)]["sum"] = clean(v, 220)
    for a in new: a["ai"] = True                               # remember these were summarized
    for i in data.get("week", []):
        if isinstance(i, int) and 0 <= i < len(new): new[i]["wp"] = True
    for i in data.get("month", []):
        if isinstance(i, int) and 0 <= i < len(new): new[i]["wp"] = new[i]["mp"] = True
    return True

def rule_selects(new):
    """No API key: the newest story from each source is a weekly select; the first two trusted ones are monthly."""
    seen, month = set(), 0
    for a in sorted(new, key=lambda a: a["d"], reverse=True):
        if a["src"] in seen: continue
        seen.add(a["src"]); a["wp"] = True
        if month < 2 and a["c"] in ("tc", "mit", "ieee"): a["mp"] = True; month += 1

def main():
    try: old = json.load(open("news.json"))["items"]
    except Exception: old = []
    known = {a["id"] for a in old} | {a["title"].lower() for a in old}
    found = hf_papers()
    for f in FEEDS: found += fetch_feed(*f)
    cutoff = (dt.date.today() - dt.timedelta(days=KEEP_DAYS)).isoformat()
    new = []
    for a in found:
        if a["id"] in known or a["title"].lower() in known or a["d"] < cutoff: continue
        known |= {a["id"], a["title"].lower()}; new.append(a)
    # also catch up on recent stories that never got an AI summary (e.g. from runs before the key was added)
    backlog = [a for a in old if not a.get("ai") and a["d"] >= (dt.date.today() - dt.timedelta(days=7)).isoformat()]
    if not ai_pass(new + backlog[:max(0, 30 - len(new))]): rule_selects(new)
    for a in new:
        if not a["sum"]: a["sum"] = f'From {a["src"]}.'
    items = sorted([a for a in new + old if a["d"] >= cutoff], key=lambda a: a["d"], reverse=True)
    json.dump({"updated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "items": items},
              open("news.json", "w"), ensure_ascii=False, indent=1)
    print(f"{len(new)} new stories, {len(items)} kept")

if __name__ == "__main__":
    main()
