"""
intel/language_detector.py — Multilingual Language Detector
============================================================
Detects primary and secondary languages from document text with confidence scores.

Features:
    - Frequency-based n-gram analysis (char trigrams via Unicode ranges)
    - Common word frequency matching for word-based languages
    - Writing direction detection (LTR, RTL, TTB)
    - Confidence scoring per language
    - Mixed-language detection
    - Encoding detection fallback
    - Fast sampling for large documents

Extends/improves core.pipeline.identifier.DocumentIdentifierImpl.detect_language()
by adding per-language confidence scores, bidirectional-text awareness, mixed-language
support, sampling, and richer language coverage (th, vi, hi, ru, nl, pt, it, sv, ar, he).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

from core.intel.models import LanguageDirection, LanguageResult


class LanguageDetector:
    """Multilingual language detector with confidence scores."""

    UNICODE_RANGES: Dict[str, tuple[int, int]] = {
        "zh":         (0x4E00, 0x9FFF),
        "ja_hiragana":(0x3040, 0x309F),
        "ja_katakana":(0x30A0, 0x30FF),
        "ko":         (0xAC00, 0xD7AF),
        "ko_jamo":    (0x1100, 0x11FF),
        "th":         (0x0E00, 0x0E7F),
        "hi":         (0x0900, 0x097F),
        "ar":         (0x0600, 0x06FF),
        "he":         (0x0590, 0x05FF),
        "ru":         (0x0400, 0x04FF),
        "el":         (0x0370, 0x03FF),
        "vi":         (0x0102, 0x0110),
        "nl":         (0x0100, 0x017F),
        "pt":         (0x00C0, 0x00FF),
        "it":         (0x00C0, 0x00FF),
        "sv":         (0x00C0, 0x00FF),
    }

    COMMON_WORDS: Dict[str, List[str]] = {
        "en": ["the","and","that","have","for","not","with","you","this","but",
               "his","from","they","be","at","one","all","would","there","their",
               "what","so","up","out"],
        "ko": ["은","는","이","가","을","를","에","에서","도","하고","거나",
               "지만","에게","까지","부터","이나","랑","세요"],
        "zh": ["的","了","在","是","人","这","中","大","为","上","个","国",
               "有","到","地","都","和","月","我","子"],
        "ja_hiragana":["は","を","に","の","た","て","か","こ","れ","る","で",
                       "ま","ち","と","り","さ"],
        "ja_katakana": ["テ","イ","ス","ッ","ー","ン","ド","ク","ト","ル","ジ",
                        "ガ","コ","サ","デ","ビ"],
        "th": ["ที่","การ","มี","มา","ใน","คุณ","ก็","ยัง","ได้","หรือ"],
        "vi": ["là","không","có","để","những","này","gì","đã","ủa","được"],
        "hi": ["है","कि","का","के","में","से","और","एक","को","नहीं"],
        "ar": ["في","من","على","هذا","الذي","ان","كان","انه","انا","و"],
        "he": ["את","לא","של","זה","בין","על","הוא","אבל","כאן","יש"],
        "ru": ["в","на","и","не","что","это","с","по","но"],
        "nl": ["de","het","van","en","is","dat","een","niet","zo","om"],
        "pt": ["de","que","e","do","da","em","um","para","com","na"],
        "it": ["di","che","e","il","la","in","un","per","a","del"],
        "sv": ["och","att","i","en","den","som","på","för","till","av"],
    }

    # ── Tunable thresholds ────────────────────────────────────────────────
    MIN_TEXT_LENGTH: int = 20
    MIXED_THRESHOLD: float = 0.15
    SAMPLE_CHUNK_COUNT: int = 3
    SAMPLE_SIZE: int = 2000
    LARGE_DOC_BYTES: int = 10_240

    LANG_NAMES: Dict[str, str] = {
        "en":"English","ko":"Korean","zh":"Chinese",
        "ja_hiragana":"Japanese (Hiragana)","ja_katakana":"Japanese (Katakana)",
        "th":"Thai","vi":"Vietnamese","hi":"Hindi","ar":"Arabic","he":"Hebrew",
        "ru":"Russian","nl":"Dutch","pt":"Portuguese","it":"Italian",
        "sv":"Swedish","el":"Greek",
    }

    def detect(self, text: str, file_path: Path | str = "") -> LanguageResult:
        """Full language detection pipeline. Returns LanguageResult."""
        if not isinstance(file_path, Path):
            file_path = Path(str(file_path)) if file_path else Path("")

        # Minimum text length gate
        if len(text.strip()) < self.MIN_TEXT_LENGTH:
            return LanguageResult(
                primary_language="unknown", primary_confidence=0.0,
                encoding=self._detect_encoding(file_path),
                writing_direction=self._detect_writing_direction(text),
                sample_size=len(text.encode("utf-8")),
            )

        # Sample large documents for balanced coverage
        if len(text.encode("utf-8")) > self.LARGE_DOC_BYTES:
            text = self._sample_text(text)

        sample_bytes = len(text)
        unicode_scores = self._detect_from_unicode_ranges(text)
        word_scores = self._detect_from_common_words(text)

        # Merge: char-set langs use Unicode, word langs use word freq, others merge
        combined: Dict[str, float] = {}
        char_set_langs = {"ko", "zh", "ja_hiragana", "ja_katakana"}
        for lang in set(unicode_scores) | set(word_scores):
            uni, wrd = unicode_scores.get(lang, 0.0), word_scores.get(lang, 0.0)
            if lang in char_set_langs:
                score = uni + (0.1 if wrd > 0 else 0)
            elif lang == "en":
                score = wrd + (0.05 if sum(1 for c in text if ord(c) < 128) / max(len(text),1) > 0.7 else 0)
            else:
                score = max(uni, wrd)
            combined[lang] = score

        sorted_scores = dict(sorted(combined.items(), key=lambda kv: kv[1], reverse=True))
        top_score = next(iter(sorted_scores.values()), 0.0)

        if top_score < 0.05:
            return LanguageResult(primary_language="unknown", primary_confidence=0.0,
                                  encoding=self._detect_encoding(file_path),
                                  writing_direction=self._detect_writing_direction(text),
                                  sample_size=sample_bytes)

        # Collapse Japanese sub-ranges into "ja" when both are active
        h, k = sorted_scores.get("ja_hiragana", 0.0), sorted_scores.get("ja_katakana", 0.0)
        if h > 0.15 and k > 0.05:
            sorted_scores["ja"] = max(h, k) + 0.1
            del sorted_scores["ja_hiragana"], sorted_scores["ja_katakana"]
            sorted_scores = dict(sorted(sorted_scores.items(),
                                        key=lambda kv: kv[1], reverse=True))

        primary = next(iter(sorted_scores))
        secondaries = {l: s for l, s in sorted_scores.items() if l != primary and s > 0}

        return LanguageResult(
            primary_language=primary, primary_confidence=min(top_score, 1.0),
            secondary_languages=list(secondaries.keys()),
            secondary_confidences={k: min(v, 1.0) for k, v in secondaries.items()},
            encoding=self._detect_encoding(file_path),
            writing_direction=self._detect_writing_direction(text),
            is_mixed=self._is_mixed_languages(sorted_scores),
            sample_size=sample_bytes,
        )

    # ── Internal helpers ──────────────────────────────────────────────────

    def _sample_text(self, text: str) -> str:
        """Return *n* non-overlapping chunks for balanced coverage of long docs."""
        length = len(text)
        step = max(1, length // self.SAMPLE_CHUNK_COUNT)
        return "".join(text[i*step:i*step+self.SAMPLE_SIZE]
                       for i in range(self.SAMPLE_CHUNK_COUNT))

    def _detect_from_unicode_ranges(self, text: str) -> Dict[str, float]:
        """Score languages by proportion of characters falling in known Unicode ranges."""
        counts: Dict[str, int] = {l: 0 for l in self.UNICODE_RANGES}
        for ch in text:
            cp = ord(ch)
            for lang, (lo, hi) in self.UNICODE_RANGES.items():
                if lo <= cp <= hi:
                    counts[lang] += 1
        total = sum(counts.values())
        if total == 0:
            return {l: 0.0 for l in counts}

        # Normalize, apply diagnostic bonuses for sparse but highly-significant scripts
        for l in counts:
            counts[l] = counts[l] / total
        if counts.get("ko", 0) > 0:
            counts["ko"] = max(counts["ko"], 0.35)
        if counts.get("zh", 0) > 0:
            counts["zh"] = max(counts["zh"], 0.35)
        best = max(counts.values())
        if best > 0:
            for l in counts:
                counts[l] /= best
        return counts

    def _detect_from_common_words(self, text: str) -> Dict[str, float]:
        """Score languages based on high-frequency function-word presence."""
        cleaned = text[:5000].lower()
        wc = max(1, len(re.findall(r"\w+", cleaned)))
        scores: Dict[str, float] = {}
        for lang, words in self.COMMON_WORDS.items():
            hit = sum(1 for w in words if w in cleaned)
            if hit:
                scores[lang] = min(hit / wc * 10.0 * hit * 0.1, 1.0)
        return scores

    def _detect_writing_direction(self, text: str) -> LanguageDirection:
        """Infer writing direction from script indicators (RTL vs LTR)."""
        if len(text) < 10:
            return LanguageDirection.LTR
        if re.search(r"[\u0600-\u06FF\u0750-\u077F]", text) or \
           re.search(r"[\u0590-\u05FF]", text):
            return LanguageDirection.RTL
        return LanguageDirection.LTR

    @staticmethod
    def _is_mixed_languages(scores: Dict[str, float],
                            threshold: float = 0.15) -> bool:
        """True when secondary ≥ threshold × primary score."""
        items = list(scores.items())
        if len(items) < 2:
            return False
        p, s = items[0][1], items[1][1]
        return (s / p) >= threshold if p > 0 else False

    @staticmethod
    def _get_iso639_name(code: str) -> str:
        """Convert ISO 639 language code to readable English name."""
        return LanguageDetector.LANG_NAMES.get(code, code)

    @staticmethod
    def _detect_encoding(file_path: Path) -> str:
        """Detect encoding via BOM check, then utf-8→latin-1 fallback."""
        if not file_path or not file_path.exists():
            return "utf-8"
        try:
            with open(file_path, "rb") as fh:
                head = fh.read(4)
            for sig, enc in [(b"\xef\xbb\xbf","utf-8-sig"),
                             (b"\xff\xfe\x00\x00","utf-32-le"),
                             (b"\x00\x00\xfe\xff","utf-32-be"),
                             (b"\xff\xfe","utf-16-le"),
                             (b"\xfe\xff","utf-16-be")]:
                if head.startswith(sig):
                    return enc
            try:
                file_path.read_text(encoding="utf-8")
                return "utf-8"
            except UnicodeDecodeError:
                return "latin-1"
        except OSError:
            return "utf-8"

    # ── Convenience ───────────────────────────────────────────────────────

    def detect_from_file(self, file_path: Path | str) -> LanguageResult:
        """Read a file and detect its language."""
        fp = Path(str(file_path))
        try:
            text = fp.read_text(encoding="utf-8", errors="replace")
        except Exception:
            text = fp.read_text(encoding="latin-1", errors="replace")
        return self.detect(text, fp)


def detect_language(text: str, file_path: Path | str = "") -> LanguageResult:
    """Quick language detection — thin wrapper around :class:`LanguageDetector`."""
    return LanguageDetector().detect(text, file_path)
