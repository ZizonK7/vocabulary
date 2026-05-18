import base64
import json
import os
import ssl
import threading
import urllib.error
import urllib.request

from kivy.app import App
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.core.text import DEFAULT_FONT, Label as CoreTextLabel, LabelBase
from kivy.core.window import Window
from kivy.graphics import Color, Line, RoundedRectangle
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


OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
OPENAI_MODEL_ENV = "OPENAI_MODEL"
OPENAI_MODEL = os.environ.get(OPENAI_MODEL_ENV, "gpt-5.4-nano").strip() or "gpt-5.4-nano"
LOCAL_OPENAI_API_KEY_FILE = "openai_api_key.txt"

PALETTE = {
	"background": (0.95, 0.96, 0.98, 1),
	"surface": (1, 1, 1, 1),
	"surface_alt": (0.91, 0.94, 0.97, 1),
	"primary": (0.10, 0.31, 0.64, 1),
	"success": (0.08, 0.53, 0.34, 1),
	"danger": (0.78, 0.18, 0.20, 1),
	"text": (0.08, 0.11, 0.17, 1),
	"muted": (0.40, 0.45, 0.54, 1),
	"border": (0.79, 0.84, 0.90, 1),
	"white": (1, 1, 1, 1),
}

BUTTON_STYLES = {
	"primary": (PALETTE["primary"], PALETTE["white"], None),
	"success": (PALETTE["success"], PALETTE["white"], None),
	"danger": (PALETTE["danger"], PALETTE["white"], None),
	"secondary": (PALETTE["surface"], PALETTE["text"], PALETTE["border"]),
	"quiet": (PALETTE["surface_alt"], PALETTE["text"], None),
	"reveal": (PALETTE["surface"], PALETTE["text"], PALETTE["border"]),
}


def _pressed_color(color):
	return (max(color[0] - 0.05, 0), max(color[1] - 0.05, 0), max(color[2] - 0.05, 0), color[3])


def _font_sp_number(value, default=16):
	try:
		return int(float(str(value).replace("sp", "")))
	except (TypeError, ValueError):
		return default


def _wrap_label(label, horizontal_padding=0):
	label.text_size = (max(label.width - dp(horizontal_padding), 0), None)


def _fit_wrapped_label(label, min_height=28, horizontal_padding=0, vertical_padding=8):
	_wrap_label(label, horizontal_padding)
	label.texture_update()
	label.height = max(dp(min_height), label.texture_size[1] + dp(vertical_padding))


def _fit_text_to_box(widget, max_sp, min_sp, horizontal_padding=0, vertical_padding=0, grow_height=True, guarded=True):
	if guarded and getattr(widget, "_fitting_text", False):
		return

	if guarded:
		widget._fitting_text = True
	try:
		_fit_text_to_box_inner(widget, max_sp, min_sp, horizontal_padding, vertical_padding, grow_height)
	finally:
		if guarded:
			widget._fitting_text = False


def _fit_text_to_box_inner(widget, max_sp, min_sp, horizontal_padding=0, vertical_padding=0, grow_height=True):
	available_width = max(widget.width - dp(horizontal_padding), 1)
	available_height = max(widget.height - dp(vertical_padding), 1)
	widget.text_size = (available_width, None)

	for size_sp in range(max_sp, min_sp - 1, -1):
		widget.font_size = sp(size_sp)
		widget.texture_update()
		if widget.texture_size[1] <= available_height and _longest_unwrapped_width(widget) <= available_width:
			return

	widget.font_size = sp(min_sp)
	widget.texture_update()
	if grow_height:
		widget.height = max(widget.height, widget.texture_size[1] + dp(vertical_padding))


def _longest_unwrapped_width(widget):
	text = str(widget.text or "")
	parts = text.replace("\n", " ").split()
	longest = max(parts, key=len) if parts else text
	if not longest:
		return 0

	label = CoreTextLabel(
		text=longest,
		font_size=widget.font_size,
		font_name=getattr(widget, "font_name", DEFAULT_FONT),
		bold=getattr(widget, "bold", False),
	)
	label.refresh()
	return label.texture.size[0]


def make_label(text, font_size="16sp", bold=False, color=None, height=None, halign="left", valign="middle"):
	label = Label(
		text=text,
		font_size=font_size,
		bold=bold,
		color=color or PALETTE["text"],
		halign=halign,
		valign=valign,
		size_hint=(1, None) if height is not None else (1, 1),
		height=height if height is not None else dp(32),
	)
	label.bind(size=lambda instance, _size: _wrap_label(instance, 4))
	return label


def style_text_input(field):
	field.background_normal = ""
	field.background_active = ""
	field.background_color = (0, 0, 0, 0)
	field.foreground_color = PALETTE["text"]
	field.cursor_color = PALETTE["primary"]
	field.hint_text_color = PALETTE["muted"]
	field.padding = (dp(4), dp(8), dp(4), dp(8))
	return field


class Surface(BoxLayout):
	def __init__(self, surface_color=None, border_color=None, radius=16, **kwargs):
		super().__init__(**kwargs)
		self.surface_color = surface_color or PALETTE["surface"]
		self.border_color = border_color
		self.radius = dp(radius)
		with self.canvas.before:
			self._bg_color = Color(*self.surface_color)
			self._bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius])
			if self.border_color:
				self._line_color = Color(*self.border_color)
				self._border_line = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, self.radius), width=1)
			else:
				self._border_line = None
		self.bind(pos=self._update_canvas, size=self._update_canvas)

	def _update_canvas(self, *_args):
		self._bg_rect.pos = self.pos
		self._bg_rect.size = self.size
		self._bg_rect.radius = [self.radius]
		if self._border_line:
			self._border_line.rounded_rectangle = (self.x, self.y, self.width, self.height, self.radius)


class AppButton(Button):
	def __init__(self, variant="primary", radius=14, **kwargs):
		bg_color, text_color, border_color = BUTTON_STYLES.get(variant, BUTTON_STYLES["primary"])
		self.max_font_sp = _font_sp_number(kwargs.get("font_size", "17sp"), 17)
		self.min_font_sp = min(10, self.max_font_sp)
		kwargs.setdefault("size_hint", (1, None))
		kwargs.setdefault("height", dp(54))
		kwargs.setdefault("font_size", "17sp")
		kwargs.setdefault("bold", True)
		kwargs.setdefault("halign", "center")
		kwargs.setdefault("valign", "middle")
		super().__init__(**kwargs)
		self.normal_bg_color = bg_color
		self.pressed_bg_color = _pressed_color(bg_color)
		self.border_color = border_color
		self.radius = dp(radius)
		self.background_normal = ""
		self.background_down = ""
		self.background_color = (0, 0, 0, 0)
		self.color = text_color
		with self.canvas.before:
			self._bg_color = Color(*self.normal_bg_color)
			self._bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius])
			if self.border_color:
				self._line_color = Color(*self.border_color)
				self._border_line = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, self.radius), width=1)
			else:
				self._border_line = None
		self.bind(pos=self._update_canvas, size=self._update_canvas, state=self._update_state)
		self.bind(size=self._update_text_size, text=self._update_text_size)

	def _update_canvas(self, *_args):
		self._bg_rect.pos = self.pos
		self._bg_rect.size = self.size
		self._bg_rect.radius = [self.radius]
		if self._border_line:
			self._border_line.rounded_rectangle = (self.x, self.y, self.width, self.height, self.radius)

	def _update_state(self, *_args):
		self._bg_color.rgba = self.pressed_bg_color if self.state == "down" else self.normal_bg_color

	def _update_text_size(self, *_args):
		if getattr(self, "_fitting_text", False):
			return
		self.text_size = (max(self.width - dp(24), 0), None)
		if self.width > 0 and self.height > 0:
			_fit_text_to_box(self, self.max_font_sp, self.min_font_sp, 24, 14, grow_height=False)


def make_text_field(multiline=False, height=52, font_size="17sp", hint_text="", **kwargs):
	field = TextInput(
		multiline=multiline,
		size_hint=(1, 1),
		font_size=font_size,
		hint_text=hint_text,
		write_tab=False,
		**kwargs,
	)
	style_text_input(field)
	shell = Surface(
		orientation="vertical",
		size_hint=(1, None),
		height=dp(height),
		padding=(dp(12), dp(2), dp(12), dp(2)),
		surface_color=PALETTE["surface"],
		border_color=PALETTE["border"],
		radius=14,
	)
	shell.add_widget(field)
	return shell, field


def make_popup(title, content, size_hint, auto_dismiss=False):
	frame = Surface(
		orientation="vertical",
		spacing=dp(8),
		padding=(dp(12), dp(10), dp(12), dp(12)),
		surface_color=PALETTE["surface"],
		border_color=PALETTE["border"],
		radius=16,
	)
	title_label = Label(
		text=title,
		size_hint=(1, None),
		height=dp(30),
		font_size="18sp",
		bold=True,
		color=PALETTE["text"],
		halign="left",
		valign="middle",
	)
	title_label.bind(size=lambda instance, _size: _wrap_label(instance, 2))
	frame.add_widget(title_label)
	content.size_hint = (1, 1)
	frame.add_widget(content)

	popup = Popup(title="", content=frame, size_hint=size_hint, auto_dismiss=auto_dismiss)
	popup.background = ""
	popup.background_color = (0, 0, 0, 0)
	popup.separator_color = PALETTE["border"]
	popup.title_color = PALETTE["text"]
	popup.title_size = "0sp"
	return popup


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
		root = BoxLayout(orientation="vertical", spacing=dp(14), padding=(dp(20), dp(24), dp(20), dp(18)))

		title = Label(
			text="단어장",
			font_size="32sp",
			bold=True,
			color=PALETTE["text"],
			halign="left",
			valign="middle",
			size_hint=(1, None),
			height=dp(48),
		)
		title.bind(size=lambda instance, _size: _wrap_label(instance, 2))
		root.add_widget(title)

		subtitle = Label(
			text="오늘도 한 단어씩 차분하게",
			font_size="15sp",
			color=PALETTE["muted"],
			halign="left",
			valign="middle",
			size_hint=(1, None),
			height=dp(30),
		)
		subtitle.bind(size=lambda instance, _size: _wrap_label(instance, 2))
		root.add_widget(subtitle)

		summary = Surface(
			orientation="vertical",
			spacing=dp(2),
			padding=(dp(16), dp(12), dp(16), dp(12)),
			size_hint=(1, None),
			height=dp(82),
			border_color=PALETTE["border"],
		)
		self.summary_label = Label(
			text="저장된 단어 0개",
			font_size="21sp",
			bold=True,
			color=PALETTE["text"],
			halign="left",
			valign="middle",
			size_hint=(1, None),
			height=dp(34),
		)
		self.summary_label.bind(size=lambda instance, _size: _wrap_label(instance, 2))
		self.summary_caption = Label(
			text="학습할 단어를 기다리고 있어요.",
			font_size="14sp",
			color=PALETTE["muted"],
			halign="left",
			valign="middle",
			size_hint=(1, None),
			height=dp(24),
		)
		self.summary_caption.bind(size=lambda instance, _size: _wrap_label(instance, 2))
		summary.add_widget(self.summary_label)
		summary.add_widget(self.summary_caption)
		root.add_widget(summary)

		root.add_widget(self._menu_button("단어 추가", self._go_add, "primary"))
		root.add_widget(self._menu_button("공부 시작", self._go_study, "success"))
		root.add_widget(self._menu_button("단어장 보기", self._go_list, "secondary"))

		backup_row = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint=(1, None), height=dp(52))
		backup_row.add_widget(self._menu_button("백업", self._make_backup_code, "quiet", height=dp(52)))
		backup_row.add_widget(self._menu_button("복원", self._restore_backup_code, "quiet", height=dp(52)))
		root.add_widget(backup_row)
		root.add_widget(Label(text="", size_hint=(1, 1)))

		self.add_widget(root)

	def on_pre_enter(self, *_args):
		app = App.get_running_app()
		total = len(app.vocabulary)
		active = sum(1 for item in app.vocabulary if int(item.get("remaining", 5)) > 0)
		self.summary_label.text = f"저장된 단어 {total}개"
		self.summary_caption.text = f"오늘 복습할 단어 {active}개" if active else "학습할 단어를 기다리고 있어요."

	def _menu_button(self, text, callback, variant="primary", height=None):
		button = AppButton(
			text=text,
			variant=variant,
			font_size="18sp",
			size_hint=(1, None),
			height=height or dp(58),
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
		root = BoxLayout(orientation="vertical", spacing=dp(14), padding=(dp(20), dp(22), dp(20), dp(18)))

		header = Label(
			text="새 단어 등록",
			font_size="27sp",
			bold=True,
			color=PALETTE["text"],
			halign="left",
			valign="middle",
			size_hint=(1, None),
			height=dp(48),
		)
		header.bind(size=lambda instance, _size: _wrap_label(instance, 2))
		root.add_widget(header)

		scroll = ScrollView(size_hint=(1, 1))
		form = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None)
		form.bind(minimum_height=form.setter("height"))

		form.add_widget(make_label("단어", font_size="14sp", bold=True, color=PALETTE["muted"], height=dp(24)))
		word_field, self.word_input = make_text_field(
			multiline=False,
			height=52,
			font_size="18sp",
			hint_text="apple",
			input_type="mail" if platform == "android" else "text",
			keyboard_suggestions=True,
		)
		form.add_widget(word_field)

		form.add_widget(make_label("뜻", font_size="14sp", bold=True, color=PALETTE["muted"], height=dp(24)))
		meaning_field, self.meaning_input = make_text_field(
			multiline=False,
			height=52,
			font_size="18sp",
			hint_text="사과",
			input_type="text",
			keyboard_suggestions=False,
		)
		form.add_widget(meaning_field)

		form.add_widget(make_label("예문", font_size="14sp", bold=True, color=PALETTE["muted"], height=dp(24)))
		example_field, self.example_input = make_text_field(
			multiline=True,
			height=118,
			font_size="16sp",
			hint_text="비워두면 예문을 자동으로 채웁니다.",
			input_type="text",
			keyboard_suggestions=True,
		)
		form.add_widget(example_field)
		scroll.add_widget(form)
		root.add_widget(scroll)

		button_row = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint=(1, None), height=dp(54))
		back_btn = AppButton(
			text="뒤로",
			variant="secondary",
			size_hint=(0.38, None),
			height=dp(54),
			font_size="17sp",
		)
		back_btn.bind(on_release=lambda _x: self._go_home())
		button_row.add_widget(back_btn)

		save_btn = AppButton(
			text="저장",
			variant="primary",
			size_hint=(1, None),
			height=dp(54),
			font_size="18sp",
		)
		save_btn.bind(on_release=self._save_word)
		button_row.add_widget(save_btn)
		root.add_widget(button_row)
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
		text_label = Label(
			text=desc,
			font_size="15sp",
			color=PALETTE["text"],
			halign="left",
			valign="middle",
			size_hint=(1, None),
		)
		text_label.bind(size=lambda instance, _size: _fit_wrapped_label(instance, 88, 8, 8))
		content.add_widget(text_label)

		add_btn = AppButton(text="뜻 추가", variant="success", size_hint=(1, None), height=dp(48), font_size="16sp")
		update_btn = AppButton(text="뜻 수정", variant="primary", size_hint=(1, None), height=dp(48), font_size="16sp")
		cancel_btn = AppButton(text="취소", variant="secondary", size_hint=(1, None), height=dp(46), font_size="16sp")

		content.add_widget(add_btn)
		content.add_widget(update_btn)
		content.add_widget(cancel_btn)

		self.duplicate_popup = make_popup(
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
		example = app.generate_example_with_openai(word, meaning)
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
			reason = str(getattr(app, "last_openai_error", "")).strip()
			if reason:
				app.show_message("저장 완료", f"'{word}' 단어를 저장했습니다. 예문 생성 실패 사유: {reason}")
			else:
				app.show_message("저장 완료", f"'{word}' 단어를 저장했습니다. 예문은 생성되지 않아 비워두었습니다.")

	def _show_loading_popup(self):
		if self.loading_popup:
			self.loading_popup.dismiss()

		content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(16))
		content.add_widget(Label(text="예문을 생성 중입니다...\n잠시만 기다려주세요.", font_size="16sp", color=PALETTE["text"]))
		self.loading_popup = make_popup(
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
		root = BoxLayout(orientation="vertical", spacing=dp(14), padding=(dp(20), dp(22), dp(20), dp(18)))

		header = Label(
			text="단어 공부",
			font_size="27sp",
			bold=True,
			color=PALETTE["text"],
			halign="left",
			valign="middle",
			size_hint=(1, None),
			height=dp(46),
		)
		header.bind(size=lambda instance, _size: _wrap_label(instance, 2))
		root.add_widget(header)

		study_scroll = ScrollView(size_hint=(1, 1))
		study_content = BoxLayout(orientation="vertical", spacing=dp(12), size_hint_y=None)
		study_content.bind(minimum_height=study_content.setter("height"))

		word_panel = Surface(
			orientation="vertical",
			spacing=dp(4),
			padding=(dp(16), dp(16), dp(16), dp(14)),
			size_hint=(1, None),
			height=dp(128),
			border_color=PALETTE["border"],
		)
		self.word_label = Label(
			text="",
			font_size="34sp",
			bold=True,
			color=PALETTE["text"],
			halign="center",
			valign="middle",
			size_hint=(1, None),
			height=dp(66),
		)
		self.word_label.bind(size=lambda instance, _size: _wrap_label(instance, 8))
		word_panel.add_widget(self.word_label)

		self.status_label = Label(
			text="",
			font_size="14sp",
			color=PALETTE["muted"],
			halign="center",
			valign="middle",
			size_hint=(1, None),
			height=dp(28),
		)
		self.status_label.bind(size=lambda instance, _size: _wrap_label(instance, 8))
		word_panel.add_widget(self.status_label)
		study_content.add_widget(word_panel)

		self.meaning_button = AppButton(
			text="뜻 보기",
			variant="reveal",
			size_hint=(1, None),
			height=dp(66),
			font_size="20sp",
			halign="left",
			valign="middle",
			bold=False,
		)
		self.meaning_button.bind(on_release=self._reveal_meaning)
		self.meaning_button.bind(size=self._update_button_text_wrap, text=self._update_button_text_wrap)
		study_content.add_widget(self.meaning_button)

		self.example_button = AppButton(
			text="예문 보기",
			variant="reveal",
			size_hint=(1, None),
			height=dp(66),
			font_size="20sp",
			halign="left",
			valign="middle",
			bold=False,
		)
		self.example_button.bind(on_release=self._reveal_example)
		self.example_button.bind(size=self._update_button_text_wrap, text=self._update_button_text_wrap)
		study_content.add_widget(self.example_button)

		hint_label = Label(
			text="뜻을 떠올린 뒤 확인하고 O/X를 누르세요.",
			font_size="14sp",
			color=PALETTE["muted"],
			size_hint=(1, None),
			height=dp(28),
		)
		study_content.add_widget(hint_label)
		study_scroll.add_widget(study_content)
		root.add_widget(study_scroll)

		ox_row = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint=(1, None), height=dp(64))

		correct_btn = AppButton(
			text="O",
			variant="success",
			font_size="22sp",
			size_hint=(1, 1),
		)
		correct_btn.bind(on_release=self._mark_correct)
		ox_row.add_widget(correct_btn)

		incorrect_btn = AppButton(
			text="X",
			variant="danger",
			font_size="22sp",
			size_hint=(1, 1),
		)
		incorrect_btn.bind(on_release=self._mark_incorrect)
		ox_row.add_widget(incorrect_btn)

		root.add_widget(ox_row)

		back_btn = AppButton(text="뒤로", variant="secondary", size_hint=(1, None), height=dp(52), font_size="17sp")
		back_btn.bind(on_release=lambda _x: self._go_home())
		root.add_widget(back_btn)

		self.add_widget(root)

	def _update_button_text_wrap(self, button, _value):
		if getattr(button, "_fitting_text", False):
			return
		self._fit_button_font(button)

	def _fit_button_font(self, button):
		if getattr(button, "_fitting_text", False):
			return

		base_height = dp(66)
		button._fitting_text = True
		try:
			button.height = base_height
			_fit_text_to_box(
				button,
				self.default_reveal_font_sp,
				self.min_reveal_font_sp,
				20,
				16,
				grow_height=True,
				guarded=False,
			)
		finally:
			button._fitting_text = False

	def refresh(self):
		app = App.get_running_app()
		item = app.get_current_study_item()
		if not item:
			app.show_message("단어 공부", "이번 학습 시퀀스가 완료되었습니다.")
			self.manager.current = "main"
			return

		progress = f"진행: {app.study_position + 1}/{len(app.study_sequence)}"
		self.word_label.text = item["word"]
		word_length = len(str(item["word"]))
		if word_length > 24:
			self.word_label.font_size = "22sp"
		elif word_length > 14:
			self.word_label.font_size = "28sp"
		else:
			self.word_label.font_size = "34sp"
		_fit_text_to_box(self.word_label, _font_sp_number(self.word_label.font_size, 34), 12, 16, 8, grow_height=False)
		self.status_label.text = f"{progress}  |  남은 연속 정답 {item['remaining']}회"
		self.meaning_button.height = dp(66)
		self.example_button.height = dp(66)
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
		root = BoxLayout(orientation="vertical", spacing=dp(14), padding=(dp(20), dp(22), dp(20), dp(18)))

		header = Label(
			text="단어장",
			font_size="27sp",
			bold=True,
			color=PALETTE["text"],
			halign="left",
			valign="middle",
			size_hint=(1, None),
			height=dp(46),
		)
		header.bind(size=lambda instance, _size: _wrap_label(instance, 2))
		root.add_widget(header)

		self.scroll = ScrollView(size_hint=(1, 1))
		self.list_container = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None)
		self.list_container.bind(minimum_height=self.list_container.setter("height"))
		self.scroll.add_widget(self.list_container)
		root.add_widget(self.scroll)

		back_btn = AppButton(text="뒤로", variant="secondary", size_hint=(1, None), height=dp(52), font_size="17sp")
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
				Label(
					text="아직 추가된 단어가 없습니다.",
					size_hint=(1, None),
					height=dp(48),
					font_size="16sp",
					color=PALETTE["muted"],
				)
			)
			return

		for idx, item in enumerate(app.vocabulary, start=1):
			example = str(item.get("example", "")).strip()

			item_box = Surface(
				orientation="vertical",
				spacing=dp(8),
				size_hint=(1, None),
				padding=(dp(14), dp(12), dp(14), dp(12)),
				border_color=PALETTE["border"],
				radius=14,
			)
			item_box.bind(minimum_height=item_box.setter("height"))

			word_label = Label(
				text=f"{idx}. {item['word']}",
				size_hint=(1, None),
				height=dp(30),
				font_size="19sp",
				bold=True,
				color=PALETTE["text"],
				halign="left",
				valign="middle",
			)
			word_label.max_font_sp = 19
			word_label.min_font_sp = 9
			word_label.bind(size=self._update_wrapped_list_label, text=self._update_wrapped_list_label)
			self._update_wrapped_list_label(word_label, word_label.size)

			meaning_label = Label(
				text=item["meaning"],
				size_hint=(1, None),
				font_size="15sp",
				color=PALETTE["text"],
				halign="left",
				valign="middle",
			)
			meaning_label.max_font_sp = 15
			meaning_label.min_font_sp = 9
			meaning_label.bind(size=self._update_wrapped_list_label, text=self._update_wrapped_list_label)
			self._update_wrapped_list_label(meaning_label, meaning_label.size)

			meta_label = Label(
				text=f"남은 연속 정답 {item.get('remaining', 5)}회",
				size_hint=(1, None),
				height=dp(24),
				font_size="13sp",
				color=PALETTE["muted"],
				halign="left",
				valign="middle",
			)
			meta_label.bind(size=lambda instance, _size: _wrap_label(instance, 2))

			item_box.add_widget(word_label)
			item_box.add_widget(meaning_label)
			if example:
				example_label = Label(
					text=f"예문: {example}",
					size_hint=(1, None),
					font_size="14sp",
					color=PALETTE["muted"],
					halign="left",
					valign="middle",
				)
				example_label.max_font_sp = 14
				example_label.min_font_sp = 9
				example_label.bind(size=self._update_wrapped_list_label, text=self._update_wrapped_list_label)
				self._update_wrapped_list_label(example_label, example_label.size)
				item_box.add_widget(example_label)
			item_box.add_widget(meta_label)

			delete_btn = AppButton(
				text="이 단어 삭제",
				variant="danger",
				size_hint=(1, None),
				height=dp(38),
				font_size="14sp",
			)
			delete_btn.bind(on_release=lambda _x, target=item: self._show_delete_confirm(target))

			item_box.add_widget(delete_btn)
			self.list_container.add_widget(item_box)

	def _go_home(self):
		self.manager.current = "main"

	def _update_wrapped_list_label(self, label, _size):
		if getattr(label, "_fitting_text", False):
			return
		max_font_sp = getattr(label, "max_font_sp", _font_sp_number(label.font_size, 15))
		min_font_sp = getattr(label, "min_font_sp", 9)
		label._fitting_text = True
		try:
			_fit_text_to_box(label, max_font_sp, min_font_sp, 8, 8, grow_height=True, guarded=False)
			label.height = max(dp(30), label.texture_size[1] + dp(8))
		finally:
			label._fitting_text = False

	def _show_delete_confirm(self, item):
		app = App.get_running_app()
		content = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(16))
		text = Label(
			text=f"'{item.get('word', '')}' 단어를 삭제할까요?",
			font_size="16sp",
			color=PALETTE["text"],
			halign="left",
			valign="middle",
		)
		text.bind(size=lambda instance, _size: _wrap_label(instance, 8))
		content.add_widget(text)

		btn_row = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint=(1, None), height=dp(46))
		cancel_btn = AppButton(text="취소", variant="secondary", height=dp(46), font_size="15sp")
		delete_btn = AppButton(text="삭제", variant="danger", height=dp(46), font_size="15sp")
		btn_row.add_widget(cancel_btn)
		btn_row.add_widget(delete_btn)
		content.add_widget(btn_row)

		popup = make_popup(title="단어 삭제", content=content, size_hint=(0.85, 0.35), auto_dismiss=False)

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
		self.openai_api_key = ""
		self.openai_model = OPENAI_MODEL
		self.last_openai_error = ""

	def build(self):
		configure_korean_font()
		Window.clearcolor = PALETTE["background"]
		self.data_file_path = self._resolve_data_file_path()
		self.load_openai_config()
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

	def _load_local_openai_api_key(self):
		key_file_path = os.path.join(os.path.dirname(__file__), LOCAL_OPENAI_API_KEY_FILE)
		try:
			with open(key_file_path, "r", encoding="utf-8") as file:
				return file.read().strip()
		except OSError:
			return ""

	def load_openai_config(self):
		self.openai_model = os.environ.get(OPENAI_MODEL_ENV, OPENAI_MODEL).strip() or OPENAI_MODEL

		env_api_key = os.environ.get(OPENAI_API_KEY_ENV, "").strip()
		self.openai_api_key = env_api_key or self._load_local_openai_api_key()

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
		message_label = Label(text=text, font_size="16sp", color=PALETTE["text"], halign="left", valign="middle")
		message_label.bind(size=lambda instance, _size: _fit_wrapped_label(instance, 96, 8, 8))
		content.add_widget(message_label)
		close_btn = AppButton(text="확인", variant="primary", size_hint=(1, None), height=dp(48), font_size="16sp")
		content.add_widget(close_btn)

		popup = make_popup(title=title, content=content, size_hint=(0.85, 0.45), auto_dismiss=False)
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
		content.add_widget(Label(text="아래 코드를 안전한 곳에 저장하세요.", size_hint=(1, None), height=dp(28), font_size="15sp", color=PALETTE["text"]))

		code_input = TextInput(
			text=backup_code,
			readonly=True,
			multiline=True,
			size_hint=(1, 1),
			font_size="13sp",
		)
		style_text_input(code_input)
		code_input.background_color = PALETTE["surface_alt"]
		content.add_widget(code_input)

		button_row = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint=(1, None), height=dp(48))
		copy_btn = AppButton(text="코드 복사", variant="primary", height=dp(48), font_size="15sp")
		close_btn = AppButton(text="닫기", variant="secondary", height=dp(48), font_size="15sp")
		button_row.add_widget(copy_btn)
		button_row.add_widget(close_btn)
		content.add_widget(button_row)

		popup = make_popup(title="백업 코드", content=content, size_hint=(0.92, 0.7), auto_dismiss=False)

		def _copy_code(_instance):
			Clipboard.copy(backup_code)
			self.show_message("복사 완료", "백업 코드를 클립보드에 복사했습니다.")

		copy_btn.bind(on_release=_copy_code)
		close_btn.bind(on_release=popup.dismiss)
		popup.open()

	def show_restore_code_popup(self):
		content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(14))
		content.add_widget(Label(text="저장해둔 백업 코드를 붙여넣으세요.", size_hint=(1, None), height=dp(28), font_size="15sp", color=PALETTE["text"]))

		code_input = TextInput(
			text="",
			multiline=True,
			size_hint=(1, 1),
			font_size="13sp",
		)
		style_text_input(code_input)
		code_input.background_color = PALETTE["surface_alt"]
		content.add_widget(code_input)

		button_row = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint=(1, None), height=dp(48))
		restore_btn = AppButton(text="복원 실행", variant="primary", height=dp(48), font_size="15sp")
		cancel_btn = AppButton(text="취소", variant="secondary", height=dp(48), font_size="15sp")
		button_row.add_widget(restore_btn)
		button_row.add_widget(cancel_btn)
		content.add_widget(button_row)

		popup = make_popup(title="백업 코드 복원", content=content, size_hint=(0.92, 0.7), auto_dismiss=False)

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

	def _extract_openai_text(self, result):
		direct_text = result.get("output_text")
		if isinstance(direct_text, str) and direct_text.strip():
			return direct_text.strip()

		text_parts = []
		output_items = result.get("output", [])
		if not isinstance(output_items, list):
			return ""

		for output_item in output_items:
			if not isinstance(output_item, dict):
				continue

			content_items = output_item.get("content", [])
			if isinstance(content_items, list):
				for content_item in content_items:
					if not isinstance(content_item, dict):
						continue
					text = content_item.get("text")
					if isinstance(text, str) and text.strip():
						text_parts.append(text.strip())

			text = output_item.get("text")
			if isinstance(text, str) and text.strip():
				text_parts.append(text.strip())

		return " ".join(text_parts).strip()

	def _clean_example_sentence(self, text):
		cleaned = str(text or "").replace("\n", " ").strip()
		cleaned = cleaned.strip('"').strip("'").strip()

		while cleaned.startswith(("-", "*", "•")):
			cleaned = cleaned[1:].strip()

		prefixes = ("example:", "sentence:", "예문:")
		lowered = cleaned.lower()
		for prefix in prefixes:
			if lowered.startswith(prefix):
				cleaned = cleaned[len(prefix):].strip()
				break

		return cleaned.strip('"').strip("'").strip()

	def generate_example_with_openai(self, word, meaning):
		self.last_openai_error = ""
		if not self.openai_api_key:
			self.last_openai_error = "GPT API 키가 설정되어 있지 않습니다."
			return ""

		instructions = (
			"You are a professional English vocabulary tutor. "
			"Write exactly ONE natural and practical English example sentence using the target word. "
			"CRITICAL RULES:\n"
			"1. The sentence MUST reflect the provided Korean meaning; this is important for words with multiple meanings.\n"
			"2. Use only widely known words and basic grammar that a high school graduate should understand.\n"
			"3. Keep the sentence clear and simple. Avoid advanced or rare words, idioms, and complex clauses.\n"
			"4. Output ONLY the raw sentence. No quotes, no translations, no explanations, no conversational filler."
		)

		payload = {
			"model": self.openai_model or OPENAI_MODEL,
			"instructions": instructions,
			"input": f"Target word: {word}\nKorean meaning: {meaning}",
			"temperature": 0.7,
			"max_output_tokens": 80,
			"store": False,
		}

		request = urllib.request.Request(
			"https://api.openai.com/v1/responses",
			data=json.dumps(payload).encode("utf-8"),
			headers={
				"Authorization": f"Bearer {self.openai_api_key}",
				"Content-Type": "application/json",
			},
			method="POST",
		)

		ssl_context = self._build_ssl_context()

		try:
			with urllib.request.urlopen(request, timeout=15, context=ssl_context) as response:
				result = json.loads(response.read().decode("utf-8"))
		except urllib.error.HTTPError as http_error:
			try:
				error_body = http_error.read().decode("utf-8", errors="ignore")
				error_data = json.loads(error_body) if error_body else {}
			except Exception:
				error_body = ""
				error_data = {}

			message = ""
			if isinstance(error_data, dict):
				error_info = error_data.get("error")
				if isinstance(error_info, dict):
					message = str(error_info.get("message", "")).strip()

			self.last_openai_error = f"HTTP {http_error.code}"
			if message:
				self.last_openai_error += f" | {message[:140]}"
			elif error_body:
				self.last_openai_error += f" | {error_body[:140]}"
			return ""
		except (urllib.error.URLError, TimeoutError, OSError, ValueError):
			self.last_openai_error = "네트워크/SSL 연결 실패"
			return ""

		error_info = result.get("error")
		if isinstance(error_info, dict):
			code = str(error_info.get("code", "")).strip()
			message = str(error_info.get("message", "")).strip()
			self.last_openai_error = code or "API 오류"
			if message:
				self.last_openai_error += f" | {message[:140]}"
			return ""

		text = self._clean_example_sentence(self._extract_openai_text(result))
		if not text:
			self.last_openai_error = "응답 문장이 비어 있습니다."
			return ""

		return text


if __name__ == "__main__":
	configure_korean_font()
	VocabularyApp().run()
