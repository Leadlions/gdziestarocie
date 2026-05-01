#!/usr/bin/env python3
"""
Scraper orchestrator for gdziestarocie.pl.

Usage:
    python main.py                          # scrape all sources, save fairs.json
    python main.py --dry-run                # print merged JSON, do not save
    python main.py --source targowiskastaroci  # run only one source

Merge rules (safe for editorial data):
    - reviews and mentions are NEVER overwritten by scraped data
    - nextDate and url are updated when scraper finds a match by slug
    - new slugs from scraper are appended with empty reviews/mentions
    - entries that no longer appear in any source are kept (never deleted)
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Path to the Astro data file
FAIRS_JSON = Path(__file__).resolve().parents[2] / 'src' / 'data' / 'fairs.json'

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')
logger = logging.getLogger('main')


# ── Registry — add new scrapers here ──────────────────────────────────────────

def get_scrapers(source_filter: str | None = None):
    from scrapers.targowiskastaroci import TargowiskaStarosciScraper

    all_scrapers = [
        TargowiskaStarosciScraper(),
        # AntykirScraper(),        # add when built
        # EventbritePolishScraper(),
    ]

    if source_filter:
        matched = [s for s in all_scrapers if source_filter in s.name]
        if not matched:
            logger.error('No scraper name contains "%s". Available: %s',
                         source_filter, [s.name for s in all_scrapers])
            sys.exit(1)
        return matched
    return all_scrapers


# ── Merge logic ────────────────────────────────────────────────────────────────

def load_existing(path: Path) -> list[dict]:
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    logger.warning('fairs.json not found at %s — starting fresh', path)
    return []


def merge(existing: list[dict], scraped: list[dict]) -> list[dict]:
    by_slug = {f['slug']: f for f in existing}

    for fair in scraped:
        slug = fair['slug']
        if slug in by_slug:
            existing_fair = by_slug[slug]
            # Update only safe, non-editorial fields
            existing_fair['nextDate'] = fair['nextDate']
            if fair.get('url') and not existing_fair.get('url'):
                existing_fair['url'] = fair['url']
            if fair.get('venue') and not existing_fair.get('venue'):
                existing_fair['venue'] = fair['venue']
            # Mark source for debugging
            existing_fair['_source'] = fair.get('_source', 'scraper')
        else:
            # Brand-new fair — always has empty reviews/mentions
            fair.setdefault('reviews', [])
            fair.setdefault('mentions', [])
            by_slug[slug] = fair
            logger.info('New fair added: "%s" (%s)', fair['name'], fair['city'])

    # Sort by nextDate, nulls last
    return sorted(
        by_slug.values(),
        key=lambda f: f.get('nextDate') or '9999-99-99',
    )


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description='Scrape antique fair data for gdziestarocie.pl')
    parser.add_argument('--dry-run', action='store_true', help='Print result, do not write file')
    parser.add_argument('--source', metavar='NAME', help='Run only the named scraper')
    args = parser.parse_args()

    scrapers = get_scrapers(args.source)
    scraped: list[dict] = []

    for scraper in scrapers:
        logger.info('Running: %s', scraper.name)
        try:
            results = scraper.scrape()
            scraped.extend(results)
        except Exception as exc:
            logger.error('Scraper "%s" crashed: %s', scraper.name, exc)

    logger.info('Scraped %d fairs total', len(scraped))

    existing = load_existing(FAIRS_JSON)
    merged = merge(existing, scraped)

    output = json.dumps(merged, ensure_ascii=False, indent=2)

    if args.dry_run:
        print(output)
        logger.info('Dry run — file not saved')
        return

    FAIRS_JSON.write_text(output, encoding='utf-8')
    logger.info('Saved %d fairs → %s', len(merged), FAIRS_JSON)


if __name__ == '__main__':
    main()
