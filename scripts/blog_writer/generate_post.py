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
ROOT = Path(__file__).resolve().parents[2]          # repo root
TOPICS_FILE  = Path(__file__).parent / "topics.json"
BLOG_DIR     = ROOT / "src" / "content" / "blog"

# ── model ────────────────────────────────────────────────────────────────────
MODEL = "claude-3-5-haiku-20241022"   # fast + cheap for daily automation
MAX_TOKENS = 2048

# ── prompt ───────────────────────────────────────────────────────────────────
SYSTEM = (
    "Jesteś redaktorem portalu gdziestarocie.pl — polskiego kalendarza targów staroci i antyków. "
    "Piszesz po polsku, naturalnie i rzeczowo. Twój czytelnik to kolekcjoner lub miłośnik vintage "
    "z pewnym doświadczeniem, który nie potrzebuje tłumaczenia, czym są antyki. "
    "Unikaj pustych fraz marketingowych i nadużywania słów 'fascynujący', 'niezwykły', 'wyjątkowy'."
)

USER_TEMPLATE = """\
Napisz artykuł blogowy na temat: "{title}"

Zwróć WYŁĄCZNIE poprawny obiekt JSON (bez żadnego tekstu przed ani po, bez bloków kodu), z dokładnie tymi polami:
{{
  "description": "<meta opis po polsku, 1–2 zdania, max 155 znaków>",
  "tags": ["<tag1>", "<tag2>"],
  "content": "<pełna treść artykułu w Markdown>"
}}

Wymagania dotyczące treści:
- Długość: 450–600 słów
- Nagłówki H2 (##), opcjonalnie listy (-)
- Nie zaczynaj od ogólnika — wskocz od razu w konkretny temat
- Zakończ akapitem z linkiem: sprawdź [terminarz targów](/) lub [stronę główną](/)
- Tagi: 2–4 słowa kluczowe, małe litery, po polsku
"""


def load_topics() -> list[dict]:
    with open(TOPICS_FILE, encoding="utf-8") as f:
        return json.load(f)


def existing_slugs() -> set[str]:
    """Return slugs of blog posts that already exist on disk."""
    slugs = set()
    for path in BLOG_DIR.glob("*.md"):
        if path.stem != ".gitkeep":
            slugs.add(path.stem)
    return slugs


def pick_topic(topics: list[dict], used: set[str]) -> dict | None:
    for topic in topics:
        if topic["slug"] not in used:
            return topic
    return None


def call_api(title: str) -> dict:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM,
        messages=[{"role": "user", "content": USER_TEMPLATE.format(title=title)}],
    )
    raw = message.content[0].text.strip()

    # Strip markdown code fences if model wrapped output
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[ERROR] API returned invalid JSON: {e}\n---\n{raw}\n---", file=sys.stderr)
        sys.exit(1)


def build_frontmatter(topic: dict, description: str, tags: list[str]) -> str:
    today = datetime.date.today().isoformat()
    tag_str = ", ".join(f'"{t}"' for t in tags)
    return (
        "---\n"
        f'title: "{topic["title"]}"\n'
        f'description: "{description}"\n'
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
    parser.add_argument("--dry-run", action="store_true", help="Print output without saving")
    args = parser.parse_args()

    topics = load_topics()
    used   = existing_slugs()
    topic  = pick_topic(topics, used)

    if topic is None:
        print("[INFO] All 60 topics have been published. No post generated.")
        sys.exit(0)

    print(f"[INFO] Generating: {topic['title']}")
    result = call_api(topic["title"])

    description = result.get("description", "")
    tags        = result.get("tags", topic.get("tags", []))
    content     = result.get("content", "")

    frontmatter = build_frontmatter(topic, description, tags)
    full_post   = frontmatter + content.strip() + "\n"

    if args.dry_run:
        print("\n" + "=" * 60)
        print(full_post)
        print("=" * 60)
        print(f"\n[DRY-RUN] Would save to: {BLOG_DIR / topic['slug']}.md")
        return

    path = save_post(topic["slug"], frontmatter, content)
    print(f"[OK] Saved: {path}")


if __name__ == "__main__":
    main()
