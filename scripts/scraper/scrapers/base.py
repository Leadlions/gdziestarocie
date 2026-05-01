"""Base scraper: retry logic, rate limiting, shared slug/date utilities."""

import re
import time
import logging
from abc import ABC, abstractmethod
from typing import Optional

import requests

logger = logging.getLogger(__name__)

POLISH_MONTHS = {
    'stycznia': '01', 'lutego': '02', 'marca': '03',
    'kwietnia': '04', 'maja': '05', 'czerwca': '06',
    'lipca': '07', 'sierpnia': '08', 'września': '09',
    'października': '10', 'listopada': '11', 'grudnia': '12',
    # nominative forms (for sites that use them)
    'styczeń': '01', 'luty': '02', 'marzec': '03',
    'kwiecień': '04', 'maj': '05', 'czerwiec': '06',
    'lipiec': '07', 'sierpień': '08', 'wrzesień': '09',
    'październik': '10', 'listopad': '11', 'grudzień': '12',
}

PL_TO_ASCII = str.maketrans(
    'ąćęłńóśźżĄĆĘŁŃÓŚŹŻ',
    'acelnoszzACELNOSZZ',
)


class BaseScraper(ABC):
    REQUEST_DELAY = 2.0
    MAX_RETRIES = 3
    TIMEOUT = 30

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (compatible; gdziestarocie-bot/1.0; +https://gdziestarocie.pl/)',
        'Accept-Language': 'pl-PL,pl;q=0.9,en;q=0.5',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self._last_request: float = 0.0

    # ── HTTP ──────────────────────────────────────────────────────────────

    def get(self, url: str) -> Optional[requests.Response]:
        elapsed = time.time() - self._last_request
        if elapsed < self.REQUEST_DELAY:
            time.sleep(self.REQUEST_DELAY - elapsed)

        for attempt in range(self.MAX_RETRIES):
            try:
                resp = self.session.get(url, timeout=self.TIMEOUT)
                self._last_request = time.time()
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                logger.warning("Attempt %d/%d failed for %s: %s", attempt + 1, self.MAX_RETRIES, url, exc)
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
        return None

    # ── Abstract interface ────────────────────────────────────────────────

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable source name."""

    @abstractmethod
    def scrape(self) -> list[dict]:
        """Return list of fair dicts matching the fairs.json schema."""

    # ── Shared utilities ──────────────────────────────────────────────────

    def make_slug(self, name: str, city: str) -> str:
        text = f"{name}-{city}".lower().translate(PL_TO_ASCII)
        return re.sub(r'[^a-z0-9]+', '-', text).strip('-')

    def city_slug(self, city: str) -> str:
        return city.lower().translate(PL_TO_ASCII)

    def parse_date(self, raw: str) -> Optional[str]:
        """Parse a Polish date string to YYYY-MM-DD, or return None."""
        if not raw:
            return None
        text = raw.lower().strip()
        for pl, num in POLISH_MONTHS.items():
            text = text.replace(pl, num)
        # Keep only digits, separators
        text = re.sub(r'[^\d\-\./ ]', '', text).strip()
        text = re.sub(r'\s+', ' ', text)
        try:
            from dateutil import parser as dp
            return dp.parse(text, dayfirst=True).strftime('%Y-%m-%d')
        except Exception:
            return None

    def empty_fair(self, name: str, city: str) -> dict:
        """Return a fair dict skeleton with all required fields."""
        return {
            'slug': self.make_slug(name, city),
            'name': name,
            'city': city,
            'citySlug': self.city_slug(city),
            'voivodeship': '',
            'venue': city,
            'nextDate': None,
            'recurring': None,
            'recurringDesc': None,
            'categories': ['antyki'],
            'organizer': None,
            'url': None,
            'description': None,
            'reviews': [],
            'mentions': [],
            '_source': self.name,
        }
