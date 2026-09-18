# ScreenLingo 0.2 — third-party software

ScreenLingo is a personal, unsigned prototype. Its original application and launcher
source is provided alongside the executable. You may inspect and modify that source.
Third-party components remain under their own licenses. No affiliation with Google,
Gemini, Microsoft, Qt, Argos, or OpenAI is implied.

## Bundled components

- CPython 3.11.9 embeddable x64 — Python Software Foundation License.
  Official distribution: https://www.python.org/downloads/release/python-3119/
  License: `runtime/LICENSE.txt` (upstream filename may vary).
- PySide6 Essentials / Shiboken6 6.8.3 and Qt shared libraries — LGPLv3/GPLv3,
  with module-specific exceptions and licenses supplied by Qt. This app uses
  QtCore, QtGui and QtWidgets, not GPL-only add-ons.
  https://doc.qt.io/qtforpython-6/licenses.html
  Corresponding upstream sources: https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.8.3-src/
  Qt sources: https://download.qt.io/archive/qt/6.8/6.8.3/single/
  Libraries are dynamically loaded from `runtime/Lib/site-packages/PySide6` and
  `shiboken6`; compatible modified libraries may be substituted. No app restriction
  is imposed on reverse engineering for debugging LGPL library modifications.
  Original license notices remain in package `.dist-info` folders and Qt resources.
- CTranslate2 4.6.0 — MIT. https://github.com/OpenNMT/CTranslate2/tree/v4.6.0
- SentencePiece 0.2.1 — Apache-2.0. https://github.com/google/sentencepiece
- MSS 10.0.0 — MIT. https://github.com/BoboTiG/python-mss
- Pillow 11.3.0 — MIT-CMU and bundled-library notices. https://python-pillow.org/
- NumPy 2.2.6 — BSD-3-Clause and bundled-library notices. https://numpy.org/
- PyYAML 6.0.3 — MIT. https://pyyaml.org/
- PyWinRT 3.2.1 namespace packages — MIT. https://github.com/pywinrt/pywinrt
- setuptools 80.9.0 — MIT and vendored-library notices. https://github.com/pypa/setuptools
- typing_extensions — PSF-2.0. https://github.com/python/typing_extensions
- Microsoft VC runtime DLLs as distributed within official Python and PySide6
  redistributable wheels — Microsoft runtime redistribution terms.

Exact wheel filenames and SHA-256 values are in DEPENDENCIES.json. Upstream
wheel license files have not been removed. Python code and shared libraries are
provided in ordinary, replaceable files rather than encrypted or statically linked.

## Translation models

The preferred direct-to-Korean model is Meta/Facebook M2M100 418M,
CTranslate2 INT8 conversion distributed by Jonathan Craton (jncraton), MIT.
- Original: https://huggingface.co/facebook/m2m100_418M
- Conversion: https://huggingface.co/jncraton/m2m100_418M-ct2-int8
- Pinned revision: 7c1b2620a4e58dacecbd8bf89cfd6da7eb9eb7b0
- License text: `licenses/M2M100-MIT.txt`
- Data files and SHA-256 hashes: `models/m2m100/metadata.json`

Model data is loaded by CTranslate2 and SentencePiece. Repository Python code
is not loaded or executed. The model runs locally on the CPU.

Legacy fallback models:


The English→Korean Argos package v1.1 is bundled unchanged after extraction.
Its original metadata, README and data-source credits remain in `models/en_ko`.
https://argos-net.com/v1/translate-en_ko-1_1.argosmodel
https://github.com/argosopentech/argospm-index

Japanese→English v1.1 and Chinese→English v1.9 are downloaded only after the
user agrees; their original metadata and notices are retained. When the direct model is absent, English is the
intermediate language for those legacy source-language models. The models use OPUS,
Wiktionary/Wiktextract and other corpora credited in each model's README.
Model/data rights are distinct from the Argos Translate software license.
Review the model source notices before republishing or using commercially.

Windows OCR is an operating-system feature and is not redistributed in this ZIP.
Its language packs must be installed through Windows.

## Build tooling

The launcher was cross-compiled with Zig 0.13.0 targeting x86_64-windows-gnu.
Build command: `zig cc -target x86_64-windows-gnu -O2 -municode -Wl,--subsystem,windows launcher.c -o ScreenLingo.exe -luser32`.
The Zig compiler is not included. Application source and the portable packaging
script are included for reproducibility; upstream downloads are listed in the
dependency manifest. UI screenshots/tests on Linux are not evidence of Windows
screen-capture compatibility.
