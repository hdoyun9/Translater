# ScreenLingo 0.2 Windows verification

Date: 2026-09-13. Runtime: bundled CPython 3.11.9 / CTranslate2 4.6.0 / PyWinRT 3.2.1.

## Automated tests

34 unittest tests passed. These cover the existing worker lifecycle and privacy checks,
CJK spacing, vertical reading order, separated bubbles, furigana attachment and masks,
75 independent OCR lines, lossless long-input splitting, full-resolution tiling,
opaque source coverage at a screen edge, 75 overlay entries, complete scrollable results,
partial-update backpressure, startup errors and real-model semantic regressions.

The direct model tests check that Japanese place/time information and negation survive,
and that English negation and a Chinese key-finding instruction are translated.

## Real OCR + translation integration

The capture source is replaced by synthetic in-memory text images. WinRT OCR,
SentencePiece and CTranslate2 are real. The worker's network-denying audit hook is active.

- Wrapped English sentence: joined before translation, complete Korean result.
- Horizontal Japanese: both lines retained and translated as one statement.
- Vertical Japanese: both columns retained in right-to-left column order.
- Japanese with small furigana: pronunciation attached to its kanji, masked and not mistranslated independently.
- Chinese: complete Korean output.
- Automatic mode: English, Japanese and Chinese fixtures each choose the appropriate script without duplicate paragraphs.
- 96-line page with more than 1,200 source characters: final marker sentence retained and translated.
- Repeated-capture smoke test: three frames returned and normal process exit.

Synthetic text and generated preview artifacts are the only image/text data saved by QA scripts.
Application screen captures and translations remain in memory only.

## Visual verification

Qt panel and horizontal/vertical Japanese replacement overlays rendered and inspected.
Source glyphs are covered by fully opaque fills. System CJK fonts are explicitly registered.
The results viewer preserves complete text and works after pausing.

## Limits of this evidence

The actual problematic Pixiv image was not supplied. Synthetic printed-text tests do not
establish perfect recognition of handwriting, artistic lettering, furigana at every size,
or unusual manga layouts. Machine translation can still misread nuance and proper names.
The app translates the currently visible primary display / selected region, not content
below the browser viewport. Multi-monitor, protected capture and exclusive-fullscreen
compatibility were not expanded in this update.

M2M100 data is pinned to jncraton/m2m100_418M-ct2-int8 revision
7c1b2620a4e58dacecbd8bf89cfd6da7eb9eb7b0; hashes and the MIT notice are bundled.
