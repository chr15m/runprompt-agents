"""Research tools for fetching information from various APIs."""

import urllib.request
import urllib.parse
import urllib.error
import json
import re
from html.parser import HTMLParser

MAX_CONTENT_LENGTH = 8000
MAX_ITEMS = 10
TIMEOUT = 30


class _HTMLTextExtractor(HTMLParser):
    """Extract plain text from HTML, stripping tags."""
    
    def __init__(self):
        super().__init__()
        self.result = []
        self.skip_tags = {'script', 'style', 'head', 'meta', 'link', 'noscript'}
        self.current_skip = 0
        self.in_pre = False
    
    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self.current_skip += 1
        if tag == 'pre':
            self.in_pre = True
        if tag in ('p', 'div', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'tr'):
            self.result.append('\n')
    
    def handle_endtag(self, tag):
        if tag in self.skip_tags:
            self.current_skip -= 1
        if tag == 'pre':
            self.in_pre = False
        if tag in ('p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self.result.append('\n')
    
    def handle_data(self, data):
        if self.current_skip > 0:
            return
        if self.in_pre:
            self.result.append(data)
        else:
            text = data.strip()
            if text:
                self.result.append(text + ' ')
    
    def get_text(self):
        text = ''.join(self.result)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        return text.strip()


def _html_to_text(html):
    """Convert HTML to plain text."""
    parser = _HTMLTextExtractor()
    try:
        parser.feed(html)
        return parser.get_text()
    except Exception:
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.I)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.I)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()


def _truncate(text, max_len=MAX_CONTENT_LENGTH):
    """Truncate text to max length with indicator."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "\n\n[... truncated, %d more characters ...]" % (len(text) - max_len)


def _fetch_json(url, headers=None):
    """Fetch URL and parse as JSON."""
    req_headers = {"User-Agent": "research-tool/1.0"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return {"error": "HTTP %d: %s" % (e.code, e.reason)}
    except urllib.error.URLError as e:
        return {"error": "URL error: %s" % str(e.reason)}
    except Exception as e:
        return {"error": str(e)}


def _fetch_text(url):
    """Fetch URL and return as text."""
    req = urllib.request.Request(url, headers={"User-Agent": "research-tool/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            content_type = resp.headers.get('Content-Type', '')
            data = resp.read().decode('utf-8', errors='replace')
            if 'html' in content_type.lower() or data.strip().startswith('<!') or data.strip().startswith('<html'):
                return _html_to_text(data)
            return data
    except urllib.error.HTTPError as e:
        return "Error: HTTP %d: %s" % (e.code, e.reason)
    except urllib.error.URLError as e:
        return "Error: %s" % str(e.reason)
    except Exception as e:
        return "Error: %s" % str(e)


def duckduckgo_instant(query: str):
    """Search DuckDuckGo Instant Answers for quick facts.
    
    Returns instant answers, abstracts, and related topics for a query.
    Good for quick factual lookups and definitions.
    """
    url = "https://api.duckduckgo.com/?q=%s&format=json&no_html=1&skip_disambig=1" % urllib.parse.quote(query)
    data = _fetch_json(url)
    if "error" in data:
        return data
    result = {"query": query}
    if data.get("Abstract"):
        result["abstract"] = data["Abstract"]
        result["abstract_source"] = data.get("AbstractSource", "")
        result["abstract_url"] = data.get("AbstractURL", "")
    if data.get("Answer"):
        result["answer"] = data["Answer"]
    if data.get("Definition"):
        result["definition"] = data["Definition"]
        result["definition_source"] = data.get("DefinitionSource", "")
    if data.get("RelatedTopics"):
        topics = []
        for topic in data["RelatedTopics"][:MAX_ITEMS]:
            if isinstance(topic, dict) and topic.get("Text"):
                topics.append({
                    "text": topic["Text"][:200],
                    "url": topic.get("FirstURL", "")
                })
        if topics:
            result["related_topics"] = topics
    if len(result) == 1:
        result["note"] = "No instant answer available. Try wikipedia_search or fetch_url for more detailed results."
    return result


def wikipedia_search(query: str):
    """Search Wikipedia for articles matching a query.
    
    Returns a list of matching article titles and snippets.
    Use wikipedia_article() to get the full content of a specific article.
    """
    url = "https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=%s&format=json&origin=*&srlimit=%d" % (
        urllib.parse.quote(query), MAX_ITEMS)
    data = _fetch_json(url)
    if "error" in data:
        return data
    results = []
    for item in data.get("query", {}).get("search", []):
        snippet = re.sub(r'<[^>]+>', '', item.get("snippet", ""))
        results.append({
            "title": item.get("title", ""),
            "snippet": snippet,
            "url": "https://en.wikipedia.org/wiki/%s" % urllib.parse.quote(item.get("title", "").replace(" ", "_"))
        })
    return {"query": query, "results": results}


def wikipedia_article(title: str):
    """Get the content of a Wikipedia article by title.
    
    Returns the article summary and main content as plain text.
    Use wikipedia_search() first to find the correct article title.
    """
    url = "https://en.wikipedia.org/api/rest_v1/page/summary/%s" % urllib.parse.quote(title.replace(" ", "_"))
    summary_data = _fetch_json(url)
    result = {"title": title}
    if "error" in summary_data:
        result["error"] = summary_data["error"]
        return result
    result["summary"] = summary_data.get("extract", "")
    result["url"] = summary_data.get("content_urls", {}).get("desktop", {}).get("page", "")
    content_url = "https://en.wikipedia.org/w/api.php?action=query&titles=%s&prop=extracts&explaintext=1&format=json&origin=*" % urllib.parse.quote(title.replace(" ", "_"))
    content_data = _fetch_json(content_url)
    pages = content_data.get("query", {}).get("pages", {})
    for page_id, page in pages.items():
        if page_id != "-1":
            content = page.get("extract", "")
            result["content"] = _truncate(content)
            break
    return result


def github_search(query: str):
    """Search GitHub repositories.
    
    Returns matching repositories with descriptions and stats.
    Use github_repo() to get more details about a specific repository.
    """
    url = "https://api.github.com/search/repositories?q=%s&per_page=%d" % (
        urllib.parse.quote(query), MAX_ITEMS)
    data = _fetch_json(url)
    if "error" in data:
        return data
    results = []
    for repo in data.get("items", []):
        results.append({
            "name": repo.get("full_name", ""),
            "description": (repo.get("description") or "")[:200],
            "url": repo.get("html_url", ""),
            "stars": repo.get("stargazers_count", 0),
            "language": repo.get("language", ""),
            "updated": repo.get("updated_at", "")[:10]
        })
    return {"query": query, "total_count": data.get("total_count", 0), "results": results}


def github_repo(owner: str, repo: str):
    """Get details about a specific GitHub repository.
    
    Returns repository info including README content.
    """
    url = "https://api.github.com/repos/%s/%s" % (
        urllib.parse.quote(owner), urllib.parse.quote(repo))
    data = _fetch_json(url)
    if "error" in data:
        return data
    result = {
        "name": data.get("full_name", ""),
        "description": data.get("description", ""),
        "url": data.get("html_url", ""),
        "stars": data.get("stargazers_count", 0),
        "forks": data.get("forks_count", 0),
        "language": data.get("language", ""),
        "topics": data.get("topics", []),
        "created": data.get("created_at", "")[:10],
        "updated": data.get("updated_at", "")[:10],
        "license": (data.get("license") or {}).get("name", "")
    }
    readme_url = "https://api.github.com/repos/%s/%s/readme" % (
        urllib.parse.quote(owner), urllib.parse.quote(repo))
    readme_data = _fetch_json(readme_url, headers={"Accept": "application/vnd.github.raw"})
    if isinstance(readme_data, dict) and "error" not in readme_data:
        if readme_data.get("content"):
            import base64
            try:
                readme_content = base64.b64decode(readme_data["content"]).decode('utf-8')
                result["readme"] = _truncate(readme_content, 4000)
            except Exception:
                pass
    return result


def hackernews_search(query: str):
    """Search Hacker News for stories and discussions.
    
    Returns matching stories with titles, points, and comment counts.
    Good for finding tech community discussions and opinions.
    """
    url = "https://hn.algolia.com/api/v1/search?query=%s&hitsPerPage=%d" % (
        urllib.parse.quote(query), MAX_ITEMS)
    data = _fetch_json(url)
    if "error" in data:
        return data
    results = []
    for hit in data.get("hits", []):
        results.append({
            "title": hit.get("title", "") or hit.get("story_title", ""),
            "url": hit.get("url", ""),
            "hn_url": "https://news.ycombinator.com/item?id=%s" % hit.get("objectID", ""),
            "points": hit.get("points", 0),
            "comments": hit.get("num_comments", 0),
            "author": hit.get("author", ""),
            "date": hit.get("created_at", "")[:10]
        })
    results = [r for r in results if r["title"]]
    return {"query": query, "results": results}


def reddit_search(query: str, subreddit: str = ""):
    """Search Reddit for posts and discussions.
    
    Optionally filter by subreddit. Returns post titles, scores, and comment counts.
    Good for finding community discussions and diverse opinions.
    """
    if subreddit:
        url = "https://www.reddit.com/r/%s/search.json?q=%s&restrict_sr=1&limit=%d" % (
            urllib.parse.quote(subreddit), urllib.parse.quote(query), MAX_ITEMS)
    else:
        url = "https://www.reddit.com/search.json?q=%s&limit=%d" % (
            urllib.parse.quote(query), MAX_ITEMS)
    data = _fetch_json(url)
    if "error" in data:
        return data
    results = []
    for child in data.get("data", {}).get("children", []):
        post = child.get("data", {})
        results.append({
            "title": post.get("title", ""),
            "subreddit": post.get("subreddit", ""),
            "url": "https://reddit.com%s" % post.get("permalink", ""),
            "score": post.get("score", 0),
            "comments": post.get("num_comments", 0),
            "selftext": _truncate(post.get("selftext", ""), 500) if post.get("selftext") else ""
        })
    return {"query": query, "subreddit": subreddit or "all", "results": results}


def open_library_search(query: str):
    """Search Open Library for books.
    
    Returns matching books with titles, authors, and publication info.
    Good for finding books and publications on a topic.
    """
    url = "https://openlibrary.org/search.json?q=%s&limit=%d" % (
        urllib.parse.quote(query), MAX_ITEMS)
    data = _fetch_json(url)
    if "error" in data:
        return data
    results = []
    for doc in data.get("docs", []):
        authors = doc.get("author_name", [])
        results.append({
            "title": doc.get("title", ""),
            "authors": authors[:3] if authors else [],
            "first_published": doc.get("first_publish_year", ""),
            "subjects": doc.get("subject", [])[:5] if doc.get("subject") else [],
            "url": "https://openlibrary.org%s" % doc.get("key", "") if doc.get("key") else ""
        })
    return {"query": query, "total_count": data.get("numFound", 0), "results": results}


def wikidata_search(query: str):
    """Search Wikidata for structured knowledge.
    
    Returns entities with descriptions and identifiers.
    Good for finding authoritative identifiers and structured facts.
    """
    url = "https://www.wikidata.org/w/api.php?action=wbsearchentities&search=%s&language=en&format=json&origin=*&limit=%d" % (
        urllib.parse.quote(query), MAX_ITEMS)
    data = _fetch_json(url)
    if "error" in data:
        return data
    results = []
    for item in data.get("search", []):
        results.append({
            "id": item.get("id", ""),
            "label": item.get("label", ""),
            "description": item.get("description", ""),
            "url": item.get("concepturi", "")
        })
    return {"query": query, "results": results}


def openalex_search(query: str):
    """Search OpenAlex for academic papers and scholarly works.
    
    Returns papers with titles, authors, publication info, and citation counts.
    OpenAlex indexes 250M+ works across all academic disciplines.
    Good for finding peer-reviewed research and citation data.
    """
    url = "https://api.openalex.org/works?search=%s&per_page=%d" % (
        urllib.parse.quote(query), MAX_ITEMS)
    data = _fetch_json(url, headers={"User-Agent": "research-tool/1.0 (mailto:research@example.com)"})
    if "error" in data:
        return data
    results = []
    for work in data.get("results", []):
        authors = []
        for authorship in work.get("authorships", [])[:3]:
            author = authorship.get("author", {})
            if author.get("display_name"):
                authors.append(author["display_name"])
        result = {
            "title": work.get("title", ""),
            "authors": authors,
            "year": work.get("publication_year", ""),
            "cited_by_count": work.get("cited_by_count", 0),
            "doi": work.get("doi", ""),
            "open_access": work.get("open_access", {}).get("is_oa", False),
        }
        if work.get("primary_location", {}).get("source", {}).get("display_name"):
            result["journal"] = work["primary_location"]["source"]["display_name"]
        if work.get("open_access", {}).get("oa_url"):
            result["pdf_url"] = work["open_access"]["oa_url"]
        abstract = work.get("abstract_inverted_index")
        if abstract:
            words = [""] * (max(max(positions) for positions in abstract.values()) + 1)
            for word, positions in abstract.items():
                for pos in positions:
                    words[pos] = word
            result["abstract"] = _truncate(" ".join(words), 500)
        results.append(result)
    return {
        "query": query,
        "total_count": data.get("meta", {}).get("count", 0),
        "results": results
    }


def arxiv_search(query: str):
    """Search arXiv for preprints in physics, math, CS, and related fields.
    
    Returns preprints with titles, authors, abstracts, and PDF links.
    arXiv is the primary repository for preprints in physics, mathematics,
    computer science, quantitative biology, statistics, and related fields.
    """
    url = "http://export.arxiv.org/api/query?search_query=all:%s&start=0&max_results=%d" % (
        urllib.parse.quote(query), MAX_ITEMS)
    req = urllib.request.Request(url, headers={"User-Agent": "research-tool/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = resp.read().decode('utf-8')
    except Exception as e:
        return {"error": str(e)}
    results = []
    entries = re.findall(r'<entry>(.*?)</entry>', data, re.DOTALL)
    for entry in entries:
        title_match = re.search(r'<title>(.*?)</title>', entry, re.DOTALL)
        title = title_match.group(1).strip().replace('\n', ' ') if title_match else ""
        title = re.sub(r'\s+', ' ', title)
        summary_match = re.search(r'<summary>(.*?)</summary>', entry, re.DOTALL)
        summary = summary_match.group(1).strip().replace('\n', ' ') if summary_match else ""
        summary = re.sub(r'\s+', ' ', summary)
        authors = re.findall(r'<author>\s*<name>(.*?)</name>', entry)
        id_match = re.search(r'<id>(.*?)</id>', entry)
        arxiv_url = id_match.group(1) if id_match else ""
        arxiv_id = arxiv_url.split('/abs/')[-1] if '/abs/' in arxiv_url else ""
        published_match = re.search(r'<published>(.*?)</published>', entry)
        published = published_match.group(1)[:10] if published_match else ""
        categories = re.findall(r'<category[^>]*term="([^"]*)"', entry)
        results.append({
            "title": title,
            "authors": authors[:5],
            "abstract": _truncate(summary, 500),
            "arxiv_id": arxiv_id,
            "url": arxiv_url,
            "pdf_url": arxiv_url.replace('/abs/', '/pdf/') + ".pdf" if arxiv_url else "",
            "published": published,
            "categories": categories[:5]
        })
    return {"query": query, "results": results}


def pubmed_search(query: str):
    """Search PubMed for biomedical and life sciences literature.
    
    Returns articles with titles, authors, abstracts, and PubMed IDs.
    PubMed indexes 35M+ citations from MEDLINE, life science journals,
    and online books. Essential for medical and biological research.
    """
    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=%s&retmax=%d&retmode=json" % (
        urllib.parse.quote(query), MAX_ITEMS)
    search_data = _fetch_json(search_url)
    if "error" in search_data:
        return search_data
    id_list = search_data.get("esearchresult", {}).get("idlist", [])
    if not id_list:
        return {"query": query, "results": []}
    ids = ",".join(id_list)
    fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=%s&retmode=xml" % ids
    req = urllib.request.Request(fetch_url, headers={"User-Agent": "research-tool/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            xml_data = resp.read().decode('utf-8')
    except Exception as e:
        return {"error": str(e)}
    results = []
    articles = re.findall(r'<PubmedArticle>(.*?)</PubmedArticle>', xml_data, re.DOTALL)
    for article in articles:
        title_match = re.search(r'<ArticleTitle>(.*?)</ArticleTitle>', article, re.DOTALL)
        title = title_match.group(1) if title_match else ""
        title = re.sub(r'<[^>]+>', '', title)
        abstract_match = re.search(r'<Abstract>(.*?)</Abstract>', article, re.DOTALL)
        abstract = ""
        if abstract_match:
            abstract_text = abstract_match.group(1)
            abstract_parts = re.findall(r'<AbstractText[^>]*>(.*?)</AbstractText>', abstract_text, re.DOTALL)
            abstract = " ".join(abstract_parts)
            abstract = re.sub(r'<[^>]+>', '', abstract)
        authors = []
        author_matches = re.findall(r'<Author[^>]*>(.*?)</Author>', article, re.DOTALL)
        for author in author_matches[:5]:
            lastname = re.search(r'<LastName>(.*?)</LastName>', author)
            forename = re.search(r'<ForeName>(.*?)</ForeName>', author)
            if lastname:
                name = lastname.group(1)
                if forename:
                    name = forename.group(1) + " " + name
                authors.append(name)
        pmid_match = re.search(r'<PMID[^>]*>(.*?)</PMID>', article)
        pmid = pmid_match.group(1) if pmid_match else ""
        year_match = re.search(r'<PubDate>.*?<Year>(.*?)</Year>', article, re.DOTALL)
        year = year_match.group(1) if year_match else ""
        journal_match = re.search(r'<Journal>.*?<Title>(.*?)</Title>', article, re.DOTALL)
        journal = journal_match.group(1) if journal_match else ""
        doi_match = re.search(r'<ArticleId IdType="doi">(.*?)</ArticleId>', article)
        doi = doi_match.group(1) if doi_match else ""
        results.append({
            "title": title,
            "authors": authors,
            "abstract": _truncate(abstract, 500),
            "pmid": pmid,
            "url": "https://pubmed.ncbi.nlm.nih.gov/%s/" % pmid if pmid else "",
            "year": year,
            "journal": journal,
            "doi": "https://doi.org/%s" % doi if doi else ""
        })
    return {
        "query": query,
        "total_count": int(search_data.get("esearchresult", {}).get("count", 0)),
        "results": results
    }


def crossref_search(query: str):
    """Search Crossref for DOI metadata and scholarly publications.
    
    Returns bibliographic metadata including DOIs, titles, authors, journals.
    Crossref indexes 130M+ records. Good for finding specific papers by
    title/author and getting accurate citation metadata. Use the DOI URL
    to access the full paper (may require subscription).
    """
    url = "https://api.crossref.org/works?query=%s&rows=%d" % (
        urllib.parse.quote(query), MAX_ITEMS)
    data = _fetch_json(url, headers={"User-Agent": "research-tool/1.0 (mailto:research@example.com)"})
    if "error" in data:
        return data
    results = []
    for item in data.get("message", {}).get("items", []):
        authors = []
        for author in item.get("author", [])[:5]:
            name_parts = []
            if author.get("given"):
                name_parts.append(author["given"])
            if author.get("family"):
                name_parts.append(author["family"])
            if name_parts:
                authors.append(" ".join(name_parts))
        title_list = item.get("title", [])
        title = title_list[0] if title_list else ""
        container = item.get("container-title", [])
        journal = container[0] if container else ""
        published = item.get("published-print", item.get("published-online", {}))
        date_parts = published.get("date-parts", [[]])[0]
        year = date_parts[0] if date_parts else ""
        doi = item.get("DOI", "")
        results.append({
            "title": title,
            "authors": authors,
            "journal": journal,
            "year": year,
            "doi": doi,
            "doi_url": "https://doi.org/%s" % doi if doi else "",
            "type": item.get("type", ""),
            "cited_by_count": item.get("is-referenced-by-count", 0)
        })
    return {
        "query": query,
        "total_count": data.get("message", {}).get("total-results", 0),
        "results": results
    }


def fetch_url(url: str):
    """Fetch any URL and return its content as plain text.
    
    HTML pages are converted to plain text with tags stripped.
    Use this for specific URLs you need to examine.
    Content is truncated to avoid filling context.
    """
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    text = _fetch_text(url)
    return {"url": url, "content": _truncate(text)}
