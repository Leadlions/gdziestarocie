#!/usr/bin/env python3
"""
Daily blog post generator for gdziestarocie.pl
Uses Anthropic API to write a Polish-language article, then saves it
as a Markdown file in src/content/blog/.

Usage:
  python generate_post.py            # picks next unused topic
  python generate_post.py --dry-run  # prints output without saving
"""

import anthropic
import json
import os
import re
import sys
import datetime
import argparse
from pathlib import Path

# ── paths ────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).resolve().parents[2]
TOPICS_FILE = Path(__file__).parent / "topics.json"
BLOG_DIR    = ROOT / "src" / "content" / "blog"

# ── model ────────────────────────────────────────────────────────────────────
MODEL      = "claude-3-haiku-20240307"
MAX_TOKENS = 2048

# ── prompts ──────────────────────────────────────────────────────────────────
SYSTEM = (
    "Jesteś redaktorem portalu gdziestarocie.pl — polskiego kalendarza targów staroci i antyków. "
    "Piszesz po polsku, naturalnie i rzeczowo. Twój czytelnik to kolekcjoner lub miłośnik vintage "
    "z pewnym doświadczeniem. Unikaj pustych fraz marketingowych i słów 'fascynujący', 'niezwykły'."
)

# NOTE: {{ and }} are literal braces in .format() strings
USER_TEMPLATE = (
    'Napisz artykuł blogowy na temat: "{title}"\n\n'
    "Zwróć WYŁĄCZNIE poprawny obiekt JSON bez żadnego tekstu przed ani po i bez bloków kodu.\n"
    "Wymagana struktura:\n"
    '{{"description":"<meta opis, 1-2 zdania, max 155 znaków>","tags":["tag1","tag2"],"content":"<treść w Markdown>"}}\n\n'
    "Wymagania dotyczące treści:\n"
    "- Długość: 450-600 słów\n"
    "- Nagłówki H2 (##), opcjonalnie listy (-)\n"
    "- Wskocz od razu w temat, bez wstępów w stylu 'Antyki to...'\n"
    "- Zakończ akapitem z linkiem: sprawdź [terminarz targów](/) lub [stronę główną](/)\n"
    "- Tagi: 2-4 słowa kluczowe, małe litery, po polsku\n"
    "- W polu content używaj \\n dla nowych linii (to pole JSON, nie raw Markdown)\n"
)


def load_topics() -> list:
    with open(TOPICS_FILE, encoding="utf-8") as f:
        return json.load(f)


def existing_slugs() -> set:
    slugs = set()
    for path in BLOG_DIR.glob("*.md"):
        slugs.add(path.stem)
    return slugs


def pick_topic(topics: list, used: set):
    for topic in topics:
        if topic["slug"] not in used:
            return topic
    return None


def extract_json(text: str) -> str:
    """Try multiple strategies to extract JSON from model output."""
    text = text.strip()

    # Strategy 1: strip markdown code fences
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()

    # Strategy 2: if it starts with { — take it as-is
    if text.startswith("{"):
        return text

    # Strategy 3: find first { ... } block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)

    return text


def call_api(title: str) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY is not set or empty.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    try:
        message = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM,
            messages=[{"role": "user", "content": USER_TEMPLATE.format(title=title)}],
        )
    except anthropic.APIError as e:
        print(f"[ERROR] Anthropic API error: {e}", file=sys.stderr)
        sys.exit(1)

    raw = message.content[0].text
    print(f"[DEBUG] Raw API response (first 300 chars):\n{raw[:300]}", flush=True)

    candidate = extract_json(raw)

    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON parse failed: {e}", file=sys.stderr)
        print(f"[ERROR] Attempted to parse:\n{candidate}", file=sys.stderr)
        sys.exit(1)


def build_frontmatter(topic: dict, description: str, tags: list) -> str:
    today = datetime.date.today().isoformat()
    # Escape double quotes in title/description
    safe_title = topic["title"].replace('"', '\\"')
    safe_desc  = description.replace('"', '\\"')
    tag_str    = ", ".join(f'"{t}"' for t in tags)
    return (
        "---\n"
        f'title: "{safe_title}"\n'
        f'description: "{safe_desc}"\n'
        f"publishedAt: {today}\n"
        f"tags: [{tag_str}]\n"
        "author: Redakcja gdziestarocie.pl\n"
        "---\n\n"
    )


def save_post(slug: str, frontmatter: str, content: str) -> Path:
    BLOG_DIR.mkdir(parents=True, exist_ok=True)
    path = BLOG_DIR / f"{slug}.md"
    path.write_text(frontmatter + content.strip() + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    topics = load_topics()
    used   = existing_slugs()
    topic  = pick_topic(topics, used)

    if topic is None:
        print("[INFO] All 60 topics have been published. Nothing to do.")
        sys.exit(0)

    print(f"[INFO] Generating post: {topic['title']}", flush=True)

    result      = call_api(topic["title"])
    description = result.get("description", "")
    tags        = result.get("tags", topic.get("tags", []))
    content     = result.get("content", "")

    if not content:
        print("[ERROR] API returned empty content field.", file=sys.stderr)
        sys.exit(1)

    frontmatter = build_frontmatter(topic, description, tags)
    full_post   = frontmatter + content.strip() + "\n"

    if args.dry_run:
        print("\n" + "=" * 60)
        print(full_post[:800] + ("..." if len(full_post) > 800 else ""))
        print("=" * 60)
        print(f"\n[DRY-RUN] Would save: {BLOG_DIR / topic['slug']}.md")
        return

    path = save_post(topic["slug"], frontmatter, content)
    print(f"[OK] Saved: {path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        import traceback
        print("[FATAL] Unhandled exception:", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
