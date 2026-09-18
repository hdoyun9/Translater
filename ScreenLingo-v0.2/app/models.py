"""Explicit model downloads only. Never receives screen images or OCR text."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get('LOCALAPPDATA', str(ROOT))) / 'ScreenLingo'
PAIRS = {
    'en_ko': 'https://argos-net.com/v1/translate-en_ko-1_1.argosmodel',
    'ja_en': 'https://argos-net.com/v1/translate-ja_en-1_1.argosmodel',
    'zh_en': 'https://argos-net.com/v1/translate-zh_en-1_9.argosmodel',
}


def emit(data):
    print(json.dumps(data, ensure_ascii=True), flush=True)


def required(source):
    return ['en_ko'] + (['ja_en', 'zh_en'] if source == 'auto' else
                        [source + '_en'] if source in ('ja', 'zh') else [])


def find_model(pair):
    for folder in (ROOT/'models'/pair, DATA/'models'/pair):
        if (folder/'model'/'model.bin').is_file() and (folder/'sentencepiece.model').is_file():
            return folder
    return None


def translation_ready(source):
    return find_model('m2m100') is not None or all(find_model(pair) for pair in required(source))


def safe_extract(archive, destination):
    destination = Path(destination).resolve()
    with zipfile.ZipFile(archive) as z:
        if sum(i.file_size for i in z.infolist()) > 3_000_000_000:
            raise ValueError('Model archive is too large')
        for info in z.infolist():
            path = (destination / info.filename.replace('\\', '/')).resolve()
            if not path.is_relative_to(destination) or ':' in info.filename:
                raise ValueError('Unsafe archive path')
            if ((info.external_attr >> 16) & 0o170000) == 0o120000:
                raise ValueError('Symlinks are not accepted')
        z.extractall(destination)


def install(pair, archive, base=None):
    base = Path(base) if base else DATA/'models'
    base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='unpack-', dir=base) as temp:
        safe_extract(archive, temp)
        candidates = [x.parent for x in Path(temp).rglob('sentencepiece.model')
                      if (x.parent/'model'/'model.bin').exists()]
        if len(candidates) != 1:
            raise ValueError('Unsupported model format')
        destination = base/pair
        if destination.exists():
            # Preserve an incomplete prior model for diagnosis; never overwrite it.
            backup = base/(pair + '.previous-' + str(os.getpid()))
            destination.rename(backup)
        shutil.move(str(candidates[0]), str(destination))


def download(pair):
    if pair not in PAIRS:
        raise ValueError('Unknown model')
    DATA.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='download-', dir=DATA) as tmp:
        target = Path(tmp)/'model.zip'
        request = urllib.request.Request(PAIRS[pair], headers={'User-Agent':'ScreenLingo/0.1'})
        with urllib.request.urlopen(request, timeout=45) as response, target.open('wb') as f:
            if not response.url.startswith('https://'):
                raise ValueError('HTTPS is required')
            total = int(response.headers.get('Content-Length') or 0)
            size = 0
            while True:
                chunk = response.read(1024*1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > 1_000_000_000:
                    raise ValueError('Download is too large')
                f.write(chunk)
                emit({'type':'progress','pair':pair,'bytes':size,'total':total})
        install(pair, target)


if __name__ == '__main__':
    try:
        for pair in required(sys.argv[1]):
            if not find_model(pair):
                download(pair)
        emit({'type':'installed'})
    except Exception as exc:
        emit({'type':'error','message':'모델 다운로드 실패: ' + type(exc).__name__})
        sys.exit(1)
