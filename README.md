# vocabulary
Make vocabulary program

## GPT 예문 자동 생성

단어와 뜻만 입력하고 예문을 비워 둔 채 저장하면 OpenAI Responses API로 예문을 한 문장 생성해서 함께 저장합니다.

API 키 설정 방법:

1. 프로젝트 루트에 `openai_api_key.txt`를 만들고 API 키만 한 줄로 붙여넣습니다.
2. 개발 중에는 환경변수 `OPENAI_API_KEY`를 설정해도 됩니다.

APK를 빌드할 때 `openai_api_key.txt`가 앱 안에 포함되어, 설치된 앱은 이 키를 기본으로 사용합니다. 이 파일은 `.gitignore`에 포함되어 GitHub에는 올라가지 않습니다.

기본 모델은 `gpt-5.4-nano`이며, 환경변수 `OPENAI_MODEL`로 바꿀 수 있습니다.

## 앱 아이콘 설정

앱 아이콘으로 쓸 PNG 파일을 아래 경로에 넣습니다.

```text
assets/icons/app_icon.png
```

권장 크기는 512x512입니다. 아이콘 파일을 바꾼 뒤 APK를 다시 빌드하면 새 아이콘이 반영됩니다.
