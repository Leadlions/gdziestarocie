"""
Scraper for targowiskastaroci.pl (or any similar Polish antique-fair aggregator).

HOW TO ADAPT:
1. Open the site in your browser and inspect the fair listing page.
2. Identify the CSS selectors for each fair row/card.
3. Update LISTING_URL and the selectors in _parse_item().
4. Run: python main.py --source targowiskastaroci --dry-run
"""

import logging
from bs4 import BeautifulSoup
from .base import BaseScraper

logger = logging.getLogger(__name__)


class TargowiskaStarosciScraper(BaseScraper):
    # ── Configuration — adjust these to match the real site ───────────────
    LISTING_URL = 'https://targowiskastaroci.pl/terminarz/'

    # CSS selectors — inspect the site and update accordingly
    SEL_ITEM   = 'article, .targ-item, .terminarz-row, tr[data-targ]'
    SEL_NAME   = 'h2, h3, .targ-nazwa, .nazwa, .title'
    SEL_CITY   = '.miasto, .city, [data-city], td:nth-child(2)'
    SEL_VENUE  = '.miejsce, .venue, .lokalizacja, td:nth-child(3)'
    SEL_DATE   = 'time, .data, .date, td:nth-child(1)'
    SEL_LINK   = 'a[href]'
    # ─────────────────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return 'targowiskastaroci.pl'

    def scrape(self) -> list[dict]:
        resp = self.get(self.LISTING_URL)
        if resp is None:
            logger.error('%s: could not fetch %s', self.name, self.LISTING_URL)
            return []

        soup = BeautifulSoup(resp.text, 'lxml')
        items = soup.select(self.SEL_ITEM)
        logger.info('%s: found %d candidate elements', self.name, len(items))

        results = []
        for item in items:
            fair = self._parse_item(item)
            if fair:
                results.append(fair)

        logger.info('%s: parsed %d valid fairs', self.name, len(results))
        return results

    def _parse_item(self, item) -> dict | None:
        try:
            name_el  = item.select_one(self.SEL_NAME)
            city_el  = item.select_one(self.SEL_CITY)
            venue_el = item.select_one(self.SEL_VENUE)
            date_el  = item.select_one(self.SEL_DATE)
            link_el  = item.select_one(self.SEL_LINK)

            if not name_el or not city_el:
                return None

            name  = name_el.get_text(strip=True)
            city  = city_el.get_text(strip=True)
            venue = venue_el.get_text(strip=True) if venue_el else city
            date_raw = (
                date_el.get('datetime') or date_el.get_text(strip=True)
                if date_el else ''
            )
            url = link_el['href'] if link_el else None
            if url and not url.startswith('http'):
                url = f'https://targowiskastaroci.pl{url}'

            parsed_date = self.parse_date(date_raw)
            if not parsed_date:
                logger.debug('%s: skipping "%s" — unparseable date "%s"', self.name, name, date_raw)
                return None

            fair = self.empty_fair(name, city)
            fair.update({
                'venue':    venue,
                'nextDate': parsed_date,
                'url':      url,
            })
            return fair

        except Exception as exc:
            logger.warning('%s: error parsing item: %s', self.name, exc)
            return None
