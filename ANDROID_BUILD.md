# Android APK 빌드 가이드

이 프로젝트는 Kivy 기반 앱이며, APK 빌드는 WSL(Ubuntu)에서 진행합니다.

## 0) 핵심 요약

- 코드 수정 후에는 APK를 다시 빌드해야 합니다.
- 하지만 아래 "최초 1회" 준비는 매번 할 필요가 없습니다.
- 매번 필요한 것은 "반복 빌드" 섹션의 명령만 실행하면 됩니다.

## 1) 최초 1회 준비 (WSL)

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv pipx git zip unzip openjdk-17-jdk \
	cython3 autoconf automake libtool pkg-config build-essential \
	libffi-dev libssl-dev zlib1g-dev libbz2-dev libsqlite3-dev liblzma-dev rsync

pipx ensurepath
pipx install buildozer
```

터미널을 재실행한 뒤 확인:

```bash
~/.local/bin/buildozer --version
```

Ubuntu 24.04 계열의 pip 보호(PEP 668) 대응:

```bash
mkdir -p ~/.config/pip
printf "[global]\nbreak-system-packages = true\n" > ~/.config/pip/pip.conf
echo 'export PIP_BREAK_SYSTEM_PACKAGES=1' >> ~/.bashrc
source ~/.bashrc
```

## 2) 최초 1회: 공백 없는 빌드 작업 폴더 준비

현재 Windows 경로에는 공백이 있어서 Buildozer가 실패합니다.

```bash
mkdir -p ~/builds
rsync -a --delete "/mnt/c/Users/피콜록콜록/OneDrive/바탕 화면/새 폴더/코딩/파이썬/vocabulary/" ~/builds/vocabulary/
cd ~/builds/vocabulary
buildozer init
```

## 3) 최초 1회: buildozer.spec 확인

아래 값이 맞는지 확인:

- title = VocabularyApp
- package.name = vocabularyapp
- source.include_exts = py,json,png,txt,ttf,otf,ttc
- requirements = python3,kivy,certifi
- icon.filename = %(source.dir)s/assets/icons/app_icon.png
- openai_api_key.txt is included in the APK when present in the project root.
- orientation = portrait

## 4) 코드 수정 후 반복 빌드 (매번)

아래 4줄만 실행하면 됩니다.

```bash
rsync -a --delete "/mnt/c/Users/피콜록콜록/OneDrive/바탕 화면/새 폴더/코딩/파이썬/vocabulary/" ~/builds/vocabulary/
cd ~/builds/vocabulary
buildozer android clean
buildozer -v android debug
```

APK 출력 위치: 

- ~/builds/vocabulary/bin/*.apk

## 5) 휴대폰 설치

- APK를 폰으로 전송해 설치
- 필요 시 "출처를 알 수 없는 앱 설치 허용" 활성화

## 6) 자주 발생한 오류 빠른 해결

- Cython (cython) not found

```bash
sudo apt install -y cython3
if ! command -v cython >/dev/null 2>&1; then
	sudo ln -s /usr/bin/cython3 /usr/local/bin/cython
fi
```

- autoreconf: not found

```bash
sudo apt install -y autoconf automake libtool pkg-config
```

- ModuleNotFoundError: No module named '_ctypes'

```bash
sudo apt install -y build-essential libffi-dev libssl-dev zlib1g-dev libbz2-dev libsqlite3-dev liblzma-dev
```

- ValueError: storage dir path cannot contain spaces

공백 없는 경로(~/builds/vocabulary)에서 빌드하면 해결됩니다.
