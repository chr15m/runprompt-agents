# Agent Prompts

A collection of research and analysis agent prompts for [runprompt](https://github.com/chr15m/runprompt).

## Prompts

### `research.prompt`

General-purpose deep research agent. Gathers information from Wikipedia, academic databases (OpenAlex, arXiv, PubMed), community discussions (Reddit, Hacker News), and more.

```bash
echo "history of the QWERTY keyboard layout" | ./research.prompt
```

### `steam_reviews.prompt`

Analyzes Steam reviews to extract what players liked and disliked about a game.

```bash
echo "Hades" | ./steam_reviews.prompt
echo "1145360" | ./steam_reviews.prompt  # by app ID
```

### `steam_hooks_analysis.prompt`

Applies the "hooks framework" from Ryan Chambers' GDC talk to analyze a game's marketability. Evaluates what makes a game memorable, discussable, and shareable.

```bash
echo "Vampire Survivors" | ./steam_hooks_analysis.prompt
```

### `steam_mechanics_aesthetics_analysis.prompt`

Documents a game's mechanics, aesthetics, and game feel in enough detail for a developer to create something similar.

```bash
echo "Celeste" | ./steam_mechanics_aesthetics_analysis.prompt
```

### `search.prompt`

Quick-answer assistant for simple questions. Tries instant answers first, then Wikipedia or community sources as needed.

```bash
echo "What year was the first iPhone released?" | ./search.prompt
```

## Setup

Requires [runprompt](https://github.com/chr15m/runprompt) and an API key:

```bash
export ANTHROPIC_API_KEY="your-key"
```

## Creating New `.prompt` Files

This repo’s prompts follow the Dotprompt format used by `runprompt`: a
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
  - Explicitly say “Output Markdown to stdout only.”
- Write to a file via a parameterized builtin tool:
  - Example pattern used by `research.prompt`:

    ```yaml
    tools:
      - builtin.write_file("REPORT.md")
    ```

    Then instruct: “Write the result into `REPORT.md`.”

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
- `crossref_search(query)` - Search DOI metadata

**Books**
- `open_library_search(query)` - Search books and publications

**Code & Tech**
- `github_search(query)` - Search GitHub repositories
- `github_repo(owner, repo)` - Get repository details

**Community**
- `hackernews_search(query)` - Search Hacker News discussions
- `reddit_search(query, subreddit)` - Search Reddit posts

**General**
- `fetch_url(url)` - Fetch any URL as plain text
