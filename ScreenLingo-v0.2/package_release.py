"""Package a portable release, excluding local backups, captures and caches."""
import argparse
import hashlib
from pathlib import Path
import time
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    target = args.output or root.parent / 'ScreenLingo-Windows-x64-v0.2.zip'
    folders = ('app', 'runtime', 'models', 'licenses', 'tests')
    root_files = ('ScreenLingo.exe', 'launcher.c', 'build_portable.py',
                  'package_release.py', 'README.html', 'TEST_REPORT.md',
                  'UPDATE_NOTES_0.2.md', 'THIRD_PARTY_NOTICES.md', 'DEPENDENCIES.json')
    required = ('ScreenLingo.exe', 'app/boot.py', 'runtime/pythonw.exe',
                'runtime/python311._pth', 'models/en_ko/model/model.bin',
                'models/m2m100/model/model.bin', 'models/m2m100/model/config.json',
                'models/m2m100/model/shared_vocabulary.json',
                'models/m2m100/sentencepiece.model', 'models/m2m100/metadata.json',
                'licenses/M2M100-MIT.txt', 'README.html', 'UPDATE_NOTES_0.2.md')
    for name in required:
        if not (root / name).is_file():
            raise FileNotFoundError(root / name)
    files = [root / name for name in root_files if (root / name).is_file()]
    for folder in folders:
        files.extend(file for file in (root / folder).rglob('*')
                     if file.is_file() and '__pycache__' not in file.parts
                     and file.suffix.lower() not in ('.pyc', '.pdb'))
    print('Packaging', len(files), 'files into', target, flush=True)
    last_update = time.monotonic()
    # Exclusive creation protects any existing release at the chosen path.
    with zipfile.ZipFile(target, 'x', zipfile.ZIP_DEFLATED, compresslevel=3) as archive:
        for index, file in enumerate(sorted(files), 1):
            archive.write(file, Path('ScreenLingo') / file.relative_to(root))
            if time.monotonic() - last_update > 10:
                print('Packaged', index, '/', len(files), flush=True)
                last_update = time.monotonic()
    print('Verifying ZIP CRC and required files...', flush=True)
    with zipfile.ZipFile(target) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError('ZIP CRC failure: ' + bad)
        names = set(archive.namelist())
        for name in required:
            if 'ScreenLingo/' + name not in names:
                raise RuntimeError('Missing release file: ' + name)
    digest = hashlib.sha256()
    with target.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    print('PASS:', target, flush=True)
    print('Bytes:', target.stat().st_size, flush=True)
    print('SHA256:', digest.hexdigest(), flush=True)


if __name__ == '__main__':
    main()
