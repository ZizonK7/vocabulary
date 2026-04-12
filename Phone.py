import base64
import json
import os
import ssl
import threading
import urllib.error
import urllib.parse
import urllib.request

from kivy.app import App
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.core.text import DEFAULT_FONT, LabelBase
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.utils import platform
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

try:
	import certifi
except Exception:
	certifi = None


GEMINI_API_KEY = "AIzaSyCLJecLnx61olOdfpQYLAowyPOIHmbsrrs"
GEMINI_MODEL = "gemini-2.5-flash"


def configure_korean_font():
	# 플랫폼별 한글 폰트를 기본 폰트로 등록해 문자 깨짐을 방지합니다.
	candidate_paths = []

	if os.name == "nt":
		candidate_paths.extend(
			[
				"C:/Windows/Fonts/malgun.ttf",
				"C:/Windows/Fonts/NanumGothic.ttf",
			]
		)

	# Android 패키징 시 앱 폴더 안에 폰트를 넣어두면 가장 먼저 사용합니다.
	app_dir = os.path.dirname(__file__)
	candidate_paths.extend(
		[
			os.path.join(app_dir, "assets", "fonts", "NotoSansKR-Regular.otf"),
			os.path.join(app_dir, "assets", "fonts", "NotoSansKR-Regular.ttf"),
		]
	)

	# 기기 내 시스템 폰트 경로(제조사/버전별 차이 대응)
	candidate_paths.extend(
		[
			"/system/fonts/NotoSansKR-Regular.otf",
			"/system/fonts/NotoSansCJK-Regular.ttc",
			"/system/fonts/NanumGothic.ttf",
			"/system/fonts/DroidSansFallback.ttf",
		]
	)

	for font_path in candidate_paths:
		if os.path.exists(font_path):
			LabelBase.register(DEFAULT_FONT, font_path)
			return


class MainScreen(Screen):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		root = BoxLayout(orientation="vertical", spacing=dp(14), padding=dp(18))

		title = Label(
			text="단어장",
			font_size="30sp",
			bold=True,
			size_hint=(1, None),
			height=dp(58),
		)
		root.add_widget(title)

		subtitle = Label(
			text="핸드폰에서 바로 쓰는 단어 앱",
			font_size="15sp",
			size_hint=(1, None),
			height=dp(34),
		)
		root.add_widget(subtitle)

		root.add_widget(self._menu_button("단어 추가하기", self._go_add))
		root.add_widget(self._menu_button("단어 공부하기", self._go_study))
		root.add_widget(self._menu_button("단어장 확인하기", self._go_list))
		root.add_widget(self._menu_button("백업 코드 만들기", self._make_backup_code))
		root.add_widget(self._menu_button("백업 코드로 복원", self._restore_backup_code))
		root.add_widget(Label(text="", size_hint=(1, 1)))

		self.add_widget(root)

	def _menu_button(self, text, callback):
		button = Button(
			text=text,
			font_size="20sp",
			size_hint=(1, None),
			height=dp(76),
			background_normal="",
			background_color=(0.15, 0.39, 0.92, 1),
		)
		button.bind(on_release=callback)
		return button

	def _go_add(self, _instance):
		self.manager.current = "add"

	def _go_study(self, _instance):
		app = App.get_running_app()
		app.start_study_session()

	def _go_list(self, _instance):
		self.manager.current = "list"

	def _make_backup_code(self, _instance):
		app = App.get_running_app()
		app.show_backup_code_popup()

	def _restore_backup_code(self, _instance):
		app = App.get_running_app()
		app.show_restore_code_popup()


class AddWordScreen(Screen):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.loading_popup = None
		self.duplicate_popup = None
		root = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(18))

		root.add_widget(Label(text="새 단어 등록", font_size="26sp", bold=True, size_hint=(1, None), height=dp(56)))

		root.add_widget(Label(text="단어", size_hint=(1, None), height=dp(30), halign="left", valign="middle"))
		self.word_input = TextInput(
			multiline=False,
			size_hint=(1, None),
			height=dp(46),
			font_size="18sp",
			write_tab=False,
			input_type="mail" if platform == "android" else "text",
			keyboard_suggestions=True,
		)
		root.add_widget(self.word_input)

		root.add_widget(Label(text="뜻", size_hint=(1, None), height=dp(30), halign="left", valign="middle"))
		self.meaning_input = TextInput(
			multiline=False,
			size_hint=(1, None),
			height=dp(46),
			font_size="18sp",
			write_tab=False,
			input_type="text",
			keyboard_suggestions=False,
		)
		root.add_widget(self.meaning_input)

		root.add_widget(Label(text="예문 (선택)", size_hint=(1, None), height=dp(30), halign="left", valign="middle"))
		self.example_input = TextInput(
			multiline=True,
			size_hint=(1, None),
			height=dp(96),
			font_size="17sp",
			write_tab=False,
			input_type="text",
			keyboard_suggestions=True,
		)
		root.add_widget(self.example_input)

		save_btn = Button(
			text="저장",
			size_hint=(1, None),
			height=dp(56),
			font_size="20sp",
			background_normal="",
			background_color=(0.09, 0.64, 0.29, 1),
		)
		save_btn.bind(on_release=self._save_word)
		root.add_widget(save_btn)

		back_btn = Button(
			text="뒤로",
			size_hint=(1, None),
			height=dp(52),
			font_size="18sp",
		)
		back_btn.bind(on_release=lambda _x: self._go_home())
		root.add_widget(back_btn)

		root.add_widget(Label(text="", size_hint=(1, 1)))
		self.add_widget(root)

	def _save_word(self, _instance):
		word = self.word_input.text.strip()
		meaning = self.meaning_input.text.strip()
		example = self.example_input.text.strip()
		app = App.get_running_app()

		if not word or not meaning:
			app.show_message("입력 확인", "단어와 뜻을 모두 입력해주세요.")
			return

		existing_item = app.find_word_item(word)
		if existing_item:
			self._show_duplicate_action_popup(existing_item, meaning, example)
			return

		if not example:
			self._show_loading_popup()
			thread = threading.Thread(
				target=self._generate_and_save_word,
				args=(word, meaning),
				daemon=True,
			)
			thread.start()
			return

		app.vocabulary.append({"word": word, "meaning": meaning, "example": example, "remaining": 5})
		app.save_vocabulary_data()
		self.word_input.text = ""
		self.meaning_input.text = ""
		self.example_input.text = ""
		app.show_message("저장 완료", f"'{word}' 단어를 저장했습니다.")

	def _show_duplicate_action_popup(self, existing_item, input_meaning, input_example):
		app = App.get_running_app()
		if self.duplicate_popup:
			self.duplicate_popup.dismiss()

		desc = (
			f"'{existing_item['word']}' 단어가 이미 있습니다.\n"
			f"현재 뜻: {existing_item.get('meaning', '')}\n\n"
			"원하는 작업을 선택하세요."
		)

		content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(16))
		text_label = Label(text=desc, font_size="15sp", halign="left", valign="middle", size_hint=(1, None))
		text_label.bind(size=lambda instance, _size: setattr(instance, "text_size", (max(instance.width - dp(8), 0), None)))
		content.add_widget(text_label)

		add_btn = Button(text="뜻 추가", size_hint=(1, None), height=dp(48), background_normal="", background_color=(0.09, 0.64, 0.29, 1))
		update_btn = Button(text="뜻 수정", size_hint=(1, None), height=dp(48), background_normal="", background_color=(0.15, 0.39, 0.92, 1))
		cancel_btn = Button(text="취소", size_hint=(1, None), height=dp(46))

		content.add_widget(add_btn)
		content.add_widget(update_btn)
		content.add_widget(cancel_btn)

		self.duplicate_popup = Popup(
			title="이미 저장된 단어",
			content=content,
			size_hint=(0.9, 0.72),
			auto_dismiss=False,
		)

		add_btn.bind(
			on_release=lambda _x: self._handle_duplicate_action(
				"add", existing_item, input_meaning, input_example
			)
		)
		update_btn.bind(
			on_release=lambda _x: self._handle_duplicate_action(
				"update", existing_item, input_meaning, input_example
			)
		)
		cancel_btn.bind(on_release=lambda _x: self.duplicate_popup.dismiss())
		self.duplicate_popup.open()

	def _handle_duplicate_action(self, action, existing_item, input_meaning, input_example):
		app = App.get_running_app()
		if self.duplicate_popup:
			self.duplicate_popup.dismiss()
			self.duplicate_popup = None

		message = ""

		if action == "add":
			changed = app.add_meaning_to_item(existing_item, input_meaning)
			if changed:
				message = f"'{existing_item['word']}' 단어에 뜻을 추가했습니다."
			else:
				message = "이미 같은 뜻이 있어 추가하지 않았습니다."

		elif action == "update":
			existing_item["meaning"] = input_meaning
			message = f"'{existing_item['word']}' 단어의 뜻을 수정했습니다."

		if input_example and action in ("add", "update"):
			existing_item["example"] = input_example

		app.save_vocabulary_data()
		self.word_input.text = ""
		self.meaning_input.text = ""
		self.example_input.text = ""
		app.show_message("처리 완료", message)

	def _generate_and_save_word(self, word, meaning):
		app = App.get_running_app()
		example = app.generate_example_with_gemini(word, meaning)
		Clock.schedule_once(lambda _dt: self._finalize_save(word, meaning, example), 0)

	def _finalize_save(self, word, meaning, example):
		app = App.get_running_app()
		if self.loading_popup:
			self.loading_popup.dismiss()
			self.loading_popup = None

		app.vocabulary.append({"word": word, "meaning": meaning, "example": example, "remaining": 5})
		app.save_vocabulary_data()
		self.word_input.text = ""
		self.meaning_input.text = ""
		self.example_input.text = ""

		if example:
			app.show_message("저장 완료", f"'{word}' 단어를 저장했고 예문도 자동 추가했습니다.")
		else:
			reason = str(getattr(app, "last_gemini_error", "")).strip()
			if reason:
				app.show_message("저장 완료", f"'{word}' 단어를 저장했습니다. 예문 생성 실패 사유: {reason}")
			else:
				app.show_message("저장 완료", f"'{word}' 단어를 저장했습니다. 예문은 생성되지 않아 비워두었습니다.")

	def _show_loading_popup(self):
		if self.loading_popup:
			self.loading_popup.dismiss()

		content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(16))
		content.add_widget(Label(text="예문을 생성 중입니다...\n잠시만 기다려주세요.", font_size="16sp"))
		self.loading_popup = Popup(
			title="예문 자동 추가",
			content=content,
			size_hint=(0.82, 0.32),
			auto_dismiss=False,
		)
		self.loading_popup.open()

	def _go_home(self):
		self.manager.current = "main"


class StudyScreen(Screen):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.default_reveal_font_sp = 20
		self.min_reveal_font_sp = 12
		root = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(18))

		root.add_widget(Label(text="단어 공부", font_size="26sp", bold=True, size_hint=(1, None), height=dp(56)))

		self.word_label = Label(text="", font_size="34sp", bold=True, size_hint=(1, None), height=dp(88))
		root.add_widget(self.word_label)

		self.status_label = Label(text="", font_size="15sp", size_hint=(1, None), height=dp(32))
		root.add_widget(self.status_label)

		self.meaning_button = Button(
			text="뜻 보기",
			size_hint=(1, None),
			height=dp(66),
			font_size="20sp",
			halign="left",
			valign="middle",
			background_normal="",
			background_color=(0.89, 0.91, 0.94, 1),
			color=(0.05, 0.09, 0.16, 1),
		)
		self.meaning_button.bind(on_release=self._reveal_meaning)
		self.meaning_button.bind(size=self._update_button_text_wrap, text=self._update_button_text_wrap)
		root.add_widget(self.meaning_button)

		self.example_button = Button(
			text="예문 보기",
			size_hint=(1, None),
			height=dp(66),
			font_size="20sp",
			halign="left",
			valign="middle",
			background_normal="",
			background_color=(0.89, 0.91, 0.94, 1),
			color=(0.05, 0.09, 0.16, 1),
		)
		self.example_button.bind(on_release=self._reveal_example)
		self.example_button.bind(size=self._update_button_text_wrap, text=self._update_button_text_wrap)
		root.add_widget(self.example_button)

		hint_label = Label(
			text="뜻을 떠올린 뒤 확인하고 O/X를 누르세요.",
			font_size="14sp",
			size_hint=(1, None),
			height=dp(28),
		)
		root.add_widget(hint_label)

		ox_row = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint=(1, None), height=dp(64))

		correct_btn = Button(
			text="O",
			font_size="22sp",
			background_normal="",
			background_color=(0.09, 0.64, 0.29, 1),
		)
		correct_btn.bind(on_release=self._mark_correct)
		ox_row.add_widget(correct_btn)

		incorrect_btn = Button(
			text="X",
			font_size="22sp",
			background_normal="",
			background_color=(0.86, 0.15, 0.15, 1),
		)
		incorrect_btn.bind(on_release=self._mark_incorrect)
		ox_row.add_widget(incorrect_btn)

		root.add_widget(ox_row)

		back_btn = Button(text="뒤로", size_hint=(1, None), height=dp(52), font_size="18sp")
		back_btn.bind(on_release=lambda _x: self._go_home())
		root.add_widget(back_btn)

		root.add_widget(Label(text="", size_hint=(1, 1)))
		self.add_widget(root)

	def _update_button_text_wrap(self, button, _value):
		button.text_size = (max(button.width - dp(20), 0), None)
		self._fit_button_font(button)

	def _fit_button_font(self, button):
		base_height = dp(66)
		vertical_padding = dp(16)
		button.height = max(base_height, button.height)
		available_height = max(button.height - vertical_padding, 0)
		for size_sp in range(self.default_reveal_font_sp, self.min_reveal_font_sp - 1, -1):
			button.font_size = sp(size_sp)
			button.texture_update()
			if button.texture_size[1] <= available_height:
				return
		button.font_size = sp(self.min_reveal_font_sp)
		button.texture_update()
		needed_height = button.texture_size[1] + vertical_padding
		if needed_height > button.height:
			button.height = needed_height

	def refresh(self):
		app = App.get_running_app()
		item = app.get_current_study_item()
		if not item:
			app.show_message("단어 공부", "이번 학습 시퀀스가 완료되었습니다.")
			self.manager.current = "main"
			return

		progress = f"진행: {app.study_position + 1}/{len(app.study_sequence)}"
		self.word_label.text = item["word"]
		self.status_label.text = f"{progress} | 남은 연속 정답: {item['remaining']}회"
		self.meaning_button.text = "뜻 보기"
		self.example_button.text = "예문 보기"

	def _reveal_meaning(self, _instance):
		app = App.get_running_app()
		item = app.get_current_study_item()
		if not item:
			return
		self.meaning_button.text = item["meaning"]

	def _reveal_example(self, _instance):
		app = App.get_running_app()
		item = app.get_current_study_item()
		if not item:
			return

		example = str(item.get("example", "")).strip()
		self.example_button.text = example if example else "등록된 예문이 없습니다."

	def _mark_correct(self, _instance):
		app = App.get_running_app()
		item = app.get_current_study_item()
		if not item:
			return

		item["remaining"] -= 1
		if item["remaining"] <= 0:
			mastered_word = item["word"]
			app.vocabulary.remove(item)
			app.show_message("학습 완료", f"{mastered_word}를 완전히 숙지했습니다!")

		app.save_vocabulary_data()
		app.study_position += 1
		self.refresh()

	def _mark_incorrect(self, _instance):
		app = App.get_running_app()
		item = app.get_current_study_item()
		if not item:
			return

		item["remaining"] = 5
		app.save_vocabulary_data()
		app.study_position += 1
		self.refresh()

	def _go_home(self):
		self.manager.current = "main"


class VocabularyListScreen(Screen):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		root = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(18))

		root.add_widget(Label(text="단어장", font_size="26sp", bold=True, size_hint=(1, None), height=dp(56)))

		self.scroll = ScrollView(size_hint=(1, 1))
		self.list_container = BoxLayout(orientation="vertical", spacing=dp(2), size_hint_y=None)
		self.list_container.bind(minimum_height=self.list_container.setter("height"))
		self.scroll.add_widget(self.list_container)
		root.add_widget(self.scroll)

		back_btn = Button(text="뒤로", size_hint=(1, None), height=dp(52), font_size="18sp")
		back_btn.bind(on_release=lambda _x: self._go_home())
		root.add_widget(back_btn)

		self.add_widget(root)

	def on_pre_enter(self, *_args):
		self.refresh_list()

	def refresh_list(self):
		app = App.get_running_app()
		self.list_container.clear_widgets()

		if not app.vocabulary:
			self.list_container.add_widget(
				Label(text="아직 추가된 단어가 없습니다.", size_hint=(1, None), height=dp(42), font_size="16sp")
			)
			return

		for idx, item in enumerate(app.vocabulary, start=1):
			example = str(item.get("example", "")).strip()
			text = f"{idx}. {item['word']} - {item['meaning']}"
			if example:
				text += f"\n예문: {example}"

			item_box = BoxLayout(orientation="vertical", spacing=dp(2), size_hint=(1, None), padding=(dp(2), dp(1), dp(2), dp(1)))
			item_box.bind(minimum_height=item_box.setter("height"))
			item_label = Label(text=text, size_hint=(1, None), halign="left", valign="middle")
			item_label.bind(size=self._update_wrapped_list_label, text=self._update_wrapped_list_label)
			self._update_wrapped_list_label(item_label, item_label.size)

			delete_btn = Button(
				text="이 단어 삭제",
				size_hint=(1, None),
				height=dp(32),
				font_size="14sp",
				background_normal="",
				background_color=(0.86, 0.15, 0.15, 1),
			)
			delete_btn.bind(on_release=lambda _x, target=item: self._show_delete_confirm(target))

			item_box.add_widget(item_label)
			item_box.add_widget(delete_btn)
			self.list_container.add_widget(item_box)

	def _go_home(self):
		self.manager.current = "main"

	def _update_wrapped_list_label(self, label, _size):
		label.text_size = (max(label.width - dp(8), 0), None)
		label.texture_update()
		label.height = max(dp(30), label.texture_size[1] + dp(8))

	def _show_delete_confirm(self, item):
		app = App.get_running_app()
		content = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(16))
		text = Label(
			text=f"'{item.get('word', '')}' 단어를 삭제할까요?",
			font_size="16sp",
			halign="left",
			valign="middle",
		)
		text.bind(size=lambda instance, _size: setattr(instance, "text_size", (max(instance.width - dp(8), 0), None)))
		content.add_widget(text)

		btn_row = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint=(1, None), height=dp(46))
		cancel_btn = Button(text="취소")
		delete_btn = Button(text="삭제", background_normal="", background_color=(0.86, 0.15, 0.15, 1))
		btn_row.add_widget(cancel_btn)
		btn_row.add_widget(delete_btn)
		content.add_widget(btn_row)

		popup = Popup(title="단어 삭제", content=content, size_hint=(0.85, 0.35), auto_dismiss=False)

		def do_delete(_instance):
			if item in app.vocabulary:
				app.vocabulary.remove(item)
				app.save_vocabulary_data()
			popup.dismiss()
			self.refresh_list()
			app.show_message("삭제 완료", "단어를 삭제했습니다.")

		cancel_btn.bind(on_release=popup.dismiss)
		delete_btn.bind(on_release=do_delete)
		popup.open()


class VocabularyApp(App):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.vocabulary = []
		self.study_sequence = []
		self.study_position = 0
		self.default_data_file_path = os.path.join(os.path.dirname(__file__), "vocabulary_data.json")
		self.data_file_path = self.default_data_file_path
		self.gemini_api_key = GEMINI_API_KEY.strip()
		self.gemini_model = GEMINI_MODEL
		self.last_gemini_error = ""

	def build(self):
		configure_korean_font()
		Window.clearcolor = (0.06, 0.09, 0.16, 1)
		self.data_file_path = self._resolve_data_file_path()
		self._initialize_data_file_once()
		self.load_vocabulary_data()

		sm = ScreenManager()
		sm.add_widget(MainScreen(name="main"))
		sm.add_widget(AddWordScreen(name="add"))
		sm.add_widget(StudyScreen(name="study"))
		sm.add_widget(VocabularyListScreen(name="list"))
		return sm

	def _resolve_data_file_path(self):
		if platform != "android":
			return self.default_data_file_path

		data_dir = self.user_data_dir or os.path.dirname(__file__)
		os.makedirs(data_dir, exist_ok=True)
		return os.path.join(data_dir, "vocabulary_data.json")

	def _initialize_data_file_once(self):
		# 기존 파일이 있으면 절대 덮어쓰지 않아 업데이트 시 사용자 데이터가 유지됩니다.
		if os.path.exists(self.data_file_path):
			return

		if os.path.exists(self.default_data_file_path):
			try:
				with open(self.default_data_file_path, "r", encoding="utf-8") as src:
					data = json.load(src)
				if not isinstance(data, list):
					data = []
			except Exception:
				data = []
		else:
			data = []

		with open(self.data_file_path, "w", encoding="utf-8") as dst:
			json.dump(data, dst, ensure_ascii=False, indent=2)

	def load_vocabulary_data(self):
		if not os.path.exists(self.data_file_path):
			self.vocabulary = []
			return

		try:
			with open(self.data_file_path, "r", encoding="utf-8") as file:
				data = json.load(file)

			loaded_items = []
			for item in data:
				word = str(item.get("word", "")).strip()
				meaning = str(item.get("meaning", "")).strip()
				example = str(item.get("example", "")).strip()
				remaining = item.get("remaining", 5)

				if not word or not meaning:
					continue

				if not isinstance(remaining, int):
					remaining = 5
				remaining = max(0, min(5, remaining))

				loaded_items.append({"word": word, "meaning": meaning, "example": example, "remaining": remaining})

			self.vocabulary = loaded_items
		except Exception:
			self.vocabulary = []

	def save_vocabulary_data(self):
		serializable_items = []
		for item in self.vocabulary:
			serializable_items.append(
				{
					"word": item.get("word", ""),
					"meaning": item.get("meaning", ""),
					"example": item.get("example", ""),
					"remaining": int(item.get("remaining", 5)),
				}
			)

		with open(self.data_file_path, "w", encoding="utf-8") as file:
			json.dump(serializable_items, file, ensure_ascii=False, indent=2)

	def find_word_item(self, word):
		normalized_word = str(word).strip().lower()
		for item in self.vocabulary:
			item_word = str(item.get("word", "")).strip().lower()
			if item_word == normalized_word:
				return item
		return None

	def _split_meanings(self, meaning_text):
		text = str(meaning_text or "")
		normalized = text.replace("/", ",").replace(";", ",")
		parts = [part.strip() for part in normalized.split(",")]
		return [part for part in parts if part]

	def add_meaning_to_item(self, item, new_meaning):
		current_parts = self._split_meanings(item.get("meaning", ""))
		new_part = str(new_meaning).strip()
		if not new_part:
			return False

		exists = any(part.lower() == new_part.lower() for part in current_parts)
		if exists:
			return False

		current_parts.append(new_part)
		item["meaning"] = ", ".join(current_parts)
		return True

	def remove_meaning_from_item(self, item, meaning_to_remove):
		target = str(meaning_to_remove).strip().lower()
		if not target:
			if item in self.vocabulary:
				self.vocabulary.remove(item)
				return "word-removed"
			return "not-found"

		current_parts = self._split_meanings(item.get("meaning", ""))
		remaining_parts = [part for part in current_parts if part.lower() != target]

		if len(remaining_parts) == len(current_parts):
			return "not-found"

		if not remaining_parts:
			if item in self.vocabulary:
				self.vocabulary.remove(item)
				return "word-removed"
			return "not-found"

		item["meaning"] = ", ".join(remaining_parts)
		return "meaning-removed"

	def show_message(self, title, text):
		content = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(16))
		message_label = Label(text=text, font_size="16sp", halign="left", valign="middle")
		message_label.bind(size=lambda instance, _size: setattr(instance, "text_size", (max(instance.width - dp(8), 0), None)))
		content.add_widget(message_label)
		close_btn = Button(text="확인", size_hint=(1, None), height=dp(48))
		content.add_widget(close_btn)

		popup = Popup(title=title, content=content, size_hint=(0.85, 0.45), auto_dismiss=False)
		close_btn.bind(on_release=popup.dismiss)
		popup.open()

	def create_backup_code(self):
		payload = {
			"version": 1,
			"vocabulary": self.vocabulary,
		}
		serialized = json.dumps(payload, ensure_ascii=False).encode("utf-8")
		return base64.urlsafe_b64encode(serialized).decode("ascii")

	def restore_from_backup_code(self, raw_code):
		code = str(raw_code or "").strip()
		if not code:
			return False, "백업 코드를 입력해주세요."

		try:
			decoded = base64.urlsafe_b64decode(code.encode("ascii")).decode("utf-8")
			payload = json.loads(decoded)
		except Exception:
			return False, "백업 코드 형식이 올바르지 않습니다."

		if not isinstance(payload, dict):
			return False, "백업 코드 내용이 손상되었습니다."

		items = payload.get("vocabulary")
		if not isinstance(items, list):
			return False, "복원할 단어 목록을 찾을 수 없습니다."

		restored_items = []
		for item in items:
			if not isinstance(item, dict):
				continue
			word = str(item.get("word", "")).strip()
			meaning = str(item.get("meaning", "")).strip()
			example = str(item.get("example", "")).strip()
			remaining = item.get("remaining", 5)

			if not word or not meaning:
				continue

			if not isinstance(remaining, int):
				remaining = 5
			remaining = max(0, min(5, remaining))
			restored_items.append({"word": word, "meaning": meaning, "example": example, "remaining": remaining})

		self.vocabulary = restored_items
		self.save_vocabulary_data()
		return True, f"복원이 완료되었습니다. 단어 {len(restored_items)}개를 불러왔습니다."

	def show_backup_code_popup(self):
		backup_code = self.create_backup_code()

		content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(14))
		content.add_widget(Label(text="아래 코드를 안전한 곳에 저장하세요.", size_hint=(1, None), height=dp(28), font_size="15sp"))

		code_input = TextInput(
			text=backup_code,
			readonly=True,
			multiline=True,
			size_hint=(1, 1),
			font_size="13sp",
		)
		content.add_widget(code_input)

		button_row = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint=(1, None), height=dp(48))
		copy_btn = Button(text="코드 복사")
		close_btn = Button(text="닫기")
		button_row.add_widget(copy_btn)
		button_row.add_widget(close_btn)
		content.add_widget(button_row)

		popup = Popup(title="백업 코드", content=content, size_hint=(0.92, 0.7), auto_dismiss=False)

		def _copy_code(_instance):
			Clipboard.copy(backup_code)
			self.show_message("복사 완료", "백업 코드를 클립보드에 복사했습니다.")

		copy_btn.bind(on_release=_copy_code)
		close_btn.bind(on_release=popup.dismiss)
		popup.open()

	def show_restore_code_popup(self):
		content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(14))
		content.add_widget(Label(text="저장해둔 백업 코드를 붙여넣으세요.", size_hint=(1, None), height=dp(28), font_size="15sp"))

		code_input = TextInput(
			text="",
			multiline=True,
			size_hint=(1, 1),
			font_size="13sp",
		)
		content.add_widget(code_input)

		button_row = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint=(1, None), height=dp(48))
		restore_btn = Button(text="복원 실행")
		cancel_btn = Button(text="취소")
		button_row.add_widget(restore_btn)
		button_row.add_widget(cancel_btn)
		content.add_widget(button_row)

		popup = Popup(title="백업 코드 복원", content=content, size_hint=(0.92, 0.7), auto_dismiss=False)

		def _restore(_instance):
			success, message = self.restore_from_backup_code(code_input.text)
			if success:
				popup.dismiss()
				self.show_message("복원 완료", message)
			else:
				self.show_message("복원 실패", message)

		restore_btn.bind(on_release=_restore)
		cancel_btn.bind(on_release=popup.dismiss)
		popup.open()

	def start_study_session(self):
		if not self.vocabulary:
			self.show_message("단어 공부", "공부할 단어가 없습니다. 먼저 단어를 추가해주세요.")
			return

		self.study_sequence = list(reversed(self.vocabulary.copy()))
		self.study_position = 0
		self.root.current = "study"
		study_screen = self.root.get_screen("study")
		study_screen.refresh()

	def get_current_study_item(self):
		if not self.vocabulary or not self.study_sequence:
			return None

		while self.study_position < len(self.study_sequence):
			item = self.study_sequence[self.study_position]
			if item in self.vocabulary:
				if "remaining" not in item:
					item["remaining"] = 5
				return item
			self.study_position += 1

		return None

	def _build_ssl_context(self):
		if certifi:
			try:
				return ssl.create_default_context(cafile=certifi.where())
			except Exception:
				return None
		return None

	def generate_example_with_gemini(self, word, meaning):
		self.last_gemini_error = ""
		if not self.gemini_api_key:
			self.last_gemini_error = "API 키가 비어 있습니다."
			return ""

		prompt = (
            "You are a professional English vocabulary tutor. "
            "Write exactly ONE natural and practical English example sentence using the target word. "
            "CRITICAL RULES:\n"
            "1. The sentence MUST reflect the provided 'Korean meaning' (this is important for words with multiple meanings).\n"
		"2. Use only widely known words and basic grammar that a high school graduate should understand.\n"
		"3. Keep the sentence clear and simple. Avoid advanced or rare words, idioms, and complex clauses.\n"
		"4. Output ONLY the raw sentence. No quotes, no translations, no explanations, no conversational filler.\n\n"
            f"Target word: {word}\n"
            f"Korean meaning: {meaning}"
        )

		url = (
			"https://generativelanguage.googleapis.com/v1beta/models/"
			f"{urllib.parse.quote(self.gemini_model)}:generateContent"
			f"?key={urllib.parse.quote(self.gemini_api_key)}"
		)

		payload = {
			"contents": [{"parts": [{"text": prompt}]}],
			"generationConfig": {
				"temperature": 0.7,
				"maxOutputTokens": 60,
			},
		}

		request = urllib.request.Request(
			url,
			data=json.dumps(payload).encode("utf-8"),
			headers={"Content-Type": "application/json"},
			method="POST",
		)

		ssl_context = self._build_ssl_context()

		try:
			with urllib.request.urlopen(request, timeout=10, context=ssl_context) as response:
				result = json.loads(response.read().decode("utf-8"))
		except urllib.error.HTTPError as http_error:
			try:
				error_body = http_error.read().decode("utf-8", errors="ignore")
			except Exception:
				error_body = ""
			self.last_gemini_error = f"HTTP {http_error.code}"
			if error_body:
				self.last_gemini_error += f" | {error_body[:140]}"
			return ""
		except (urllib.error.URLError, TimeoutError, OSError, ValueError):
			self.last_gemini_error = "네트워크/SSL 연결 실패"
			return ""

		error_info = result.get("error")
		if isinstance(error_info, dict):
			status = str(error_info.get("status", "")).upper()
			message = str(error_info.get("message", "")).strip()
			self.last_gemini_error = status or "API 오류"
			if message:
				self.last_gemini_error += f" | {message[:140]}"
			if status == "RESOURCE_EXHAUSTED":
				return ""
			return ""

		candidates = result.get("candidates", [])
		if not candidates:
			self.last_gemini_error = "응답에 candidates가 없습니다."
			return ""

		parts = candidates[0].get("content", {}).get("parts", [])
		if not parts:
			self.last_gemini_error = "응답에 문장 파트가 없습니다."
			return ""

		text = " ".join(str(part.get("text", "")).strip() for part in parts if isinstance(part, dict)).strip()
		if not text:
			self.last_gemini_error = "응답 문장이 비어 있습니다."
			return ""

		text = text.replace("\n", " ").strip().strip('"').strip("'")
		if text.lower().startswith("example:"):
			text = text.split(":", 1)[1].strip()

		return text


if __name__ == "__main__":
	configure_korean_font()
	VocabularyApp().run()
