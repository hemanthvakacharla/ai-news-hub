# AI News Hub

A static website: Daily / Weekly / Monthly AI news tiles with like and dislike on every story.
GitHub hosts it for free and refreshes the news every day.

| File | What it does |
|---|---|
| `index.html` | The website. Loads stories from `news.json`. |
| `news.json` | The stories. Rewritten daily by the workflow. |
| `fetch_news.py` | Pulls RSS feeds, Hugging Face papers, arXiv and Google News topic searches into `news.json` (keeps 45 days), then asks a free AI tier (if a key is set) for summaries and selects. |
| `.github/workflows/update.yml` | Runs `fetch_news.py` four times a day (6 AM, 10 AM, 3 PM and 8 PM Eastern) and commits the result. |
| `config.js` + `supabase.sql` | Optional shared vote counts. |

## 1. Put it on GitHub (10 minutes)

1. Create a free account at github.com, then **New repository** → name it `ai-news-hub` → **Public** → Create.
2. On the new repository page choose **uploading an existing file**, drag in everything from this folder, and commit.
   The `.github` folder is hidden on Mac: press `Cmd+Shift+.` in Finder to see it. If drag-and-drop skips it,
   use **Add file → Create new file**, type `.github/workflows/update.yml` as the name, and paste the file's contents.
3. **Settings → Pages** → Source: *Deploy from a branch* → Branch: `main`, folder `/ (root)` → Save.
   After a minute the site is live at `https://<your-username>.github.io/ai-news-hub/`.
4. **Settings → Actions → General** → Workflow permissions → **Read and write permissions** → Save.
5. **Actions** tab → *Update news* → **Run workflow** to test it. A green tick and a new "Update news" commit mean daily updates work.

## 2. Connect your domain

1. Buy the domain anywhere (Cloudflare, Namecheap, Porkbun, Squarespace…).
2. In the registrar's DNS settings add:
   - four `A` records for `@` → `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
   - one `CNAME` record for `www` → `<your-username>.github.io`
3. In GitHub **Settings → Pages → Custom domain**, enter the domain and Save (this adds a `CNAME` file to the repo — leave it there).
4. When the DNS check passes (minutes to a few hours), tick **Enforce HTTPS**.

## 3. Shared vote counts (optional, free)

Out of the box each visitor's votes are saved in their own browser only. To show everyone's totals:

1. Create a free project at supabase.com.
2. **SQL Editor** → paste `supabase.sql` → Run.
3. **Project Settings → API**: copy the *Project URL* and the *anon public* key into `config.js`, commit.

Votes are anonymous (a random id per browser), so someone determined can vote more than once by clearing their
browser data. That is normal for a login-free thumbs up/down.

## 4. AI-written summaries (free)

Each daily run makes **one** AI request to write the one-line summaries and pick the weekly/monthly selects.
Without a key the run still succeeds: tiles show the feed's own excerpt and selects follow a simple rule
(newest story per source).

To turn AI summaries on, get a free key from any provider below (no credit card), then in the repository go to
**Settings → Secrets and variables → Actions** and add a *secret* named `AI_API_KEY` with the key. If you pick a
provider other than Gemini, also add a *variable* `AI_PROVIDER` with its name.

| `AI_PROVIDER` | Get a free key at | Notes |
|---|---|---|
| `gemini` (default) | aistudio.google.com → Get API key | Generous free tier; free-tier prompts may be used by Google to improve products. |
| `groq` | console.groq.com | Very fast, open models. |
| `openrouter` | openrouter.ai/keys | Rotating free models, about 50 requests/day. |
| `cerebras` | cloud.cerebras.ai | Fast, open models. |
| `mistral` | console.mistral.ai | "Experiment" plan. |
| `none` | | Turn AI off. |

(GitHub's own free "GitHub Models" service was retired in July 2026, so it can't be used here.)

Free model names change a few times a year. If the Actions log shows `AI: <model> failed`, set a variable
`AI_MODEL` to a current model id from that provider's model list (comma-separated ids are tried in order).
Free tiers also have no uptime promise; a missed day just means excerpts instead of summaries.

## Changing things

- **Refresh time:** edit the `cron` line in `update.yml` (UTC). `0 */6 * * *` = every 6 hours.
- **Sources and topics:** edit `FEEDS` and `RULES` at the top of `fetch_news.py`.
- **Pick a select by hand:** in `news.json` set a story's `"wp": true` (weekly) or `"mp": true` (monthly).
- GitHub pauses scheduled workflows after 60 days with no repository activity; the daily commit prevents that.
