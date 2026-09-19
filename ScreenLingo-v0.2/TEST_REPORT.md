# ScreenLingo 0.2 Windows verification

Date: 2026-09-19. Runtime: bundled CPython 3.11.9 / CTranslate2 4.6.0 / PyWinRT 3.2.1.

## Automated tests

50 unittest tests passed. These cover the existing worker lifecycle and privacy checks,
CJK spacing, vertical reading order, separated bubbles, furigana attachment and masks,
75 independent OCR lines, lossless long-input splitting, full-resolution tiling,
opaque source coverage at a screen edge, 75 overlay entries, complete scrollable results,
partial-update backpressure, startup errors and real-model semantic regressions.

The direct model tests check that Japanese place/time information and negation survive,
and that English negation and a Chinese key-finding instruction are translated.
Additional checks cover frame dragging/resizing, normalized inner bounds, capture exclusion
geometry, transparent center, overlay clipping, obsolete-result rejection, saved frame/terms,
dictionary validation, half-width kana/dakuten/long-vowel repairs, marker-loss fallback,
katakana consistency and immediate glossary cache invalidation.

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
- Cropped Japanese names/loanwords: an outside sentence is excluded; `カタリナ` and
  `コーヒー` are recognized and translated with live dictionary changes across three frames.
  This fixture reproduced OCR `コ - ヒ -`; contextual long-vowel repair restored `커피`.

Synthetic text and generated preview artifacts are the only image/text data saved by QA scripts.
Application screen captures and translations remain in memory only.

## Visual verification

Qt panel and horizontal/vertical Japanese replacement overlays rendered and inspected.
Source glyphs are covered by fully opaque fills. System CJK fonts are explicitly registered.
The results viewer preserves complete text and works after pausing.
Windows native `WindowFromPoint` checks on app-owned test windows confirm the frame center
passes through to the underlying window and its header receives input. `SetWindowDisplayAffinity`
succeeds for the capture frame. No user desktop image was captured by these tests.
The input hole uses Qt's documented QWidget region mask behavior:
https://doc.qt.io/qt-6.8/qwidget.html#setMask-1

## Limits of this evidence

The actual problematic Pixiv image was not supplied. Synthetic printed-text tests do not
establish perfect recognition of handwriting, artistic lettering, furigana at every size,
or unusual manga layouts. Machine translation can still misread nuance and proper names.
The app translates the visible interior of its frame on the primary display, not content
below the browser viewport. Multi-monitor, protected capture and exclusive-fullscreen
compatibility were not expanded in this update.
Katakana normalization and consistent standalone inference do not establish official Korean
localizations for every fictional character or brand. User glossary entries override model
spellings. A damaged model marker triggers a lossless segmented fallback, which may reduce
sentence fluency. Handwritten or unrelated OCR substitutions still require source review.

M2M100 data is pinned to jncraton/m2m100_418M-ct2-int8 revision
7c1b2620a4e58dacecbd8bf89cfd6da7eb9eb7b0; hashes and the MIT notice are bundled.
