import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from dataclasses import dataclass, field
import re
import sys
import ctypes
import webbrowser
import json
import os

import customtkinter as ctk
import pyperclip
from PIL import Image, ImageDraw, ImageFont, ImageTk, ImageOps


ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("green")


@dataclass
class DocumentState:
    frame: tk.Frame
    text: tk.Text
    file_path: str | None = None
    is_modified: bool = False
    suspend_change_events: bool = False
    syntax_after_id: str | None = None
    last_highlight_source: str = ""
    emoji_map: dict[str, str] = field(default_factory=dict)
    emoji_counter: int = 0
    interactive_ranges: list[tuple[str, str, str, str]] = field(default_factory=list)
    stats_after_id: str | None = None
    message_cache: str = ""
    message_cache_dirty: bool = True


class WhatsAppEditor(ctk.CTk):
    SYNTAX_HIGHLIGHT_DELAY_MS = 140
    STATS_REFRESH_DELAY_MS = 90

    def __init__(self):
        super().__init__()

        self.title("Editor Texto WhatsApp Pro")
        self.geometry("1280x980")
        self._set_windows_app_id()

        icon_path = self._resource_path("icon2.ico")
        if icon_path.exists():
            self.iconbitmap(str(icon_path))

        self.emoji_cache = {}
        self.emoji_image_cache = {}
        self._close_tab_pressed: int | None = None
        self._close_tab_images: dict[str, ImageTk.PhotoImage] = {}
        self._is_closing = False
        self._setup_notebook_style()

        self.documents: list[DocumentState] = []
        self.doc_by_text: dict[tk.Text, DocumentState] = {}
        self.doc_by_frame: dict[tk.Frame, DocumentState] = {}

        self._pattern_specs = [
            ("bold", re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)"), 1),
            ("italic", re.compile(r"_([^_\n][^_\n]*?)_"), 1),
            ("strike", re.compile(r"~([^~\n][^~\n]*?)~"), 1),
            ("inline_code", re.compile(r"`([^`\n]+)`"), 1),
            ("code_block", re.compile(r"```([\s\S]*?)```"), 1),
        ]

        self._smart_specs = [
            ("link", re.compile(r"https?://[^\s<>()\[\]{}\"']+"), "link"),
            ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "email"),
            ("phone", re.compile(r"(?<!\w)(?:\+?\d[\d\s\-().]{6,}\d)(?!\w)"), "phone"),
            (
                "datetime",
                re.compile(r"\b(?:hoy|manana|mañana|pasado manana|pasado mañana|\d{1,2}:\d{2}|\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)\b", re.IGNORECASE),
                "datetime",
            ),
        ]

        default_emoji_font = Path("C:/Windows/Fonts/seguiemj.ttf")
        self.emoji_font_path = str(default_emoji_font) if default_emoji_font.exists() else None
        self.emoji_categories = {
            "Noticias": ["🏛️", "📰", "🗞️", "🗣️", "📺", "📻", "🎙️", "🗳️", "⚖️", "📢"],
            "Alertas": ["✅", "✔️", "🆗", "🚨", "⚠️", "🔥", "❗", "⭕", "❌", "✖️", "🚫", "💯"],
            "Datos": ["📑", "📊", "📈", "📉", "📝", "📁", "📂", "💼", "🏢", "💻", "📧", "📌"],
            "Marcadores": ["🔺", "🔻", "➡", "⬅", "⬆", "⬇", "▶", "◀", "👉", "👈", "📍", "🚩", "🔔"],
            "Colores": ["🟢", "🔴", "🟡", "⚪", "⚫", "🔵", "🟣", "🟠", "💎", "⭐", "🌟"],
            "Varios": ["💰", "💵", "💸", "⌛", "⏳", "⏰", "📆", "📅", "🔎", "🔍", "🛒", "📦", "📱", "🎥"],
        }

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.grid_columnconfigure(0, minsize=290)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.toolbar = ctk.CTkFrame(
            self,
            height=84,
            corner_radius=0,
            fg_color="#F0F2F5",
            border_width=1,
            border_color="#D1D1D1",
        )
        self.toolbar.grid(row=0, column=0, columnspan=2, sticky="nsew")

        self.tools_container = ctk.CTkFrame(self.toolbar, fg_color="transparent")
        self.tools_container.pack(pady=15, padx=20, fill="x")

        self.create_menu_button(
            self.tools_container,
            "Archivo",
            [
                ("Abrir .md/.txt", self.open_file),
                ("Guardar", self.save_file),
                ("Guardar como", self.save_file_as),
                ("Cerrar pestaña", self.close_current_tab),
                ("Nueva pestaña", self.new_file),
            ],
        )

        self.edit_menu_btn = self.create_menu_button(
            self.tools_container,
            "Editar",
            [
                ("Deshacer (Ctrl+Z)", self.undo_action),
                ("Rehacer (Ctrl+Y)", self.redo_action),
                ("Buscar y Reemplazar (Ctrl+F)", self.open_find_replace),
                ("Titulo", self.insert_title),
                ("Lista con viñetas", self.insert_list),
                ("Lista numerada", self.insert_numbered_list),
                ("Cita de bloque", self.insert_quote),
                ("Codigo inline", lambda: self.apply_format("`")),
                ("Bloque de codigo", self.insert_code_block),
                ("Caracter invisible", self.insert_invisible_char),
                ("Combo de emojis", self.insert_emoji_combo),
            ],
        )

        self.create_menu_button(
            self.tools_container,
            "Vista",
            [
                ("Modo Claro", lambda: self.change_appearance("Light")),
                ("Modo Oscuro", lambda: self.change_appearance("Dark")),
                ("Zoom + (Ctrl+)", lambda: self.change_zoom(1)),
                ("Zoom - (Ctrl-)", lambda: self.change_zoom(-1)),
            ],
        )
        self._edit_emojis_injected = False
        self.emojis_menu_btn = self.create_emoji_menu_button(self.tools_container, "Emojis")
        self.emojis_menu_btn.pack_forget()

        self.create_tool_btn(
            self.tools_container,
            "B",
            lambda: self.apply_format("*"),
            font_style=("Segoe UI", 13, "bold"),
            width=42,
        )
        self.create_tool_btn(
            self.tools_container,
            "I",
            lambda: self.apply_format("_"),
            font_style=("Segoe UI", 13, "italic"),
            width=42,
        )
        self.create_tool_btn(
            self.tools_container,
            "U",
            lambda: self.apply_format("~"),
            font_style=("Segoe UI", 13, "underline"),
            width=42,
        )
        self.create_tool_btn(
            self.tools_container,
            "\u21b6",
            self.undo_action,
            width=42,
        )
        self.create_tool_btn(
            self.tools_container,
            "\u21b7",
            self.redo_action,
            width=42,
        )
        self.quick_title_btn = self.create_tool_btn(self.tools_container, "H1", self.insert_title, width=38)
        self.quick_quote_btn = self.create_tool_btn(self.tools_container, ">", self.insert_quote, width=34)
        self.quick_list_btn = self.create_tool_btn(self.tools_container, "Li", self.insert_list, width=36)
        self.quick_title_btn.pack_forget()
        self.quick_quote_btn.pack_forget()
        self.quick_list_btn.pack_forget()

        self.btn_copy_top = ctk.CTkButton(
            self.tools_container,
            text="🚀 COPIAR PARA WHATSAPP",
            fg_color="#25D366",
            hover_color="#128C7E",
            text_color="white",
            width=220,
            height=40,
            font=("Segoe UI", 12, "bold"),
            command=self.export_to_whatsapp,
        )
        self.btn_copy_top.pack(side="right", padx=10)

        self.sidebar = ctk.CTkFrame(
            self,
            width=290,
            corner_radius=0,
            fg_color="#FFFFFF",
            border_width=1,
            border_color="#D1D1D1",
        )
        self.sidebar.grid(row=1, column=0, sticky="nsew")

        ctk.CTkLabel(
            self.sidebar,
            text="EMOJIS A COLOR",
            font=("Segoe UI", 12, "bold"),
            text_color="#075E54",
        ).pack(pady=16)
        self.emoji_scroll = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.emoji_scroll.pack(fill="both", expand=True, padx=20, pady=10)

        self.create_emoji_panel_premium()

        self.editor_bg = ctk.CTkFrame(self, fg_color="#E5DDD5", corner_radius=0)
        self.editor_bg.grid(row=1, column=1, sticky="nsew")

        self.sheet_shadow = ctk.CTkFrame(self.editor_bg, fg_color="#D1D1D1", corner_radius=15)
        self.sheet_shadow.pack(pady=40, padx=60, fill="both", expand=True)

        self.paper = ctk.CTkFrame(self.sheet_shadow, fg_color="white", corner_radius=15)
        self.paper.place(relx=0.5, rely=0.5, relwidth=0.99, relheight=0.99, anchor="center")

        self.notebook = ttk.Notebook(self.paper, style="ClosableNotebook.TNotebook")
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)
        self.notebook.bind("<ButtonPress-1>", self.on_notebook_button_press, add=True)
        self.notebook.bind("<ButtonRelease-1>", self.on_notebook_button_release, add=True)
        self.notebook.bind("<ButtonRelease-2>", self.on_notebook_middle_click, add=True)
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        self.status = ctk.CTkFrame(self, height=34, fg_color="#F0F2F5")
        self.status.grid(row=2, column=0, columnspan=2, sticky="nsew")
        self.lbl_stats = ctk.CTkLabel(self.status, text="Listo...", font=("Segoe UI", 11))
        self.lbl_stats.pack(side="left", padx=20)
        self.lbl_limit = ctk.CTkLabel(self.status, text="", font=("Segoe UI", 11, "bold"))
        self.lbl_limit.pack(side="left", padx=10)
        self.lbl_hint = ctk.CTkLabel(self.status, text="Tip: Ctrl+Click en enlace/correo para abrir", font=("Segoe UI", 10), text_color="#666")
        self.lbl_hint.pack(side="right", padx=20)

        self.session_file = Path(os.getenv("APPDATA", os.path.expanduser("~"))) / ".whatsapp_editor_session.json"

        self.bind("<Configure>", self.on_window_resize)
        self.bind("<Control-f>", self.open_find_replace)
        
        if not self.load_session():
            self.new_file()

    @staticmethod
    def _resource_path(filename: str) -> Path:
        if hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS) / filename
        return Path(__file__).resolve().parent / filename

    @staticmethod
    def _set_windows_app_id():
        if sys.platform != "win32":
            return
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("EditorWhatsapp.Pro")
        except Exception:
            pass

    def _create_tab_close_image(self, line_color: str, bg_color: str | None = None) -> ImageTk.PhotoImage:
        image = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        if bg_color:
            draw.rounded_rectangle((1, 1, 15, 15), radius=7, fill=bg_color)
        draw.line((5, 5, 11, 11), fill=line_color, width=2)
        draw.line((11, 5, 5, 11), fill=line_color, width=2)
        return ImageTk.PhotoImage(image)

    def _setup_notebook_style(self):
        style = ttk.Style(self)
        self._close_tab_images = {
            "normal": self._create_tab_close_image("#6B7280"),
            "active": self._create_tab_close_image("#FFFFFF", "#E74C3C"),
            "pressed": self._create_tab_close_image("#FFFFFF", "#C0392B"),
        }
        try:
            style.element_create(
                "ClosableNotebook.close",
                "image",
                self._close_tab_images["normal"],
                ("active", self._close_tab_images["active"]),
                ("pressed", self._close_tab_images["pressed"]),
                border=4,
                sticky="",
            )
        except tk.TclError:
            pass

        style.layout("ClosableNotebook.TNotebook", style.layout("TNotebook"))
        style.configure("ClosableNotebook.TNotebook", tabmargins=(10, 8, 10, 0))
        style.layout(
            "ClosableNotebook.TNotebook.Tab",
            [
                (
                    "ClosableNotebook.tab",
                    {
                        "sticky": "nswe",
                        "children": [
                            (
                                "ClosableNotebook.padding",
                                {
                                    "side": "top",
                                    "sticky": "nswe",
                                    "children": [
                                        (
                                            "ClosableNotebook.focus",
                                            {
                                                "side": "top",
                                                "sticky": "nswe",
                                                "children": [
                                                    ("ClosableNotebook.label", {"side": "left", "sticky": ""}),
                                                    ("ClosableNotebook.close", {"side": "left", "sticky": ""}),
                                                ],
                                            },
                                        )
                                    ],
                                },
                            )
                        ],
                    },
                )
            ],
        )
        style.configure("ClosableNotebook.TNotebook.Tab", padding=(14, 8, 10, 8))

    def _is_emoji_char(self, char: str) -> bool:
        if not char:
            return False
        cp = ord(char)
        emoji_ranges = (
            (0x1F300, 0x1FAFF),
            (0x2600, 0x27BF),
            (0x1F1E6, 0x1F1FF),
        )
        return any(start <= cp <= end for start, end in emoji_ranges)

    @staticmethod
    def _is_emoji_component(char: str) -> bool:
        if not char:
            return False
        cp = ord(char)
        return (
            cp == 0x200D  # ZWJ
            or cp == 0x20E3  # Keycap
            or 0xFE00 <= cp <= 0xFE0F  # Variation selectors
            or 0x1F3FB <= cp <= 0x1F3FF  # Skin tone modifiers
            or 0xE0020 <= cp <= 0xE007F  # Tag modifiers
        )

    @staticmethod
    def _is_regional_indicator(char: str) -> bool:
        if not char:
            return False
        cp = ord(char)
        return 0x1F1E6 <= cp <= 0x1F1FF

    @staticmethod
    def _is_keycap_base(char: str) -> bool:
        return char in "0123456789#*"

    def _consume_emoji_sequence(self, text: str, start: int) -> tuple[str, int]:
        i = start
        n = len(text)
        i += 1

        # Banderas: par de indicadores regionales.
        if self._is_regional_indicator(text[start]) and i < n and self._is_regional_indicator(text[i]):
            i += 1

        while i < n:
            ch = text[i]
            if self._is_emoji_component(ch):
                i += 1
                # Si hay ZWJ, consumir el siguiente emoji base si existe.
                if ord(ch) == 0x200D and i < n and self._is_emoji_char(text[i]):
                    i += 1
                continue
            break
        return text[start:i], i

    def _consume_keycap_sequence(self, text: str, start: int) -> tuple[str, int] | None:
        n = len(text)
        if start >= n or not self._is_keycap_base(text[start]):
            return None
        i = start + 1
        if i < n and ord(text[i]) == 0xFE0F:
            i += 1
        if i < n and ord(text[i]) == 0x20E3:
            i += 1
            return text[start:i], i
        return None

    def current_doc(self) -> DocumentState | None:
        tabs = self.notebook.tabs()
        if not tabs:
            return None
        current = self.notebook.select()
        if not current:
            return None
        frame = self.nametowidget(current)
        return self.doc_by_frame.get(frame)

    def update_tab_title(self, doc: DocumentState):
        base = Path(doc.file_path).name if doc.file_path else "Sin titulo"
        if doc.is_modified:
            base = f"* {base}"
        self.notebook.tab(doc.frame, text=base)

    def _tab_index_from_coordinates(self, x: int, y: int) -> int | None:
        try:
            return self.notebook.index(f"@{x},{y}")
        except tk.TclError:
            return None

    def on_notebook_button_press(self, event):
        element = self.notebook.identify(event.x, event.y)
        if "close" not in element:
            self._close_tab_pressed = None
            return None
        self._close_tab_pressed = self._tab_index_from_coordinates(event.x, event.y)
        return "break"

    def on_notebook_button_release(self, event):
        element = self.notebook.identify(event.x, event.y)
        tab_index = self._tab_index_from_coordinates(event.x, event.y)
        pressed_index = self._close_tab_pressed
        self._close_tab_pressed = None
        if pressed_index is None or tab_index != pressed_index or "close" not in element:
            return None

        self._close_tab_by_index(tab_index)
        return "break"

    def _close_tab_by_index(self, tab_index: int | None):
        if tab_index is None:
            return
        tabs = self.notebook.tabs()
        if not (0 <= tab_index < len(tabs)):
            return
        frame = self.nametowidget(tabs[tab_index])
        self.notebook.select(frame)
        self.close_current_tab()

    def on_notebook_middle_click(self, event):
        if "label" not in self.notebook.identify(event.x, event.y):
            return None
        self._close_tab_by_index(self._tab_index_from_coordinates(event.x, event.y))
        return "break"

    def create_document_tab(self, title: str = "Sin titulo", content: str = "", file_path: str | None = None):
        frame = tk.Frame(self.notebook, bg="white")
        text = tk.Text(
            frame,
            font=("Segoe UI", 13),
            wrap="word",
            undo=True,
            bg="white",
            fg="#000000",
            padx=40,
            pady=40,
            borderwidth=0,
            highlightthickness=0,
            insertbackground="#25D366",
        )
        text.pack(fill="both", expand=True)

        text.tag_configure("bold", font=("Segoe UI", 13, "bold"))
        text.tag_configure("italic", font=("Segoe UI", 13, "italic"))
        text.tag_configure("strike", font=("Segoe UI", 13, "overstrike"))
        text.tag_configure("inline_code", font=("Consolas", 12), background="#F5F5F5")
        text.tag_configure("code_block", font=("Consolas", 12), background="#F0F3F5")
        text.tag_configure("quote", foreground="#555", lmargin1=22, lmargin2=22)
        text.tag_configure("bullet", foreground="#333")
        text.tag_configure("numbered", foreground="#333")
        text.tag_configure("link", foreground="#0A66C2", underline=True)
        text.tag_configure("email", foreground="#0A66C2", underline=True)
        text.tag_configure("phone", foreground="#036D19", underline=True)
        text.tag_configure("datetime", foreground="#7B1FA2")

        doc = DocumentState(frame=frame, text=text, file_path=file_path)
        self.documents.append(doc)
        self.doc_by_text[text] = doc
        self.doc_by_frame[frame] = doc

        text.bind("<KeyRelease>", self.on_content_changed)
        text.bind("<Control-c>", self.copy_selection)
        text.bind("<Control-C>", self.copy_selection)
        text.bind("<Control-x>", self.cut_selection)
        text.bind("<Control-X>", self.cut_selection)
        text.bind("<Control-v>", self.smart_paste_event)
        text.bind("<Control-V>", self.smart_paste_event)
        text.bind("<Control-Button-1>", self.smart_click_event)
        text.bind("<Control-z>", self.undo_action)
        text.bind("<Control-y>", self.redo_action)
        text.bind("<Control-MouseWheel>", lambda e: self.change_zoom(1 if e.delta > 0 else -1))
        text.bind("<Control-plus>", lambda e: self.change_zoom(1))
        text.bind("<Control-minus>", lambda e: self.change_zoom(-1))
        text.bind("<BackSpace>", self.delete_selection)
        text.bind("<Delete>", self.delete_selection)
        text.bind("<Return>", self.smart_enter_event)
        text.bind("<Control-f>", self.open_find_replace)
        
        self.notebook.add(frame, text=title)
        self.notebook.select(frame)

        if content:
            self._insert_text_with_visual_emojis(doc, content)
            doc.is_modified = False
            doc.last_highlight_source = ""
            self.schedule_syntax_highlighting(doc)

        self.update_tab_title(doc)
        self.update_counters()

    def remove_doc(self, doc: DocumentState):
        if doc.syntax_after_id is not None:
            try:
                self.after_cancel(doc.syntax_after_id)
            except Exception:
                pass
        if doc.stats_after_id is not None:
            try:
                self.after_cancel(doc.stats_after_id)
            except Exception:
                pass
        self.documents = [d for d in self.documents if d is not doc]
        self.doc_by_text.pop(doc.text, None)
        self.doc_by_frame.pop(doc.frame, None)

    def _reconstruct_message_from_editor(self, doc: DocumentState) -> str:
        return self._reconstruct_range_from_editor(doc, "1.0", tk.END, trim_trailing_newline=True)

    def _reconstruct_range_from_editor(
        self,
        doc: DocumentState,
        start: str,
        end: str,
        trim_trailing_newline: bool = False,
    ) -> str:
        chunks = []
        seen_images = set()
        content_data = doc.text.dump(start, end, text=True, image=True)
        for key, value, _index in content_data:
            if key == "text":
                chunks.append(value)
            elif key == "image":
                seen_images.add(value)
                chunks.append(doc.emoji_map.get(value, ""))
        message = "".join(chunks)
        if trim_trailing_newline and message.endswith("\n"):
            message = message[:-1]
        if start == "1.0" and end == tk.END:
            if len(seen_images) != len(doc.emoji_map):
                doc.emoji_map = {name: emoji for name, emoji in doc.emoji_map.items() if name in seen_images}
            doc.message_cache = message
            doc.message_cache_dirty = False
        return message

    def _copy_selection_to_clipboard(self, doc: DocumentState) -> bool:
        try:
            start = doc.text.index(tk.SEL_FIRST)
            end = doc.text.index(tk.SEL_LAST)
        except tk.TclError:
            return False

        selection = self._reconstruct_range_from_editor(doc, start, end)
        self.clipboard_clear()
        self.clipboard_append(selection)
        return True

    def copy_selection(self, event=None):
        doc = self.current_doc() if event is None else self.doc_by_text.get(event.widget)
        if doc is None:
            return "break"
        if self._copy_selection_to_clipboard(doc):
            return "break"
        return None

    def cut_selection(self, event=None):
        doc = self.current_doc() if event is None else self.doc_by_text.get(event.widget)
        if doc is None:
            return "break"
        try:
            start = doc.text.index(tk.SEL_FIRST)
            end = doc.text.index(tk.SEL_LAST)
        except tk.TclError:
            return None

        self._copy_selection_to_clipboard(doc)
        doc.text.delete(start, end)
        self.on_content_changed()
        return "break"

    def delete_selection(self, event=None):
        doc = self.current_doc() if event is None else self.doc_by_text.get(event.widget)
        if doc is None:
            return "break"
        try:
            start = doc.text.index(tk.SEL_FIRST)
            end = doc.text.index(tk.SEL_LAST)
        except tk.TclError:
            return None

        doc.text.delete(start, end)
        self.on_content_changed()
        return "break"

    def _insert_text_with_visual_emojis(self, doc: DocumentState, text: str):
        doc.suspend_change_events = True
        try:
            plain_buffer = []
            i = 0
            n = len(text)
            while i < n:
                ch = text[i]

                keycap = self._consume_keycap_sequence(text, i)
                if keycap:
                    emoji_seq, i = keycap
                    if plain_buffer:
                        doc.text.insert(tk.INSERT, "".join(plain_buffer))
                        plain_buffer = []
                    self.insert_emoji_visual(emoji_seq, trigger_change=False, doc=doc)
                    continue

                if self._is_emoji_char(ch):
                    emoji_seq, i = self._consume_emoji_sequence(text, i)
                    if plain_buffer:
                        doc.text.insert(tk.INSERT, "".join(plain_buffer))
                        plain_buffer = []
                    self.insert_emoji_visual(emoji_seq, trigger_change=False, doc=doc)
                    continue

                plain_buffer.append(ch)
                i += 1
            if plain_buffer:
                doc.text.insert(tk.INSERT, "".join(plain_buffer))
        finally:
            doc.suspend_change_events = False

    def get_emoji_image_tk(self, emoji_char, size=32):
        cache_key = (emoji_char, size)
        cached = self.emoji_image_cache.get(cache_key)
        if cached is not None:
            return cached

        render_size = size * 4
        canvas = Image.new("RGBA", (render_size * 2, render_size * 2), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)

        try:
            if not self.emoji_font_path:
                return None
            font = ImageFont.truetype(self.emoji_font_path, render_size)
            draw.text(
                (render_size, render_size),
                emoji_char,
                font=font,
                fill="white",
                embedded_color=True,
                anchor="mm",
            )

            bbox = canvas.getbbox()
            if not bbox:
                return None

            # Evitar recortes agresivos agregando margen al bounding box.
            padding = max(2, render_size // 6)
            left = max(0, bbox[0] - padding)
            top = max(0, bbox[1] - padding)
            right = min(canvas.width, bbox[2] + padding)
            bottom = min(canvas.height, bbox[3] + padding)
            emoji_cropped = canvas.crop((left, top, right, bottom))
            emoji_cropped = ImageOps.expand(emoji_cropped, border=max(1, padding // 4), fill=(0, 0, 0, 0))

            # Evitar pérdida visual en emojis complejos con un ajuste menos agresivo.
            target_inner_size = int(size * 0.92)
            w, h = emoji_cropped.size
            aspect = w / h if h else 1

            if w <= 1 or h <= 1:
                return None

            if w > h:
                new_w = target_inner_size
                new_h = max(1, int(target_inner_size / aspect))
            else:
                new_h = target_inner_size
                new_w = max(1, int(target_inner_size * aspect))

            emoji_resized = emoji_cropped.resize((new_w, new_h), Image.Resampling.LANCZOS)

            final_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            offset_x = (size - new_w) // 2
            offset_y = (size - new_h) // 2
            final_img.paste(emoji_resized, (offset_x, offset_y), emoji_resized)

            tk_img = ImageTk.PhotoImage(final_img)
            self.emoji_image_cache[cache_key] = tk_img
            return tk_img
        except Exception:
            return None

    def create_emoji_panel_premium(self):
        for cat, icons in self.emoji_categories.items():
            ctk.CTkLabel(
                self.emoji_scroll,
                text=cat.upper(),
                font=("Segoe UI", 10, "bold"),
                text_color="#666666",
            ).pack(pady=(15, 5), anchor="w", padx=5)
            frame = ctk.CTkFrame(self.emoji_scroll, fg_color="transparent")
            frame.pack(fill="x")

            for i, icon in enumerate(icons):
                tk_img = self.get_emoji_image_tk(icon, size=28)
                if tk_img:
                    sidebar_key = ("sidebar", icon, 28)
                    sidebar_img = self.emoji_cache.get(sidebar_key)
                    if sidebar_img is None:
                        sidebar_img = ctk.CTkImage(light_image=ImageTk.getimage(tk_img), size=(28, 28))
                        self.emoji_cache[sidebar_key] = sidebar_img
                    btn = ctk.CTkButton(
                        frame,
                        text="",
                        image=sidebar_img,
                        width=44,
                        height=44,
                        fg_color="#F8F9FA",
                        hover_color="#E9ECEF",
                        corner_radius=8,
                        border_width=1,
                        border_color="#E0E0E0",
                        command=lambda e=icon: self.insert_emoji_visual(e),
                    )
                else:
                    btn = ctk.CTkButton(
                        frame,
                        text=icon,
                        width=44,
                        height=44,
                        fg_color="#F8F9FA",
                        hover_color="#E9ECEF",
                        corner_radius=8,
                        border_width=1,
                        border_color="#E0E0E0",
                        command=lambda e=icon: self.insert_emoji_visual(e),
                    )
                btn.grid(row=i // 5, column=i % 5, padx=2, pady=2)

    def insert_emoji_visual(self, emoji_char, trigger_change=True, doc: DocumentState | None = None):
        doc = doc or self.current_doc()
        if doc is None:
            return

        tk_img = self.get_emoji_image_tk(emoji_char, size=24)
        if tk_img:
            img_name = f"emoji_{doc.emoji_counter}"
            doc.emoji_map[img_name] = emoji_char
            doc.emoji_counter += 1
            doc.text.image_create(tk.INSERT, image=tk_img, name=img_name)
        else:
            doc.text.insert(tk.INSERT, emoji_char)

        if trigger_change:
            self.on_content_changed()

    def on_content_changed(self, event=None):
        doc = self.current_doc() if event is None else self.doc_by_text.get(event.widget)
        if doc is None or doc.suspend_change_events:
            return
        doc.is_modified = True
        doc.message_cache_dirty = True
        self.update_tab_title(doc)
        self.schedule_counters_update(doc)
        self.schedule_syntax_highlighting(doc)

    def schedule_syntax_highlighting(self, doc: DocumentState):
        if doc.syntax_after_id is not None:
            try:
                self.after_cancel(doc.syntax_after_id)
            except Exception:
                pass
        doc.syntax_after_id = self.after(self.SYNTAX_HIGHLIGHT_DELAY_MS, lambda d=doc: self.apply_syntax_highlighting(d))

    def schedule_counters_update(self, doc: DocumentState):
        if doc.stats_after_id is not None:
            try:
                self.after_cancel(doc.stats_after_id)
            except Exception:
                pass
        doc.stats_after_id = self.after(self.STATS_REFRESH_DELAY_MS, lambda d=doc: self.update_counters(doc=d))

    def _clear_tags(self, doc: DocumentState):
        for tag in [
            "bold",
            "italic",
            "strike",
            "inline_code",
            "code_block",
            "quote",
            "bullet",
            "numbered",
            "link",
            "email",
            "phone",
            "datetime",
        ]:
            doc.text.tag_remove(tag, "1.0", tk.END)

    def apply_syntax_highlighting(self, doc: DocumentState):
        doc.syntax_after_id = None
        content = doc.text.get("1.0", tk.END)
        if content == doc.last_highlight_source:
            return
        doc.last_highlight_source = content

        self._clear_tags(doc)
        doc.interactive_ranges.clear()

        for tag, pattern, group_idx in self._pattern_specs:
            for match in pattern.finditer(content):
                start = match.start(group_idx)
                end = match.end(group_idx)
                if start < end:
                    doc.text.tag_add(tag, f"1.0 + {start} chars", f"1.0 + {end} chars")

        for match in re.finditer(r"^>\s.*$", content, re.MULTILINE):
            doc.text.tag_add("quote", f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")

        for match in re.finditer(r"^(?:\*|-|•)\s+.*$", content, re.MULTILINE):
            doc.text.tag_add("bullet", f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")

        for match in re.finditer(r"^\d+\.\s+.*$", content, re.MULTILINE):
            doc.text.tag_add("numbered", f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")

        for tag, pattern, interactive_type in self._smart_specs:
            for match in pattern.finditer(content):
                value = match.group(0)
                start_idx = f"1.0 + {match.start()} chars"
                end_idx = f"1.0 + {match.end()} chars"
                doc.text.tag_add(tag, start_idx, end_idx)
                doc.interactive_ranges.append((start_idx, end_idx, interactive_type, value))

    def smart_paste_event(self, event=None):
        doc = self.current_doc() if event is None else self.doc_by_text.get(event.widget)
        if doc is None:
            return "break"
        try:
            text = self.clipboard_get()
        except Exception:
            text = pyperclip.paste()
        self._insert_text_with_visual_emojis(doc, text or "")
        self.on_content_changed()
        return "break"

    def smart_click_event(self, event=None):
        doc = self.current_doc() if event is None else self.doc_by_text.get(event.widget)
        if doc is None:
            return
        index = doc.text.index(f"@{event.x},{event.y}")
        for start, end, kind, value in doc.interactive_ranges:
            if doc.text.compare(index, ">=", start) and doc.text.compare(index, "<", end):
                if kind == "link":
                    webbrowser.open(value)
                elif kind == "email":
                    webbrowser.open(f"mailto:{value}")
                elif kind == "phone":
                    pyperclip.copy(value)
                    messagebox.showinfo("Telefono", f"Numero copiado: {value}")
                elif kind == "datetime":
                    messagebox.showinfo("Fecha/Hora", f"Detectado: {value}")
                return "break"
        return None

    def _history_action(self, action: str, event=None):
        doc = self.current_doc() if event is None else self.doc_by_text.get(event.widget)
        if doc is None:
            return "break"
        try:
            getattr(doc.text, action)()
        except tk.TclError:
            return "break"
        self.on_content_changed()
        return "break"

    def undo_action(self, event=None):
        return self._history_action("edit_undo", event)

    def redo_action(self, event=None):
        return self._history_action("edit_redo", event)

    def export_to_whatsapp(self):
        doc = self.current_doc()
        if doc is None:
            return
        message = self._reconstruct_message_from_editor(doc)
        cleaned = message.replace("\r\n", "\n").replace("\r", "\n")
        pyperclip.copy(cleaned)
        messagebox.showinfo("WhatsApp", "Mensaje reconstruido y copiado con exito.")

    def create_tool_btn(self, parent, text, command, font_style=None, width=95):
        btn = ctk.CTkButton(
            parent,
            text=text,
            command=command,
            width=width,
            height=40,
            fg_color="white",
            text_color="#333333",
            border_width=1,
            border_color="#D1D1D1",
            hover_color="#F0F2F5",
            font=font_style if font_style else ("Segoe UI", 11),
        )
        btn.pack(side="left", padx=3)
        return btn

    def create_menu_button(self, parent, text, items):
        menu_btn = tk.Menubutton(
            parent,
            text=text,
            font=("Segoe UI", 11),
            bg="white",
            fg="#333333",
            activebackground="#F0F2F5",
            activeforeground="#333333",
            relief="solid",
            bd=1,
            padx=12,
            pady=8,
            cursor="hand2",
        )
        menu = tk.Menu(menu_btn, tearoff=0, font=("Segoe UI", 10))
        for label, command in items:
            menu.add_command(label=label, command=command)
        menu_btn.configure(menu=menu)
        menu_btn.menu = menu
        menu_btn.pack(side="left", padx=4)
        return menu_btn

    def create_emoji_menu_button(self, parent, text):
        menu_btn = tk.Menubutton(
            parent,
            text=text,
            font=("Segoe UI", 11),
            bg="white",
            fg="#333333",
            activebackground="#F0F2F5",
            activeforeground="#333333",
            relief="solid",
            bd=1,
            padx=12,
            pady=8,
            cursor="hand2",
        )
        menu = tk.Menu(menu_btn, tearoff=0, font=("Segoe UI", 10))
        for category, icons in self.emoji_categories.items():
            sub = tk.Menu(menu, tearoff=0, font=("Segoe UI Emoji", 10))
            for emoji_char in icons:
                sub.add_command(label=emoji_char, command=lambda e=emoji_char: self.insert_emoji_visual(e))
            menu.add_cascade(label=category, menu=sub)
        menu_btn.configure(menu=menu)
        menu_btn.menu = menu
        menu_btn.pack(side="left", padx=4)
        return menu_btn

    def add_separator(self, parent):
        ctk.CTkLabel(parent, text="|", text_color="#D1D1D1", font=("Arial", 18)).pack(side="left", padx=9)

    def _inject_emojis_into_edit_menu(self):
        if self._edit_emojis_injected:
            return
        try:
            self.edit_menu_btn.menu.add_cascade(label="Emojis", menu=self.emojis_menu_btn.menu)
            self._edit_emojis_injected = True
        except Exception:
            return

    def _remove_emojis_from_edit_menu(self):
        if not self._edit_emojis_injected:
            return
        try:
            end_index = self.edit_menu_btn.menu.index("end")
            if end_index is None:
                self._edit_emojis_injected = False
                return
            for idx in range(end_index, -1, -1):
                if self.edit_menu_btn.menu.type(idx) == "cascade" and self.edit_menu_btn.menu.entrycget(idx, "label") == "Emojis":
                    self.edit_menu_btn.menu.delete(idx)
                    break
        finally:
            self._edit_emojis_injected = False

    def on_window_resize(self, event=None):
        if self._is_closing or not self.winfo_exists():
            return
        widgets = (
            self.btn_copy_top,
            self.sidebar,
            self.quick_title_btn,
            self.quick_quote_btn,
            self.quick_list_btn,
        )
        if any(not widget.winfo_exists() for widget in widgets):
            return
        width = self.winfo_width()
        if width < 980:
            self.btn_copy_top.configure(text="WSP", width=90)
            if self.sidebar.winfo_ismapped():
                self.sidebar.grid_remove()
                self.grid_columnconfigure(0, minsize=0)
            self._inject_emojis_into_edit_menu()
        else:
            self.btn_copy_top.configure(text="🚀 COPIAR PARA WHATSAPP", width=220)
            if not self.sidebar.winfo_ismapped():
                self.sidebar.grid(row=1, column=0, sticky="nsew")
                self.grid_columnconfigure(0, minsize=290)
            self._remove_emojis_from_edit_menu()

        if width >= 1160:
            if not self.quick_title_btn.winfo_ismapped():
                self.quick_title_btn.pack(side="left", padx=2)
            if not self.quick_quote_btn.winfo_ismapped():
                self.quick_quote_btn.pack(side="left", padx=2)
            if not self.quick_list_btn.winfo_ismapped():
                self.quick_list_btn.pack(side="left", padx=2)
        else:
            if self.quick_title_btn.winfo_ismapped():
                self.quick_title_btn.pack_forget()
            if self.quick_quote_btn.winfo_ismapped():
                self.quick_quote_btn.pack_forget()
            if self.quick_list_btn.winfo_ismapped():
                self.quick_list_btn.pack_forget()

    def apply_format(self, char):
        doc = self.current_doc()
        if doc is None:
            return
        try:
            start = doc.text.index(tk.SEL_FIRST)
            end = doc.text.index(tk.SEL_LAST)
            
            prefix = doc.text.get(start, f"{start} + {len(char)} chars")
            suffix = doc.text.get(f"{end} - {len(char)} chars", end)
            
            if prefix == char and suffix == char:
                doc.text.delete(f"{end} - {len(char)} chars", end)
                doc.text.delete(start, f"{start} + {len(char)} chars")
            else:
                doc.text.insert(end, char)
                doc.text.insert(start, char)
        except tk.TclError:
            doc.text.insert(tk.INSERT, f"{char}{char}")
            doc.text.mark_set(tk.INSERT, f"insert - {len(char)} chars")
        self.on_content_changed()

    def insert_code_block(self):
        doc = self.current_doc()
        if doc is None:
            return
        try:
            start = doc.text.index(tk.SEL_FIRST)
            end = doc.text.index(tk.SEL_LAST)
            doc.text.insert(end, "\n```")
            doc.text.insert(start, "```\n")
        except tk.TclError:
            doc.text.insert(tk.INSERT, "```\n\n```")
            doc.text.mark_set(tk.INSERT, "insert - 4 chars")
        self.on_content_changed()

    def insert_quote(self):
        doc = self.current_doc()
        if doc is None:
            return
        try:
            start_line = int(doc.text.index(tk.SEL_FIRST).split(".")[0])
            end_line = int(doc.text.index(tk.SEL_LAST).split(".")[0])
            for line_num in range(start_line, end_line + 1):
                doc.text.insert(f"{line_num}.0", "> ")
        except tk.TclError:
            doc.text.insert("insert linestart", "> ")
        self.on_content_changed()

    def insert_title(self):
        doc = self.current_doc()
        if doc is None:
            return
        try:
            start = doc.text.index(tk.SEL_FIRST)
            end = doc.text.index(tk.SEL_LAST)
            txt = doc.text.get(start, end).upper()
            doc.text.delete(start, end)
            doc.text.insert(start, f"*{txt}*")
        except tk.TclError:
            return
        self.on_content_changed()

    def insert_list(self):
        doc = self.current_doc()
        if doc is None:
            return
        try:
            start_line = int(doc.text.index(tk.SEL_FIRST).split(".")[0])
            end_line = int(doc.text.index(tk.SEL_LAST).split(".")[0])
            for line_num in range(start_line, end_line + 1):
                doc.text.insert(f"{line_num}.0", "• ")
        except tk.TclError:
            doc.text.insert("insert linestart", "• ")
        self.on_content_changed()

    def insert_numbered_list(self):
        doc = self.current_doc()
        if doc is None:
            return
        try:
            start_line = int(doc.text.index(tk.SEL_FIRST).split(".")[0])
            end_line = int(doc.text.index(tk.SEL_LAST).split(".")[0])
            count = 1
            for line_num in range(start_line, end_line + 1):
                doc.text.insert(f"{line_num}.0", f"{count}. ")
                count += 1
        except tk.TclError:
            doc.text.insert("insert linestart", "1. ")
        self.on_content_changed()

    def change_appearance(self, mode):
        ctk.set_appearance_mode(mode)
        bg_color = "white" if mode == "Light" else "#1E1E1E"
        fg_color = "black" if mode == "Light" else "#D4D4D4"
        
        for doc in self.documents:
            doc.frame.configure(bg=bg_color)
            doc.text.configure(bg=bg_color, fg=fg_color, insertbackground="#25D366")
            
            if mode == "Dark":
                doc.text.tag_configure("inline_code", background="#2D2D2D", foreground="#CE9178")
                doc.text.tag_configure("code_block", background="#252526", foreground="#D4D4D4")
                doc.text.tag_configure("quote", foreground="#858585")
                doc.text.tag_configure("link", foreground="#4FC1FF")
            else:
                doc.text.tag_configure("inline_code", background="#F5F5F5", foreground="black")
                doc.text.tag_configure("code_block", background="#F0F3F5", foreground="black")
                doc.text.tag_configure("quote", foreground="#555")
                doc.text.tag_configure("link", foreground="#0A66C2")
        
        self.sidebar.configure(fg_color="#FFFFFF" if mode == "Light" else "#252526")
        self.toolbar.configure(fg_color="#F0F2F5" if mode == "Light" else "#2D2D2D")

    def change_zoom(self, delta):
        doc = self.current_doc()
        if not doc: return
        current_font = doc.text.cget("font")
        # Parse font: ('Segoe UI', 13)
        if isinstance(current_font, str):
            import tkinter.font as tkfont
            font_obj = tkfont.Font(font=current_font)
            size = font_obj.actual()["size"]
        else:
            size = current_font[1]
        
        new_size = max(8, min(72, size + delta))
        for d in self.documents:
            d.text.configure(font=("Segoe UI", new_size))
            # Actualizar tags de fuente
            d.text.tag_configure("bold", font=("Segoe UI", new_size, "bold"))
            d.text.tag_configure("italic", font=("Segoe UI", new_size, "italic"))

    def insert_invisible_char(self):
        doc = self.current_doc()
        if doc is None:
            return
        doc.text.insert(tk.INSERT, "\u2800")
        self.on_content_changed()

    def insert_emoji_combo(self):
        doc = self.current_doc()
        if doc is None:
            return
        combos = [
            "👀🍿",
            "✨Texto✨",
            "🚩🚩🚩",
            "🤡",
            "🍿🔥",
            "🕵️📌",
        ]
        popup = tk.Toplevel(self)
        popup.title("Combos de Emojis")
        popup.geometry("340x240")
        popup.transient(self)
        popup.grab_set()

        tk.Label(popup, text="Elige un combo", font=("Segoe UI", 11, "bold")).pack(pady=10)
        container = tk.Frame(popup)
        container.pack(fill="both", expand=True, padx=12, pady=6)

        for combo in combos:
            tk.Button(
                container,
                text=combo,
                font=("Segoe UI Emoji", 12),
                command=lambda c=combo: (doc.text.insert(tk.INSERT, c), self.on_content_changed(), popup.destroy()),
            ).pack(fill="x", pady=4)

    def update_counters(self, event=None, doc: DocumentState | None = None):
        if doc is None:
            doc = self.current_doc()
        if doc is None:
            self.lbl_stats.configure(text="Sin documentos")
            if hasattr(self, "lbl_limit"):
                self.lbl_limit.configure(text="")
            return

        doc.stats_after_id = None

        if doc.message_cache_dirty:
            message = self._reconstruct_message_from_editor(doc)
        else:
            message = doc.message_cache
        chars = len(message)
        words = len(re.findall(r"\S+", message))
        doc_name = Path(doc.file_path).name if doc.file_path else "Sin titulo"
        self.lbl_stats.configure(text=f"Caracteres: {chars} | Palabras: {words} | Documento: {doc_name}")
        
        if hasattr(self, "lbl_limit"):
            if chars > 3150:
                self.lbl_limit.configure(text="⚠️ SUPERAS LÍMITE DE LEER MÁS", text_color="#D32F2F")
            elif chars > 2800:
                self.lbl_limit.configure(text="Cerca del límite de Leer más", text_color="#F57C00")
            else:
                self.lbl_limit.configure(text="")

    def _confirm_discard_changes(self, doc: DocumentState, action_name: str) -> bool:
        if not doc.is_modified:
            return True
        return messagebox.askyesno(action_name, "Hay cambios sin guardar. Quieres continuar?")

    def load_session(self):
        if not hasattr(self, 'session_file') or not self.session_file.exists():
            return False
        try:
            with open(self.session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not data:
                return False
            for doc_data in data:
                self.create_document_tab(
                    title=doc_data.get("title", "Sin titulo"),
                    content=doc_data.get("content", ""),
                    file_path=doc_data.get("file_path")
                )
                doc = self.documents[-1]
                doc.is_modified = doc_data.get("is_modified", False)
                self.update_tab_title(doc)
            self.update_counters()
            return True
        except Exception:
            return False

    def save_session(self):
        data = []
        for doc in self.documents:
            title = Path(doc.file_path).name if doc.file_path else "Sin titulo"
            content = self._reconstruct_message_from_editor(doc)
            data.append({
                "title": title,
                "content": content,
                "file_path": doc.file_path,
                "is_modified": doc.is_modified
            })
        try:
            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def smart_enter_event(self, event=None):
        doc = self.current_doc() if event is None else self.doc_by_text.get(event.widget)
        if doc is None:
            return
        
        line = doc.text.get("insert linestart", "insert lineend")
        
        bullet_match = re.match(r'^([•\-\*])\s+(.*)$', line)
        if bullet_match:
            marker, content = bullet_match.groups()
            if not content.strip():
                doc.text.delete("insert linestart", "insert lineend")
                return "break"
            else:
                doc.text.insert(tk.INSERT, f"\n{marker} ")
                return "break"
                
        number_match = re.match(r'^(\d+)\.\s+(.*)$', line)
        if number_match:
            num, content = number_match.groups()
            if not content.strip():
                doc.text.delete("insert linestart", "insert lineend")
                return "break"
            else:
                next_num = int(num) + 1
                doc.text.insert(tk.INSERT, f"\n{next_num}. ")
                return "break"
        return None

    def open_find_replace(self, event=None):
        popup = tk.Toplevel(self)
        popup.title("Buscar y Reemplazar")
        popup.geometry("360x180")
        popup.transient(self)
        popup.attributes("-topmost", True)
        
        tk.Label(popup, text="Buscar:", font=("Segoe UI", 10)).grid(row=0, column=0, padx=10, pady=10, sticky="e")
        entry_find = tk.Entry(popup, font=("Segoe UI", 10), width=25)
        entry_find.grid(row=0, column=1, padx=10, pady=10)
        entry_find.focus_set()
        
        tk.Label(popup, text="Reemplazar:", font=("Segoe UI", 10)).grid(row=1, column=0, padx=10, pady=10, sticky="e")
        entry_replace = tk.Entry(popup, font=("Segoe UI", 10), width=25)
        entry_replace.grid(row=1, column=1, padx=10, pady=10)
        
        def do_find():
            doc = self.current_doc()
            if not doc: return
            doc.text.tag_remove("sel", "1.0", tk.END)
            target = entry_find.get()
            if not target: return
            start_idx = doc.text.search(target, "insert", stopindex=tk.END)
            if not start_idx:
                start_idx = doc.text.search(target, "1.0", stopindex=tk.END)
            if start_idx:
                end_idx = f"{start_idx} + {len(target)} chars"
                doc.text.tag_add("sel", start_idx, end_idx)
                doc.text.mark_set("insert", end_idx)
                doc.text.see(start_idx)
                
        def do_replace():
            doc = self.current_doc()
            if not doc: return
            try:
                sel_start = doc.text.index(tk.SEL_FIRST)
                sel_end = doc.text.index(tk.SEL_LAST)
                if doc.text.get(sel_start, sel_end) == entry_find.get():
                    doc.text.delete(sel_start, sel_end)
                    doc.text.insert(sel_start, entry_replace.get())
                    self.on_content_changed()
                    do_find()
            except tk.TclError:
                do_find()
                
        def do_replace_all():
            doc = self.current_doc()
            if not doc: return
            target = entry_find.get()
            repl = entry_replace.get()
            if not target: return
            
            count = 0
            idx = "1.0"
            while True:
                idx = doc.text.search(target, idx, stopindex=tk.END)
                if not idx: break
                end_idx = f"{idx} + {len(target)} chars"
                doc.text.delete(idx, end_idx)
                doc.text.insert(idx, repl)
                idx = f"{idx} + {len(repl)} chars"
                count += 1
                
            if count > 0:
                self.on_content_changed()
                messagebox.showinfo("Reemplazar Todo", f"Se realizaron {count} reemplazos.")
        
        btn_frame = tk.Frame(popup)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=10)
        
        tk.Button(btn_frame, text="Buscar", command=do_find, width=10).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Reemplazar", command=do_replace, width=10).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Todo", command=do_replace_all, width=10).pack(side="left", padx=5)

    def on_closing(self):
        self._is_closing = True
        self.save_session()
        self.destroy()

    def new_file(self):
        self.create_document_tab(title="Sin titulo")

    def open_file(self):
        paths = filedialog.askopenfilenames(filetypes=[("Markdown", "*.md"), ("Texto", "*.txt")])
        if not paths:
            return

        for path in paths:
            try:
                content = Path(path).read_text(encoding="utf-8")
            except UnicodeDecodeError:
                try:
                    content = Path(path).read_text(encoding="cp1252")
                except Exception as exc:
                    messagebox.showerror("Error", f"No se pudo abrir el archivo: {exc}")
                    continue
            except Exception as exc:
                messagebox.showerror("Error", f"No se pudo abrir el archivo: {exc}")
                continue

            title = Path(path).name
            self.create_document_tab(title=title, content=content, file_path=path)
            doc = self.current_doc()
            if doc:
                doc.is_modified = False
                self.update_tab_title(doc)
                self.update_counters()

    def _save_doc(self, doc: DocumentState) -> bool:
        if not doc.file_path:
            self.notebook.select(doc.frame)
            return self.save_file_as()

        try:
            message = self._reconstruct_message_from_editor(doc)
            Path(doc.file_path).write_text(message, encoding="utf-8")
            doc.is_modified = False
            self.update_tab_title(doc)
            self.update_counters()
            return True
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo guardar el archivo: {exc}")
            return False

    def save_file(self):
        doc = self.current_doc()
        if doc is None:
            return False
        ok = self._save_doc(doc)
        if ok:
            messagebox.showinfo("Exito", "Guardado correctamente.")
        return ok

    def save_file_as(self):
        doc = self.current_doc()
        if doc is None:
            return False

        path = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("Texto", "*.txt")],
        )
        if not path:
            return False

        doc.file_path = path
        ok = self._save_doc(doc)
        if ok:
            messagebox.showinfo("Exito", "Guardado correctamente.")
        return ok

    def close_current_tab(self):
        doc = self.current_doc()
        if doc is None:
            return

        if doc.is_modified:
            res = messagebox.askyesnocancel("Cerrar pestaña", "Hay cambios sin guardar. Guardar antes de cerrar?")
            if res is None:
                return
            if res:
                if not self._save_doc(doc):
                    return

        self.notebook.forget(doc.frame)
        self.remove_doc(doc)
        if not self.documents:
            self.new_file()
        self.update_counters()

    def on_tab_changed(self, event=None):
        self.update_counters()
        doc = self.current_doc()
        if doc:
            self.schedule_syntax_highlighting(doc)


if __name__ == "__main__":
    app = WhatsAppEditor()
    app.mainloop()
