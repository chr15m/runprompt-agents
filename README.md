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
