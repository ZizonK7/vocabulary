# Vocabulary

간단한 단어장 학습 앱입니다.  
단어를 추가하고, 뜻을 확인하며, O/X 복습으로 암기 상태를 관리할 수 있습니다.

## 주요 기능

- 단어/뜻 추가 및 JSON 파일 저장
- 저장된 단어 목록 확인
- 복습 모드(O/X)
  - O: 남은 연속 정답 횟수(`remaining`) 1 감소
  - X: 남은 연속 정답 횟수 5로 초기화
  - `remaining`이 0이 되면 단어장에서 제거

## 프로젝트 구조

- `Test.py` : Tkinter 기반 데스크톱 앱 실행 파일
- `vocabulary_data.json` : 단어 데이터 저장 파일
- `ANDROID_BUILD.md` : Android APK 빌드 가이드
- `main.py` : 모바일 앱 진입점(환경에 따라 별도 모듈 필요)

## 실행 방법 (Desktop)

Python 3 환경에서 아래 명령으로 실행합니다.

```bash
python Test.py
```

## 데이터 형식

`vocabulary_data.json`의 각 항목은 아래 형식을 사용합니다.

```json
{
  "word": "example",
  "meaning": "예시",
  "remaining": 5
}
```

## Android 빌드

Android APK 빌드는 `ANDROID_BUILD.md`를 참고하세요.
