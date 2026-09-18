# ScreenLingo 0.1 Windows 오류 수정

검증일: 2026-09-12

대상: `D:\기타앱\번역기\ScreenLingo-Windows-x64-v0.1\ScreenLingo`

## 확인한 원인

1. Windows OCR을 불러올 때 PyWinRT에 포함된 `msvcp140.dll` 14.29.30157이 먼저 로드되었습니다. 이후 SentencePiece 0.2.1 모델 로딩에서 Windows 접근 위반 `0xC0000005`가 재현됐습니다. 시스템의 MSVCP140 14.51.36247을 먼저 로드하면 같은 OCR/번역 테스트가 성공했습니다.
2. SentencePiece에 한글이 포함된 모델 경로를 직접 넘기면 `Illegal byte sequence Error #42`가 발생했습니다. Python의 `Path.read_bytes()`로 파일을 읽은 뒤 `model_proto`로 전달하면 번역이 성공했습니다.
3. UI는 작업 프로세스의 모든 비정상 종료에 OCR 언어/Visual C++ 설치 안내를 표시했습니다. 설치 문제를 실제 진단한 메시지가 아니었습니다.

## 변경

- `app/worker.py`: WinRT를 불러오기 전에 시스템의 `msvcp140.dll`을 `LOAD_LIBRARY_SEARCH_SYSTEM32`로 로드하고 핸들을 유지합니다. 이벤트 루프/런타임 초기화 실패도 UI용 오류 메시지로 전달합니다.
- `app/translate_local.py`: Unicode 경로는 Python에서 읽고 SentencePiece에는 모델 바이트를 전달합니다.
- `app/main.py`: 종료 직전 남은 작업 메시지를 읽고 구체적인 오류를 유지합니다. 원인을 알 수 없는 비정상 종료는 종료 코드로 표시합니다.

이 수정은 Windows에 설치된 Visual C++ x64 런타임을 사용합니다. 이 PC는 14.51.36247로 검증했습니다. 배포 시 최신 Microsoft Visual C++ x64 재배포 패키지가 필요합니다. Python, 모델, 외부 패키지 버전과 모델 다운로드 동작은 변경하지 않았습니다.

## 검증

- 기존 테스트와 회귀 테스트 총 20개 통과.
- 실제 Windows OCR + 포함된 영어→한국어 모델을 사용한 통합 테스트 통과. 화면 대신 메모리의 합성 이미지로 3회 연속 인식·번역했습니다.
- `Hello. Welcome to the game.` → `안녕하세요. 게임에 오신 것을 환영합니다.`
- 수정 전에는 같은 테스트에서 `ready`, `detected` 후 `0xC0000005`로 종료됐습니다. 수정 후에는 매번 `frame` 결과를 반환하고 정상 종료합니다.
- 실제 게임 화면의 오버레이 배치와 일본어/중국어 모델은 이 테스트 범위에 포함하지 않았습니다.

## 사용

앱을 완전히 종료한 후 기존 `ScreenLingo.exe`를 다시 실행하세요. 원본 ZIP에는 이 수정이 포함되지 않습니다. 다시 압축을 풀면 수정 파일도 다시 적용해야 합니다.

## 참고

- [SentencePiece Python: 모델 바이트 로딩](https://github.com/google/sentencepiece/blob/master/python/README.md)
- [Qt QProcess: 종료 후 출력 버퍼 읽기](https://doc.qt.io/qt-6/qprocess.html)
- [Microsoft Visual C++ 재배포 패키지](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)
