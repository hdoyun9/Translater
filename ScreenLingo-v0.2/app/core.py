"""Pure, testable helpers. No capture, network or third-party imports."""
from collections import OrderedDict
import re
import unicodedata


def source_for(text, preferred="en"):
    kana = len(re.findall(r"[\u3040-\u30ff]", text))
    han = len(re.findall(r"[\u3400-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    hangul = len(re.findall(r"[\uac00-\ud7a3]", text))
    if hangul > kana + han + latin:
        return None
    if kana:
        return "ja"
    if han:
        return "ja" if preferred == "ja" else "zh"
    return "en" if latin >= 2 else None


def normalize(text):
    # Half-width kana and combining dakuten must share the same glossary keys.
    text=unicodedata.normalize('NFC',re.sub(r'[\uff61-\uff9f]+',
        lambda match:unicodedata.normalize('NFKC',match[0]),text))
    text = " ".join(text.split())
    # Windows OCR can read the katakana long-vowel stroke as a spaced hyphen
    # (コ - ヒ - を). Restrict this repair to Japanese letter contexts.
    text=re.sub(r'(?<=[ァ-ヺ])\s*[-‐‑‒–—―一]\s*(?=[ぁ-ゖァ-ヺ。、！？!?]|$)','ー',text)
    # Windows OCR inserts a space between almost every Japanese/Chinese glyph.
    cjk = r'\u3000-\u30ff\u3400-\u9fff\uff01-\uff60'
    return re.sub(r'(?<=['+cjk+r'])\s+(?=['+cjk+r'])', '', text)


def intersection_over_union(a, b):
    x = max(a[0], b[0]); y = max(a[1], b[1])
    right = min(a[0] + a[2], b[0] + b[2])
    bottom = min(a[1] + a[3], b[1] + b[3])
    area = max(0, right-x) * max(0, bottom-y)
    union = a[2]*a[3] + b[2]*b[3] - area
    return area / union if union else 0


def deduplicate(lines):
    result = []
    # CJK detections take priority over misread Latin characters in the same box.
    ordered = sorted(lines, key=lambda x: x['source'] != 'en')
    for line in reversed(ordered):
        if not any(intersection_over_union(line['box'], x['box']) > .40 for x in result):
            result.append(line)
    return sorted(result, key=lambda x: (x['box'][1], x['box'][0]))


class MemoryCache:
    def __init__(self, capacity=500):
        self.capacity = capacity
        self.items = OrderedDict()

    def get(self, key):
        if key not in self.items:
            return None
        self.items.move_to_end(key)
        return self.items[key]

    def put(self, key, value):
        self.items[key] = value
        self.items.move_to_end(key)
        while len(self.items) > self.capacity:
            self.items.popitem(last=False)

    def clear(self):
        self.items.clear()


def physical_region(monitor, region):
    if not region:
        return dict(monitor)
    x, y, w, h = region
    x, y = max(0, min(x, .99)), max(0, min(y, .99))
    w, h = min(max(.01, w), 1-x), min(max(.01, h), 1-y)
    return dict(left=monitor['left'] + int(x*monitor['width']),
                top=monitor['top'] + int(y*monitor['height']),
                width=max(1, int(w*monitor['width'])),
                height=max(1, int(h*monitor['height'])))
