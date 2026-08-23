"""
metadata/normalize.py — Metadata Normalization Framework
==========================================================
Normalizes extracted metadata to canonical, searchable, comparable forms.
All functions are PURE — no file I/O, no network calls, no mutable globals.
"""

from __future__ import annotations
import re
from typing import Any, Dict, Optional

# ── Month / quarter helpers ───────────────────────────────────────────────────

_MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

_SUFFIX_PATS = [
    re.compile(r'\b((?:Ph\.?D|M\.?D|LLM|Esq))\s*$', re.I),
    re.compile(r'\b(Jr\.?)\s*$', re.I), re.compile(r'\b(Sr\.?)\s*$', re.I),
    re.compile(r'\b((II|III|IV|V))\s*$', re.I),
]


class MetadataNormalizer:
    """Normalize all metadata fields to canonical forms."""
    COUNTRY_MAP = {
        "united states": "US", "usa": "US", "u.s.": "US", "uk": "GB",
        "great britain": "GB", "canada": "CA", "australia": "AU",
        "germany": "DE", "france": "FR", "japan": "JP", "china": "CN",
        "south korea": "KR", "korea": "KR", "india": "IN", "brazil": "BR",
        "mexico": "MX", "italy": "IT", "spain": "ES", "netherlands": "NL",
        "sweden": "SE", "norway": "NO", "denmark": "DK", "finland": "FI",
        "switzerland": "CH", "austria": "AT", "belgium": "BE", "portugal": "PT",
        "russia": "RU", "poland": "PL", "turkey": "TR", "egypt": "EG",
        "south africa": "ZA", "nigeria": "NG", "kenya": "KE", "ghana": "GH",
        "indonesia": "ID", "thailand": "TH", "vietnam": "VN", "malaysia": "MY",
        "singapore": "SG", "new zealand": "NZ", "ireland": "IE", "israel": "IL",
        "saudi arabia": "SA", "uae": "AE", "argentina": "AR", "chile": "CL",
        "colombia": "CO", "peru": "PE", "venezuela": "VE", "cuba": "CU",
        "philippines": "PH", "pakistan": "PK", "bangladesh": "BD",
    }

    def __init__(self):
        self._country_reverse: Dict[str, str] = {}
        for name, code in self.COUNTRY_MAP.items():
            self._country_reverse.setdefault(code, name)

    def _strip_suffix(self, raw: str) -> tuple[str, str]:
        """Remove academic/family suffixes, return (name_without_suffix, suffix)."""
        suffix = ""
        for pat in _SUFFIX_PATS:
            m = pat.search(raw)
            if m:
                suffix = m.group(1)
                raw = raw[:m.start()].rstrip(', \t')
                break
        return raw, suffix

    def normalize_author_name(self, raw_name: str) -> Dict[str, Any]:
        """Parse a raw author name into structured components."""
        first_name = middle_initial = last_name = suffix = ""
        # For "Last, First" format, extract surname and given-name portion first
        if ',' in raw_name:
            parts = [p.strip() for p in raw_name.split(',', 1)]
            last_name = parts[0]
            rest = parts[1].strip() if len(parts) > 1 else ""
            rest, suffix = self._strip_suffix(rest)
            tokens = rest.split()
            if tokens:
                first_name = tokens[0]
                if len(tokens) > 1:
                    middle_initial = ' '.join(tokens[1:])
        else:
            sname, suffix = self._strip_suffix(raw_name.strip())
            tokens = sname.split()
            prefix_words = {"de", "van", "von", "del", "la", "le", "di", "ter", "bin"}
            if tokens[-1].lower() not in prefix_words and len(tokens) > 1:
                last_name = tokens[-1]
                first_name = ' '.join(tokens[:-1])
            else:
                first_name = ' '.join(tokens)
        return {"name": raw_name.strip(), "first_name": first_name.strip(),
                "middle_initial": middle_initial.strip(), "last_name": last_name.strip(),
                "suffix": suffix.strip()}

    def normalize_institution(self, raw: str) -> str:
        """Normalize institution names (lowercase, strip punctuation)."""
        s = raw.strip().lower()
        s = re.sub(r'[^a-z0-9\s]', '', s)
        return re.sub(r'\s+', ' ', s).strip()

    def normalize_journal(self, raw: str) -> str:
        """Normalize journal names — lowercase, strip trailing punctuation."""
        s = re.sub(r'[\s.,;]+$', '', raw.strip()).lower()
        return re.sub(r'\s+', ' ', s).strip()

    def normalize_country(self, value: str) -> Optional[str]:
        """Convert country name or partial name → ISO 3166-1 alpha-2 code."""
        key = value.strip().lower()
        if key in self.COUNTRY_MAP:
            return self.COUNTRY_MAP[key]
        for name, code in self.COUNTRY_MAP.items():
            if name.startswith(key) or key.startswith(name):
                return code
        return None

    def normalize_date(self, raw: str) -> Optional[str]:
        """Convert various date formats to ISO 8601 (YYYY-MM-DD)."""
        s = raw.strip()
        # YYYY-MM-DD
        m = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$', s)
        if m:
            return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        # YYYY-Qn
        m = re.match(r'^(\d{4})Q(\d)$', s)
        if m:
            month = (int(m.group(2)) - 1) * 3 + 1
            return f"{int(m.group(1)):04d}-{month:02d}-01"
        # YYYY-MM
        m = re.match(r'^(\d{4})-(\d{1,2})$', s)
        if m:
            return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-01"
        # Year only
        if re.match(r'^\d{4}$', s):
            return f"{int(s):04d}-01-01"
        # Season + year
        sm = re.match(r'^(spring|summer|autumn|fall|winter)\s+(\d{4})$', s, re.I)
        if sm:
            smap = {"spring": 3, "summer": 6, "autumn": 9, "fall": 9, "winter": 12}
            yr = int(sm.group(2))
            return f"{yr:04d}-{smap[sm.group(1).lower()]:02d}-01"
        # Day Mon Year
        m = re.match(r'^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$', s)
        if m:
            month = _MONTH_MAP.get(m.group(2).lower())
            if month:
                return f"{int(m.group(3)):04d}-{month:02d}-{int(m.group(1)):02d}"
        # Mon Day, Year
        m = re.match(r'^([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})$', s)
        if m:
            month = _MONTH_MAP.get(m.group(1).lower())
            if month:
                return f"{int(m.group(3)):04d}-{month:02d}-{int(m.group(2)):02d}"
        # Mon Year
        m = re.match(r'^([A-Za-z]+)\s+(\d{4})$', s)
        if m:
            month = _MONTH_MAP.get(m.group(1).lower())
            if month:
                return f"{int(m.group(2)):04d}-{month:02d}-01"
        return None

    def normalize_doi(self, doi: str) -> Optional[str]:
        """Normalize DOI: strip https prefix, lowercase, validate format."""
        s = re.sub(r'^(https?://)?(dx\.)?doi\.org/', '', doi.strip(), flags=re.I).lower()
        return s if re.match(r'^10\.\d{4,9}/[-._;()/:A-Z0-9]+$', s, re.I) else None

    def normalize_language(self, lang_code: str) -> str:
        """Normalize language code to lowercase ISO 639-1 form."""
        s = lang_code.strip().lower().split('-', 1)[0]
        return s[:2] if len(s) >= 2 else s

    def normalize_identifier(self, ident: str) -> Optional[str]:
        """Normalize ORCID, ISBN, ISSN — strip dashes/spaces, uppercase."""
        s = re.sub(r'[-\s]', '', ident.strip()).upper().lstrip('ORCID-')
        return s if re.match(r'^[A-Z0-9X\-]+$', s) else None

    ENC_ALIASES = {
        "utf-8": "UTF-8", "ascii": "ASCII", "iso-8859-1": "ISO-8859-1",
        "latin1": "ISO-8859-1", "cp1252": "CP1252", "windows-1252": "CP1252",
        "shift-jis": "Shift_JIS", "sjis": "Shift_JIS",
        "gb2312": "GB2312", "gbk": "GBK", "big5": "Big5", "euc-kr": "EUC-KR",
        "utf-16": "UTF-16", "utf32": "UTF-32",
    }

    def normalize_encoding(self, enc: str) -> str:
        """Normalize character encoding name to standard form."""
        key = enc.strip().lower().replace('_', '-')
        return self.ENC_ALIASES.get(key, enc.strip().upper())

    @staticmethod
    def infer_from_text(text_sample: str) -> Dict[str, str]:
        """Quick heuristic normalization from raw text. Returns detected values."""
        lower = text_sample.lower()
        detected: Dict[str, str] = {}
        # Language hint by stop words
        if 'the ' in lower and ' of ' in lower:
            detected['language_hint'] = 'en'
        elif ' der ' in lower and ' die ' in lower:
            detected['language_hint'] = 'de'
        elif ' de ' in lower and ' la ' in lower:
            detected['language_hint'] = 'fr'
        # Date hint (YYYY/MM/DD or similar)
        dm = re.search(r'(\d{4})[^0-9](\d{1,2})[^0-9](\d{1,2})', text_sample)
        if dm:
            detected['date_hint'] = f"{int(dm.group(1)):04d}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
        # DOI hint
        dom = re.search(r'(10\.\d{4,9}/[\w\-]+)', text_sample)
        if dom:
            detected['doi_hint'] = dom.group(1).lower()
        # URL hint
        urlm = re.search(r'(https?://[^\s<>"]+)', text_sample)
        if urlm:
            detected['url_hint'] = urlm.group(1)
        return detected


def normalize_metadata_field(
    field_name: str, raw_value: str, normalizer: Optional[MetadataNormalizer] = None,
) -> Optional[str]:
    """Convenience function: dispatch to the appropriate normalizer by field name."""
    fn = normalizer or MetadataNormalizer()
    map_ = {
        "author_name": lambda v: str(fn.normalize_author_name(v)),
        "institution": fn.normalize_institution, "journal": fn.normalize_journal,
        "country": fn.normalize_country, "date": fn.normalize_date,
        "doi": fn.normalize_doi, "language": fn.normalize_language,
        "identifier": fn.normalize_identifier, "encoding": fn.normalize_encoding,
    }
    dispatcher = map_.get(field_name)
    if dispatcher is None:
        return None
    result = dispatcher(raw_value)
    return str(result) if isinstance(result, (dict, list)) else result

_default_normalizer: Optional[MetadataNormalizer] = None

def get_normalizer() -> MetadataNormalizer:
    global _default_normalizer
    if _default_normalizer is None:
        _default_normalizer = MetadataNormalizer()
    return _default_normalizer
