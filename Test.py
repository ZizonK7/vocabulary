import json
import os
import tkinter as tk
from tkinter import messagebox


class VocabularyApp(tk.Tk):
	def __init__(self):
		super().__init__()

		self.title("단어장")
		self.configure(bg="#0f172a")
		self.geometry("420x760")
		self.minsize(360, 640)
		self.vocabulary = []
		self.add_word_window = None
		self.study_window = None
		self.word_entry = None
		self.meaning_entry = None
		self.study_word_label = None
		self.study_status_label = None
		self.meaning_reveal_box = None
		self.study_hint_label = None
		self.study_sequence = []
		self.study_position = 0
		self.data_file_path = os.path.join(os.path.dirname(__file__), "vocabulary_data.json")

		self._load_vocabulary_data()

		self._build_ui()

	def _load_vocabulary_data(self):
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
				remaining = item.get("remaining", 5)

				if not word or not meaning:
					continue

				if not isinstance(remaining, int):
					remaining = 5
				remaining = max(0, min(5, remaining))

				loaded_items.append(
					{"word": word, "meaning": meaning, "remaining": remaining}
				)

			self.vocabulary = loaded_items
		except Exception:
			self.vocabulary = []

	def _save_vocabulary_data(self):
		serializable_items = []
		for item in self.vocabulary:
			serializable_items.append(
				{
					"word": item.get("word", ""),
					"meaning": item.get("meaning", ""),
					"remaining": int(item.get("remaining", 5)),
				}
			)

		with open(self.data_file_path, "w", encoding="utf-8") as file:
			json.dump(serializable_items, file, ensure_ascii=False, indent=2)

	def _build_ui(self):
		outer = tk.Frame(self, bg="#0f172a")
		outer.pack(fill="both", expand=True, padx=18, pady=18)

		phone = tk.Frame(outer, bg="#111827", bd=0, highlightthickness=0)
		phone.pack(fill="both", expand=True)

		top_bar = tk.Frame(phone, bg="#111827")
		top_bar.pack(fill="x", padx=22, pady=(22, 8))

		tk.Label(
			top_bar,
			text="단어장",
			fg="#f8fafc",
			bg="#111827",
			font=("Malgun Gothic", 26, "bold"),
		).pack(anchor="w")

		tk.Label(
			top_bar,
			text="오늘의 단어를 가볍게 시작하세요.",
			fg="#cbd5e1",
			bg="#111827",
			font=("Malgun Gothic", 11),
		).pack(anchor="w", pady=(6, 0))

		hero = tk.Frame(phone, bg="#1e293b", highlightbackground="#334155", highlightthickness=1)
		hero.pack(fill="x", padx=22, pady=18)

		tk.Label(
			hero,
			text="단어를 추가하고\n바로 공부할 수 있는\n간단한 시작 화면",
			fg="#f8fafc",
			bg="#1e293b",
			justify="left",
			font=("Malgun Gothic", 18, "bold"),
		).pack(anchor="w", padx=20, pady=(18, 8))

		tk.Label(
			hero,
			text="아래 버튼으로 단어를 등록하거나 복습을 시작하세요.",
			fg="#cbd5e1",
			bg="#1e293b",
			justify="left",
			font=("Malgun Gothic", 10),
		).pack(anchor="w", padx=20, pady=(0, 18))

		button_area = tk.Frame(phone, bg="#111827")
		button_area.pack(fill="both", expand=True, padx=22, pady=(0, 22))

		self._make_action_button(
			button_area,
			title="단어 추가하기",
			subtitle="새로운 단어를 저장합니다.",
			bg="#2563eb",
			command=self.add_word,
		).pack(fill="x", pady=(0, 14))

		self._make_action_button(
			button_area,
			title="단어 공부하기",
			subtitle="저장한 단어를 복습합니다.",
			bg="#0f766e",
			command=self.study_words,
		).pack(fill="x", pady=(0, 14))

		self._make_action_button(
			button_area,
			title="단어장 확인하기",
			subtitle="저장된 단어 목록을 확인합니다.",
			bg="#7c3aed",
			command=self.show_vocabulary,
		).pack(fill="x")

		footer = tk.Label(
			phone,
			text="v0.1",
			fg="#64748b",
			bg="#111827",
			font=("Malgun Gothic", 9),
		)
		footer.pack(side="bottom", pady=14)

	def _make_action_button(self, parent, title, subtitle, bg, command):
		card = tk.Frame(parent, bg=bg, highlightbackground="#ffffff", highlightthickness=0)
		card.configure(cursor="hand2")

		title_label = tk.Label(
			card,
			text=title,
			fg="#ffffff",
			bg=bg,
			font=("Malgun Gothic", 18, "bold"),
		)
		title_label.pack(anchor="w", padx=18, pady=(16, 2))

		subtitle_label = tk.Label(
			card,
			text=subtitle,
			fg="#e2e8f0",
			bg=bg,
			font=("Malgun Gothic", 10),
		)
		subtitle_label.pack(anchor="w", padx=18, pady=(0, 16))

		def bind_click(widget):
			widget.bind("<Button-1>", lambda _event: command())
			widget.bind("<Enter>", lambda _event: widget.configure(relief="raised"))
			widget.bind("<Leave>", lambda _event: widget.configure(relief="flat"))

		for widget in (card, title_label, subtitle_label):
			bind_click(widget)

		card.configure(relief="flat", bd=0)
		return card

	def add_word(self):
		if self.add_word_window and self.add_word_window.winfo_exists():
			self.add_word_window.lift()
			self.add_word_window.focus_force()
			return

		self.add_word_window = tk.Toplevel(self)
		self.add_word_window.title("단어 추가하기")
		self.add_word_window.geometry("380x360")
		self.add_word_window.configure(bg="#0f172a")
		self.add_word_window.resizable(False, False)

		frame = tk.Frame(self.add_word_window, bg="#111827")
		frame.pack(fill="both", expand=True, padx=16, pady=16)

		tk.Label(
			frame,
			text="새 단어 등록",
			fg="#f8fafc",
			bg="#111827",
			font=("Malgun Gothic", 18, "bold"),
		).pack(anchor="w", padx=14, pady=(14, 10))

		tk.Label(
			frame,
			text="단어",
			fg="#cbd5e1",
			bg="#111827",
			font=("Malgun Gothic", 10),
		).pack(anchor="w", padx=14)

		self.word_entry = tk.Entry(
			frame,
			font=("Malgun Gothic", 11),
			relief="flat",
			bg="#e2e8f0",
			fg="#0f172a",
		)
		self.word_entry.pack(fill="x", padx=14, pady=(4, 12), ipady=8)

		tk.Label(
			frame,
			text="뜻",
			fg="#cbd5e1",
			bg="#111827",
			font=("Malgun Gothic", 10),
		).pack(anchor="w", padx=14)

		self.meaning_entry = tk.Entry(
			frame,
			font=("Malgun Gothic", 11),
			relief="flat",
			bg="#e2e8f0",
			fg="#0f172a",
		)
		self.meaning_entry.pack(fill="x", padx=14, pady=(4, 18), ipady=8)

		tk.Button(
			frame,
			text="단어 추가하기",
			font=("Malgun Gothic", 11, "bold"),
			bg="#2563eb",
			fg="#ffffff",
			activebackground="#1d4ed8",
			activeforeground="#ffffff",
			relief="flat",
			command=self.save_word,
		).pack(fill="x", padx=14, ipady=8)

		self.word_entry.focus_set()

	def save_word(self):
		if not self.word_entry or not self.meaning_entry:
			return

		word = self.word_entry.get().strip()
		meaning = self.meaning_entry.get().strip()

		if not word or not meaning:
			messagebox.showwarning("입력 확인", "단어와 뜻을 모두 입력해주세요.")
			return

		# 리스트 맨 뒤에 단어를 순서대로 추가합니다.
		self.vocabulary.append({"word": word, "meaning": meaning, "remaining": 5})
		self._save_vocabulary_data()

		messagebox.showinfo("저장 완료", f"'{word}' 단어가 단어장에 추가되었습니다.")

		# 한 번에 한 단어만 입력하도록 저장 후 창을 닫습니다.
		if self.add_word_window and self.add_word_window.winfo_exists():
			self.add_word_window.destroy()
		self.add_word_window = None
		self.word_entry = None
		self.meaning_entry = None

	def show_vocabulary(self):
		if not self.vocabulary:
			messagebox.showinfo("단어장", "아직 추가된 단어가 없습니다.")
			return

		lines = []
		for idx, item in enumerate(self.vocabulary, start=1):
			lines.append(f"{idx}. {item['word']} - {item['meaning']}")

		messagebox.showinfo("단어장 확인", "\n".join(lines))

	def study_words(self):
		if not self.vocabulary:
			messagebox.showinfo("단어 공부하기", "공부할 단어가 없습니다. 먼저 단어를 추가해주세요.")
			return

		if self.study_window and self.study_window.winfo_exists():
			self.study_window.lift()
			self.study_window.focus_force()
			self._refresh_study_view()
			return

		# 이번 학습 세션은 현재 단어장을 최근 추가 순(뒤에서 앞으로)으로 각 1회씩만 진행합니다.
		self.study_sequence = list(reversed(self.vocabulary.copy()))
		self.study_position = 0

		self.study_window = tk.Toplevel(self)
		self.study_window.title("단어 공부하기")
		self.study_window.geometry("400x470")
		self.study_window.configure(bg="#0f172a")
		self.study_window.resizable(False, False)
		self.study_window.protocol("WM_DELETE_WINDOW", self._close_study_window)

		frame = tk.Frame(self.study_window, bg="#111827")
		frame.pack(fill="both", expand=True, padx=16, pady=16)

		tk.Label(
			frame,
			text="단어 공부",
			fg="#f8fafc",
			bg="#111827",
			font=("Malgun Gothic", 18, "bold"),
		).pack(anchor="w", padx=16, pady=(14, 8))

		self.study_word_label = tk.Label(
			frame,
			text="",
			fg="#ffffff",
			bg="#2563eb",
			font=("Malgun Gothic", 20, "bold"),
			pady=14,
		)
		self.study_word_label.pack(fill="x", padx=16, pady=(2, 10))

		self.study_status_label = tk.Label(
			frame,
			text="",
			fg="#cbd5e1",
			bg="#111827",
			font=("Malgun Gothic", 10),
		)
		self.study_status_label.pack(anchor="w", padx=16, pady=(0, 8))

		self.meaning_reveal_box = tk.Label(
			frame,
			text="뜻 보기 (클릭)",
			fg="#0f172a",
			bg="#e2e8f0",
			font=("Malgun Gothic", 12, "bold"),
			relief="flat",
			cursor="hand2",
			pady=18,
		)
		self.meaning_reveal_box.pack(fill="x", padx=16, pady=(0, 8))
		self.meaning_reveal_box.bind("<Button-1>", self._reveal_meaning)

		self.study_hint_label = tk.Label(
			frame,
			text="단어 뜻을 떠올린 뒤 위 박스를 눌러 확인하세요.",
			fg="#94a3b8",
			bg="#111827",
			font=("Malgun Gothic", 9),
		)
		self.study_hint_label.pack(anchor="w", padx=16, pady=(0, 16))

		button_row = tk.Frame(frame, bg="#111827")
		button_row.pack(fill="x", padx=16, pady=(0, 10))

		tk.Button(
			button_row,
			text="O",
			font=("Malgun Gothic", 13, "bold"),
			bg="#16a34a",
			fg="#ffffff",
			activebackground="#15803d",
			activeforeground="#ffffff",
			relief="flat",
			command=self._mark_correct,
		).pack(side="left", fill="x", expand=True, ipady=10, padx=(0, 6))

		tk.Button(
			button_row,
			text="X",
			font=("Malgun Gothic", 13, "bold"),
			bg="#dc2626",
			fg="#ffffff",
			activebackground="#b91c1c",
			activeforeground="#ffffff",
			relief="flat",
			command=self._mark_incorrect,
		).pack(side="left", fill="x", expand=True, ipady=10, padx=(6, 0))

		self._refresh_study_view()

	def _close_study_window(self):
		if self.study_window and self.study_window.winfo_exists():
			self.study_window.destroy()
		self.study_window = None
		self.study_sequence = []
		self.study_position = 0

	def _get_current_word_item(self):
		if not self.vocabulary or not self.study_sequence:
			return None

		while self.study_position < len(self.study_sequence):
			item = self.study_sequence[self.study_position]
			if item in self.vocabulary:
				if "remaining" not in item:
					# 이전 데이터 호환: remaining 값이 없으면 기본 5회로 설정.
					item["remaining"] = 5
				return item
			self.study_position += 1

		return None

	def _move_to_next_word(self):
		self.study_position += 1

	def _refresh_study_view(self):
		item = self._get_current_word_item()
		if not item:
			if self.study_window and self.study_window.winfo_exists():
				messagebox.showinfo("단어 공부하기", "이번 학습 시퀀스가 완료되었습니다.")
				self._close_study_window()
			return

		if self.study_word_label:
			self.study_word_label.configure(text=item["word"])
		if self.study_status_label:
			progress = f"진행: {self.study_position + 1}/{len(self.study_sequence)}"
			self.study_status_label.configure(
				text=f"{progress} | 남은 연속 정답: {item['remaining']}회 (0회가 되면 완료)")
		if self.meaning_reveal_box:
			self.meaning_reveal_box.configure(text="뜻 보기 (클릭)", bg="#e2e8f0", fg="#0f172a")

	def _reveal_meaning(self, _event=None):
		item = self._get_current_word_item()
		if not item or not self.meaning_reveal_box:
			return
		self.meaning_reveal_box.configure(text=item["meaning"], bg="#bae6fd", fg="#0c4a6e")

	def _mark_correct(self):
		item = self._get_current_word_item()
		if not item:
			return

		item["remaining"] -= 1

		if item["remaining"] <= 0:
			mastered_word = item["word"]
			self.vocabulary.remove(item)

			messagebox.showinfo("학습 완료", f"{mastered_word}를 완전히 숙지하셨습니다!")

		self._save_vocabulary_data()

		self._move_to_next_word()

		self._refresh_study_view()

	def _mark_incorrect(self):
		item = self._get_current_word_item()
		if not item:
			return

		item["remaining"] = 5
		self._save_vocabulary_data()
		self._move_to_next_word()
		self._refresh_study_view()


if __name__ == "__main__":
	app = VocabularyApp()
	app.mainloop()
