# Agent Prompts

A collection of research and analysis agent prompts for [runprompt](https://github.com/chr15m/runprompt).

## Prompts

### `research.prompt`

General-purpose deep research agent. Gathers information from Wikipedia, academic databases (OpenAlex, arXiv, PubMed), community discussions (Reddit, Hacker News), and more.

```bash
./research.prompt "history of the QWERTY keyboard layout"
```

### `search.prompt`

Quick-answer assistant for simple questions. Tries instant answers first, then Wikipedia or community sources as needed.

```bash
./search.prompt "What year was the first iPhone released?"
```

### `alternatives.prompt`

Research alternatives to a product, tool, or service. Finds competing products, open-source options, and pricing information.

```bash
./alternatives.prompt "Notion"
```

### `competitor_analysis.prompt`

Perform competitive intelligence analysis for a product idea or market category. Identifies competitors, revenue signals, marketing strategies, and market gaps.

```bash
./competitor_analysis.prompt "AI-powered note-taking app"
```

### `customer-needs-research.prompt`

Discover what customers need, want, and buy in a specific market. Gathers evidence from community discussions with verbatim quotes.

```bash
./customer-needs-research.prompt "freelance UX designers"
```

### `customer-segmentation.prompt`

Identify distinct customer segments and use cases within a market or product category.

```bash
./customer-segmentation.prompt "Excel power users"
```

### `jobs-to-be-done.prompt`

Apply the Jobs to Be Done framework to understand customer progress and hiring/firing decisions.

```bash
./jobs-to-be-done.prompt "small pizza shop owners in Australia"
```

### `domain_research.prompt`

Brainstorm and check availability of domain names using RDAP lookups.

```bash
./domain_research.prompt "I need a domain for a web-based game console emulator"
```

### `github_issues.prompt`

Extract and categorize GitHub issues based on specific queries.

```bash
./github_issues.prompt "microsoft/vscode: performance problems"
```

### `images_to_markdown.prompt`

Convert images (screenshots, diagrams, documents) to structured Markdown descriptions. Use with `--file` to attach images.

```bash
./images_to_markdown.prompt --file screenshot.png
```

### `software-spec.prompt`

Iteratively develop a detailed software specification through guided questions. Requires project files to be attached.

```bash
./software-spec.prompt --file README.md
```

### `web_extract.prompt`

Interactively explore and extract content from web pages using browser automation.

```bash
./web_extract.prompt "Extract all reviews from https://example.com/reviews"
```

### `youtube_to_article.prompt`

Convert YouTube video transcripts into well-formatted articles.

```bash
./youtube_to_article.prompt "https://www.youtube.com/watch?v=VIDEO_ID"
```

### Steam Analysis Prompts

#### `steam_reviews.prompt`

Analyzes Steam reviews to extract what players liked and disliked about a game.

```bash
./steam_reviews.prompt "Hades"
./steam_reviews.prompt "1145360"  # by app ID
```

#### `steam_hooks_analysis.prompt`

Applies the "hooks framework" from Ryan Chambers' GDC talk to analyze a game's marketability. Evaluates what makes a game memorable, discussable, and shareable.

```bash
./steam_hooks_analysis.prompt "Vampire Survivors"
```

#### `steam_mechanics_aesthetics_analysis.prompt`

Documents a game's mechanics, aesthetics, and game feel in enough detail for a developer to create something similar.

```bash
./steam_mechanics_aesthetics_analysis.prompt "Celeste"
```

### `userinterfaces.prompt`

Reverse-engineer UI elements from screenshots and generate a standalone HTML implementation.

```bash
./userinterfaces.prompt --file ui-screenshot.png
```

## Setup

Requires [runprompt](https://github.com/chr15m/runprompt) and an API key:

```bash
export ANTHROPIC_API_KEY="your-key"
```

## Creating New `.prompt` Files

This repo's prompts follow the Dotprompt format used by `runprompt`: a
frontmatter block (YAML) plus a plain-text prompt template.

### 1) Start with a minimal prompt skeleton

Use a shebang so the prompt is executable:

```text
#!/usr/bin/env runprompt
---
tools:
  - builtin.datetime
---
Your instructions...

## Input

{{INPUT}}
```

Notes:

- This repo intentionally does not pin models in `.prompt` files.
  Configure your preferred default model via `runprompt` config,
  environment variables, or CLI flags.
- `{{INPUT}}` is the default merged input (stdin if present, else args).
- Many prompts in this repo use `{{INPUT}}` only; some also include
  `{{STDIN}}` and/or `{{ARGS}}` when they want both displayed.
- Keep the prompt itself deterministic and explicit about output format.

### 2) Declare tools in frontmatter

This repo uses three common patterns:

- Import all tools from a module:

  ```yaml
  tools:
    - research_tools.*
  ```

- Import specific tools only (tighter surface area):

  ```yaml
  tools:
    - research_tools.wikipedia_search
    - research_tools.wikipedia_article
  ```

- Use builtin tools:

  ```yaml
  tools:
    - builtin.datetime
    - builtin.fetch_clean
  ```

### 3) Decide on output behavior early

Two common styles:

- Write to stdout only (most prompts here):
  - Explicitly say "Output Markdown to stdout only."
- Write to a file via a parameterized builtin tool:
  - Example pattern used by `research.prompt`:

    ```yaml
    tools:
      - builtin.write_file("REPORT.md")
    ```

    Then instruct: "Write the result into `REPORT.md`."

## Creating Python Tool Modules

Tools are normal Python functions with docstrings. `runprompt` exposes any
function with a docstring as a callable tool.

### Tool design conventions used in this repo

- Return JSON-serializable dicts/lists/strings.
- Avoid raising for routine failure; return a small `{ "error": "..." }`
  dict for fetch failures (see `*_fetch_json` implementations).
- Add a recognizable `User-Agent` header to outbound HTTP requests.
- Cap response sizes and item counts to control context growth:
  - `MAX_ITEMS` for list endpoints
  - `MAX_CONTENT_LENGTH` and `_truncate()` for long text
- Prefer plain text results over HTML:
  - `research_tools.py` converts HTML to text (`_html_to_text()`).
- Mark read-only tools safe so they can be auto-approved when
  `--safe-yes` is used:

  ```python
  def my_tool(arg: str):
      """Does a read-only lookup."""
      return {"arg": arg}

  my_tool.safe = True
  ```

### Suggested module layout (mirrors `research_tools.py` / `steam_tools.py`)

- Constants at top: timeouts, item limits, truncation limits
- Internal helpers prefixed with `_` (not exposed via wildcard tool imports)
- Public tool functions with docstrings and small, predictable return shapes
- `tool.safe = True` assignments near the tool definitions

## Notes Worth Calling Out (in addition to the upstream runprompt README)

- Wildcard imports exclude underscore-prefixed functions/files:
  internal helpers should be named `_helper` to avoid accidental exposure.
- Tools are expected to be fast and bounded:
  always set timeouts and truncate large payloads.
- Some sources are rate-limited or return inconsistent fields:
  tool code should tolerate missing keys and partial results.
- Reddit endpoints used here are unauthenticated JSON endpoints:
  availability and rate limits vary; always handle HTTP errors cleanly.

## Tools

### `steam_tools.py`

- `steam_search(query)` - Search Steam store for games by name
- `steam_app_details(app_id)` - Get detailed game info (description, genres, tags, etc.)
- `steam_reviews(app_id, num_reviews, filter)` - Fetch Steam reviews

### `research_tools.py`

**General Knowledge**
- `duckduckgo_instant(query)` - Quick facts and instant answers
- `wikipedia_search(query)` - Find Wikipedia articles
- `wikipedia_article(title)` - Get full Wikipedia article content
- `wikidata_search(query)` - Search structured knowledge base

**Academic & Scholarly**
- `openalex_search(query)` - Search 250M+ academic papers
- `arxiv_search(query)` - Search preprints (physics, math, CS, biology, stats)
- `pubmed_search(query)` - Search 35M+ biomedical articles
- `google_scholar_search(query)` - Search Google Scholar (HTML scraping; may block)
- `crossref_search(query)` - Search DOI metadata

**Books**
- `open_library_search(query)` - Search books and publications

**Code & Tech**
- `github_search(query)` - Search GitHub repositories
- `github_repo(owner, repo)` - Get repository details

**Community**
- `hackernews_search(query)` - Search Hacker News discussions
- `reddit_search(query, subreddit)` - Search Reddit posts

### `reddit_tools.py`

- `reddit_list(subreddit, sort, t, limit)` - List posts in a subreddit by sort and time window
- `reddit_comments(permalink_or_url, sort, limit)` - Fetch comments for a Reddit post

### `github_tools.py`

- `github_issues_list(owner, repo, state, sort, direction, per_page, max_pages)` - List issues from a repository with pagination
- `github_issues_search(owner, repo, query, sort, order, per_page)` - Search issues in a repository
- `github_issue_comments(owner, repo, issue_number)` - Fetch all comments for a specific issue

### `youtube_tools.py`

- `youtube_feed_xml(user, channel_id, limit)` - Fetch YouTube's public Atom feed (videos.xml)
- `youtube_channel_videos(channel_id, user, limit)` - List a channel's uploaded videos using scrapetube
- `youtube_oembed(url_or_id)` - Fetch YouTube metadata via the public oEmbed endpoint
- `youtube_metadata_pytube(url_or_id)` - Fetch YouTube metadata via pytube
- `youtube_transcript(url_or_id, prepend_timestamps)` - Fetch a YouTube transcript

### `domain_tools.py`

- `rdap_domain(domain)` - Look up a domain via RDAP and infer availability
