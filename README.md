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

## Setup

Requires [runprompt](https://github.com/chr15m/runprompt) and an API key:

```bash
export ANTHROPIC_API_KEY="your-key"
```

## Tools

- `steam_tools.py` - Steam store search, app details, and reviews
- `research_tools.py` - Wikipedia, academic search, Reddit, Hacker News, and more
