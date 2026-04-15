"""Finance Agent Android App (KivyMD) main entrypoint.

Features:
- Home dashboard: balance/income/expense + recent transactions
- Add transaction (manual)
- AI text parsing (Anthropic API)
- Scan receipt/slip image (Anthropic Vision)
- History with delete
- Settings: API key, theme, clear all data
"""

from __future__ import annotations

import base64
import json
import os
import threading
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

import requests
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import StringProperty
from kivy.uix.screenmanager import Screen
from kivy.utils import platform
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel
from kivymd.uix.snackbar import Snackbar

try:
    from plyer import filechooser
except Exception:
    filechooser = None

ANDROID = platform == "android"
if ANDROID:
    from android.permissions import Permission, request_permissions


# =========================
# Paths / Storage
# =========================

DATA_FILE: Optional[str] = None
CONFIG_FILE: Optional[str] = None

DEFAULT_CONFIG = {"api_key": "", "theme": "Light", "currency": "฿"}

CATEGORIES = [
    "food",
    "transport",
    "income",
    "shopping",
    "health",
    "entertainment",
    "other",
]

CAT_ICONS = {
    "food": "food-fork-drink",
    "transport": "car",
    "income": "cash-plus",
    "shopping": "cart",
    "health": "hospital-box",
    "entertainment": "gamepad-variant",
    "other": "dots-horizontal-circle",
}

CAT_COLORS = {
    "food": (0.96, 0.62, 0.04, 1),
    "transport": (0.23, 0.51, 0.96, 1),
    "income": (0.06, 0.72, 0.51, 1),
    "shopping": (0.93, 0.29, 0.60, 1),
    "health": (0.93, 0.27, 0.27, 1),
    "entertainment": (0.54, 0.36, 0.96, 1),
    "other": (0.42, 0.45, 0.50, 1),
}


def get_data_dir() -> str:
    if ANDROID:
        from android.storage import app_storage_path

        return app_storage_path()
    return os.path.dirname(os.path.abspath(__file__))


def init_file_paths() -> None:
    global DATA_FILE, CONFIG_FILE
    base = get_data_dir()
    os.makedirs(base, exist_ok=True)
    DATA_FILE = os.path.join(base, "data.json")
    CONFIG_FILE = os.path.join(base, "config.json")


# =========================
# Data helpers
# =========================


def load_data() -> List[Dict]:
    if not DATA_FILE or not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            obj = json.load(f)
            return obj if isinstance(obj, list) else []
    except Exception:
        return []


def save_data(rows: List[Dict]) -> None:
    if not DATA_FILE:
        return
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)


def normalize_category(cat: str) -> str:
    c = (cat or "").strip().lower()
    mapping = {
        "food": [
            "dining",
            "restaurant",
            "meal",
            "lunch",
            "dinner",
            "breakfast",
            "coffee",
            "cafe",
            "eat",
            "snack",
            "food",
        ],
        "transport": [
            "taxi",
            "grab",
            "uber",
            "bus",
            "mrt",
            "bts",
            "train",
            "subway",
            "metro",
            "car",
            "transport",
        ],
        "income": [
            "salary",
            "income",
            "pay",
            "payment",
            "revenue",
            "bonus",
            "freelance",
            "earn",
        ],
        "shopping": ["shop", "mall", "market", "store", "buy", "purchase", "shopping"],
        "health": [
            "medicine",
            "hospital",
            "clinic",
            "doctor",
            "pharmacy",
            "medical",
            "health",
        ],
        "entertainment": [
            "movie",
            "game",
            "fun",
            "party",
            "bar",
            "concert",
            "entertainment",
        ],
    }

    for target, words in mapping.items():
        if c == target or c in words:
            return target

    return c if c in CATEGORIES else "other"


def add_transaction(amount: float, category: str, note: str) -> None:
    rows = load_data()
    rows.append(
        {
            "amount": float(amount),
            "category": normalize_category(category),
            "note": (note or "").strip(),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    )
    save_data(rows)


def delete_transaction(index: int) -> None:
    rows = load_data()
    if 0 <= index < len(rows):
        rows.pop(index)
        save_data(rows)


def get_summary() -> Tuple[float, float, float]:
    rows = load_data()
    income = sum(
        float(r.get("amount", 0)) for r in rows if float(r.get("amount", 0)) > 0
    )
    expense = sum(
        float(r.get("amount", 0)) for r in rows if float(r.get("amount", 0)) < 0
    )
    balance = income + expense
    return balance, income, expense


def load_config() -> Dict:
    if not CONFIG_FILE or not os.path.exists(CONFIG_FILE):
        return dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            obj = json.load(f)
            if not isinstance(obj, dict):
                return dict(DEFAULT_CONFIG)
            merged = dict(DEFAULT_CONFIG)
            merged.update(obj)
            return merged
    except Exception:
        return dict(DEFAULT_CONFIG)


def save_config(cfg: Dict) -> None:
    if not CONFIG_FILE:
        return
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


# =========================
# AI helpers
# =========================


def clean_json(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.replace("```json", "").replace("```", "")
    return t.strip()


def _anthropic_request(payload: Dict, api_key: str) -> Dict:
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json=payload,
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


def ask_ai_text(text: str, api_key: str, callback: Callable[[Dict, str], None]) -> None:
    def worker():
        try:
            prompt = f"""
Convert this into one finance transaction.

Input:
{text}

Return ONLY JSON:
{{"amount": number, "category": "string", "note": "string"}}

Category must be one of:
food, transport, income, shopping, health, entertainment, other

Rules:
- income => positive amount
- expense => negative amount
- if unsure => category "other"
""".strip()

            payload = {
                "model": "claude-haiku-4-5",
                "max_tokens": 200,
                "messages": [{"role": "user", "content": prompt}],
            }

            data = _anthropic_request(payload, api_key)
            text_out = data["content"][0]["text"]
            parsed = json.loads(clean_json(text_out))
            parsed["category"] = normalize_category(parsed.get("category", "other"))

            Clock.schedule_once(lambda dt: callback(parsed, ""), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt: callback({}, str(e)), 0)

    threading.Thread(target=worker, daemon=True).start()


def ask_ai_image(
    path: str, api_key: str, callback: Callable[[Dict, str], None]
) -> None:
    def worker():
        try:
            ext = os.path.splitext(path.lower())[1]
            media = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".webp": "image/webp",
            }.get(ext, "image/jpeg")

            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")

            prompt = """
Convert this receipt/slip image to one finance transaction.

Return ONLY JSON:
{"amount": number, "category": "string", "note": "string"}

Category must be one of:
food, transport, income, shopping, health, entertainment, other

Rules:
- income => positive amount
- expense => negative amount
- if unsure => category "other"
""".strip()

            payload = {
                "model": "claude-haiku-4-5",
                "max_tokens": 250,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media,
                                    "data": b64,
                                },
                            },
                        ],
                    }
                ],
            }

            data = _anthropic_request(payload, api_key)
            text_out = data["content"][0]["text"]
            parsed = json.loads(clean_json(text_out))
            parsed["category"] = normalize_category(parsed.get("category", "other"))

            Clock.schedule_once(lambda dt: callback(parsed, ""), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt: callback({}, str(e)), 0)

    threading.Thread(target=worker, daemon=True).start()


# =========================
# UI
# =========================

KV = r"""
#:import dp kivy.metrics.dp

<RootNav>:
    orientation: "vertical"

    ScreenManager:
        id: sm

        HomeScreen:
            name: "home"

        HistoryScreen:
            name: "history"

        AddScreen:
            name: "add"

        AIScreen:
            name: "ai"

        ScanScreen:
            name: "scan"

        SettingsScreen:
            name: "settings"

    MDBoxLayout:
        size_hint_y: None
        height: "68dp"
        padding: "12dp", "8dp"
        spacing: "8dp"

        MDIconButton:
            icon: "home"
            on_release: app.go_to_screen("home")

        MDIconButton:
            icon: "history"
            on_release: app.go_to_screen("history")

        Widget:

        MDFloatingActionButton:
            icon: "plus"
            on_release: app.go_to_screen("add")

        Widget:

        MDIconButton:
            icon: "robot"
            on_release: app.go_to_screen("ai")

        MDIconButton:
            icon: "camera"
            on_release: app.go_to_screen("scan")


<HomeScreen>:
    MDBoxLayout:
        orientation: "vertical"

        MDTopAppBar:
            title: "Finance Agent"
            right_action_items: [["cog-outline", lambda x: app.go_to_screen("settings")]]

        ScrollView:
            MDBoxLayout:
                orientation: "vertical"
                adaptive_height: True
                padding: "12dp"
                spacing: "10dp"

                MDCard:
                    size_hint_y: None
                    height: "110dp"
                    radius: [12]
                    elevation: 2
                    md_bg_color: app.theme_cls.primary_color
                    padding: "14dp"

                    MDBoxLayout:
                        orientation: "vertical"

                        MDLabel:
                            text: "Balance"
                            theme_text_color: "Custom"
                            text_color: 1, 1, 1, 1

                        MDLabel:
                            id: lbl_balance
                            text: "฿ 0.00"
                            font_style: "H4"
                            theme_text_color: "Custom"
                            text_color: 1, 1, 1, 1

                MDBoxLayout:
                    adaptive_height: True
                    spacing: "10dp"

                    MDCard:
                        size_hint_y: None
                        height: "90dp"
                        radius: [12]
                        elevation: 1
                        md_bg_color: 0.10, 0.62, 0.40, 1
                        padding: "10dp"

                        MDBoxLayout:
                            orientation: "vertical"
                            MDLabel:
                                text: "Income"
                                theme_text_color: "Custom"
                                text_color: 1, 1, 1, 1
                            MDLabel:
                                id: lbl_income
                                text: "฿ 0.00"
                                theme_text_color: "Custom"
                                text_color: 1, 1, 1, 1

                    MDCard:
                        size_hint_y: None
                        height: "90dp"
                        radius: [12]
                        elevation: 1
                        md_bg_color: 0.85, 0.22, 0.25, 1
                        padding: "10dp"

                        MDBoxLayout:
                            orientation: "vertical"
                            MDLabel:
                                text: "Expense"
                                theme_text_color: "Custom"
                                text_color: 1, 1, 1, 1
                            MDLabel:
                                id: lbl_expense
                                text: "฿ 0.00"
                                theme_text_color: "Custom"
                                text_color: 1, 1, 1, 1

                MDLabel:
                    text: "Recent Transactions"
                    bold: True
                    size_hint_y: None
                    height: self.texture_size[1] + dp(8)

                MDBoxLayout:
                    id: recent_box
                    orientation: "vertical"
                    adaptive_height: True
                    spacing: "8dp"


<AddScreen>:
    MDBoxLayout:
        orientation: "vertical"

        MDTopAppBar:
            title: "Add Transaction"
            left_action_items: [["arrow-left", lambda x: app.go_back()]]

        ScrollView:
            MDBoxLayout:
                orientation: "vertical"
                adaptive_height: True
                padding: "12dp"
                spacing: "12dp"

                MDTextField:
                    id: add_amount
                    hint_text: "Amount (negative = expense)"
                    helper_text: "Example: -45, 3000"
                    helper_text_mode: "on_focus"
                    input_filter: "float"

                MDLabel:
                    text: "Category"
                    bold: True
                    size_hint_y: None
                    height: self.texture_size[1] + dp(6)

                MDBoxLayout:
                    id: category_grid
                    orientation: "vertical"
                    adaptive_height: True
                    spacing: "8dp"

                MDTextField:
                    id: add_note
                    hint_text: "Note"
                    helper_text: "e.g. lunch, salary, taxi"
                    helper_text_mode: "on_focus"

                MDRaisedButton:
                    text: "Save"
                    pos_hint: {"center_x": 0.5}
                    on_release: app.save_manual_transaction()


<AIScreen>:
    MDBoxLayout:
        orientation: "vertical"

        MDTopAppBar:
            title: "AI Input"
            left_action_items: [["arrow-left", lambda x: app.go_back()]]

        ScrollView:
            MDBoxLayout:
                orientation: "vertical"
                adaptive_height: True
                padding: "12dp"
                spacing: "12dp"

                MDTextField:
                    id: ai_text
                    hint_text: "Type natural language e.g. paid 45 for coffee"
                    multiline: True
                    max_height: "180dp"

                MDRaisedButton:
                    id: ai_btn
                    text: "Parse with AI"
                    pos_hint: {"center_x": 0.5}
                    on_release: app.process_ai_text()

                MDCard:
                    id: ai_result_card
                    elevation: 2
                    radius: [12]
                    padding: "12dp"
                    adaptive_height: True
                    opacity: 0
                    disabled: True

                    MDBoxLayout:
                        orientation: "vertical"
                        adaptive_height: True
                        spacing: "8dp"

                        MDLabel:
                            id: ai_result_label
                            text: ""

                        MDBoxLayout:
                            adaptive_height: True
                            spacing: "8dp"

                            MDRaisedButton:
                                text: "Confirm"
                                on_release: app.confirm_ai_transaction()

                            MDFlatButton:
                                text: "Cancel"
                                on_release: app.hide_ai_result()


<ScanScreen>:
    MDBoxLayout:
        orientation: "vertical"

        MDTopAppBar:
            title: "Scan Slip"
            left_action_items: [["arrow-left", lambda x: app.go_back()]]

        MDBoxLayout:
            orientation: "vertical"
            padding: "12dp"
            spacing: "10dp"

            MDRaisedButton:
                id: pick_btn
                text: "Pick Image"
                on_release: app.pick_image()

            MDLabel:
                id: selected_image_label
                text: "No image selected"

            MDRaisedButton:
                id: scan_btn
                text: "Analyze with AI"
                on_release: app.scan_image()

            MDCard:
                id: scan_result_card
                elevation: 2
                radius: [12]
                padding: "12dp"
                adaptive_height: True
                opacity: 0
                disabled: True

                MDBoxLayout:
                    orientation: "vertical"
                    adaptive_height: True
                    spacing: "8dp"

                    MDLabel:
                        id: scan_result_label
                        text: ""

                    MDBoxLayout:
                        adaptive_height: True
                        spacing: "8dp"

                        MDRaisedButton:
                            text: "Confirm"
                            on_release: app.confirm_scan_transaction()

                        MDFlatButton:
                            text: "Cancel"
                            on_release: app.hide_scan_result()


<HistoryScreen>:
    MDBoxLayout:
        orientation: "vertical"

        MDTopAppBar:
            title: "History"
            left_action_items: [["arrow-left", lambda x: app.go_back()]]

        ScrollView:
            MDBoxLayout:
                id: history_box
                orientation: "vertical"
                adaptive_height: True
                padding: "12dp"
                spacing: "8dp"


<SettingsScreen>:
    MDBoxLayout:
        orientation: "vertical"

        MDTopAppBar:
            title: "Settings"
            left_action_items: [["arrow-left", lambda x: app.go_back()]]

        ScrollView:
            MDBoxLayout:
                orientation: "vertical"
                adaptive_height: True
                padding: "12dp"
                spacing: "12dp"

                MDTextField:
                    id: api_key
                    hint_text: "Anthropic API Key"
                    password: True

                MDRaisedButton:
                    text: "Save API Key"
                    on_release: app.save_api_key()

                MDLabel:
                    text: "Theme"
                    bold: True
                    size_hint_y: None
                    height: self.texture_size[1] + dp(8)

                MDBoxLayout:
                    adaptive_height: True
                    spacing: "8dp"

                    MDRaisedButton:
                        text: "Light"
                        on_release: app.set_theme("Light")

                    MDRaisedButton:
                        text: "Dark"
                        on_release: app.set_theme("Dark")

                MDRaisedButton:
                    text: "Clear All Data"
                    md_bg_color: 0.85, 0.22, 0.25, 1
                    on_release: app.confirm_clear_data()
"""


class RootNav(MDBoxLayout):
    pass


class HomeScreen(Screen):
    pass


class AddScreen(Screen):
    selected_category = StringProperty("other")


class AIScreen(Screen):
    pass


class ScanScreen(Screen):
    pass


class HistoryScreen(Screen):
    pass


class SettingsScreen(Screen):
    pass


class FinanceApp(MDApp):
    def build(self):
        init_file_paths()

        self.config_data = load_config()
        self.theme_cls.primary_palette = "Teal"
        self.theme_cls.accent_palette = "Amber"
        self.theme_cls.theme_style = self.config_data.get("theme", "Light")

        self.current_screen_history: List[str] = []
        self.pending_transaction: Dict = {}
        self.selected_image_path: str = ""
        self._dialog = None

        Builder.load_string(KV)
        return RootNav()

    def on_start(self):
        if ANDROID:
            request_permissions(
                [
                    Permission.INTERNET,
                    Permission.READ_EXTERNAL_STORAGE,
                    Permission.WRITE_EXTERNAL_STORAGE,
                    Permission.CAMERA,
                ]
            )

        self._build_category_buttons()
        self.go_to_screen("home", push=False)
        self.refresh_all()

    # -------- Navigation --------

    def go_to_screen(self, name: str, push: bool = True):
        sm = self.root.ids.sm
        if push and sm.current != name:
            self.current_screen_history.append(sm.current)
        sm.current = name

        if name == "home":
            self.refresh_home()
        elif name == "history":
            self.refresh_history()
        elif name == "settings":
            self.refresh_settings()

    def go_back(self):
        sm = self.root.ids.sm
        if self.current_screen_history:
            sm.current = self.current_screen_history.pop()
        else:
            sm.current = "home"

    # -------- Utility --------

    def show_message(self, text: str):
        Snackbar(text=text).open()

    def currency(self) -> str:
        return self.config_data.get("currency", "฿")

    def money(self, amount: float) -> str:
        return f"{self.currency()} {amount:,.2f}"

    def refresh_all(self):
        self.refresh_home()
        self.refresh_history()
        self.refresh_settings()

    # -------- Add screen --------

    def _build_category_buttons(self):
        add_screen = self.root.ids.sm.get_screen("add")
        grid = add_screen.ids.category_grid

        if grid.children:
            return

        row = MDBoxLayout(adaptive_height=True, spacing=dp(8))
        count = 0
        for cat in CATEGORIES:
            btn = MDRaisedButton(
                text=cat.title(),
                on_release=lambda btn_obj, c=cat: self.select_category(c),
            )
            row.add_widget(btn)
            count += 1
            if count % 3 == 0:
                grid.add_widget(row)
                row = MDBoxLayout(adaptive_height=True, spacing=dp(8))

        if row.children:
            grid.add_widget(row)

        self.select_category("other")

    def select_category(self, category: str):
        add_screen = self.root.ids.sm.get_screen("add")
        add_screen.selected_category = category

        for row in add_screen.ids.category_grid.children:
            for btn in row.children:
                if btn.text.lower() == category:
                    btn.md_bg_color = CAT_COLORS.get(category, (0.2, 0.6, 0.5, 1))
                else:
                    btn.md_bg_color = (0.25, 0.25, 0.25, 0.25)

    def save_manual_transaction(self):
        add_screen = self.root.ids.sm.get_screen("add")
        amount_raw = add_screen.ids.add_amount.text.strip()
        note = add_screen.ids.add_note.text.strip()

        if not amount_raw:
            self.show_message("Please enter amount")
            return

        try:
            amount = float(amount_raw)
        except ValueError:
            self.show_message("Invalid amount")
            return

        add_transaction(amount, add_screen.selected_category, note)
        add_screen.ids.add_amount.text = ""
        add_screen.ids.add_note.text = ""

        self.show_message("Saved")
        self.refresh_all()
        self.go_to_screen("home")

    # -------- Home --------

    def refresh_home(self):
        home = self.root.ids.sm.get_screen("home")
        balance, income, expense = get_summary()

        home.ids.lbl_balance.text = self.money(balance)
        home.ids.lbl_income.text = self.money(income)
        home.ids.lbl_expense.text = self.money(expense)

        recent_box = home.ids.recent_box
        recent_box.clear_widgets()

        rows = load_data()[-5:][::-1]
        if not rows:
            recent_box.add_widget(
                MDLabel(text="No transactions yet", size_hint_y=None, height=dp(30))
            )
            return

        for tx in rows:
            recent_box.add_widget(self._transaction_card(tx))

    def _transaction_card(self, tx: Dict) -> MDCard:
        amount = float(tx.get("amount", 0))
        amount_color = (0.06, 0.72, 0.51, 1) if amount >= 0 else (0.9, 0.25, 0.25, 1)

        card = MDCard(
            size_hint_y=None, height=dp(80), radius=[10], elevation=1, padding=dp(10)
        )

        row = MDBoxLayout()
        left = MDBoxLayout(orientation="vertical")
        left.add_widget(
            MDLabel(text=f"[{tx.get('category', 'other')}] {tx.get('note', '')}")
        )
        left.add_widget(MDLabel(text=tx.get("date", ""), theme_text_color="Hint"))
        row.add_widget(left)
        row.add_widget(
            MDLabel(
                text=self.money(amount),
                halign="right",
                theme_text_color="Custom",
                text_color=amount_color,
            )
        )
        card.add_widget(row)
        return card

    # -------- AI text --------

    def process_ai_text(self):
        s = self.root.ids.sm.get_screen("ai")
        text = s.ids.ai_text.text.strip()
        api_key = self.config_data.get("api_key", "").strip()

        if not api_key:
            self.show_message("Set API key in Settings first")
            return
        if not text:
            self.show_message("Enter text")
            return

        s.ids.ai_btn.disabled = True
        s.ids.ai_btn.text = "Parsing..."
        ask_ai_text(text, api_key, self.on_ai_result)

    def on_ai_result(self, result: Dict, error: str):
        s = self.root.ids.sm.get_screen("ai")
        s.ids.ai_btn.disabled = False
        s.ids.ai_btn.text = "Parse with AI"

        if error:
            self.show_message(f"AI failed: {error[:120]}")
            return

        self.pending_transaction = {
            "amount": float(result.get("amount", 0)),
            "category": normalize_category(result.get("category", "other")),
            "note": (result.get("note") or "").strip(),
        }

        s.ids.ai_result_label.text = (
            f"Amount: {self.pending_transaction['amount']}\n"
            f"Category: {self.pending_transaction['category']}\n"
            f"Note: {self.pending_transaction['note']}"
        )
        s.ids.ai_result_card.opacity = 1
        s.ids.ai_result_card.disabled = False

    def hide_ai_result(self):
        s = self.root.ids.sm.get_screen("ai")
        s.ids.ai_result_card.opacity = 0
        s.ids.ai_result_card.disabled = True

    def confirm_ai_transaction(self):
        if not self.pending_transaction:
            return
        add_transaction(
            self.pending_transaction["amount"],
            self.pending_transaction["category"],
            self.pending_transaction["note"],
        )
        self.pending_transaction = {}
        self.hide_ai_result()
        self.root.ids.sm.get_screen("ai").ids.ai_text.text = ""

        self.show_message("Saved from AI")
        self.refresh_all()
        self.go_to_screen("home")

    # -------- Scan --------

    def pick_image(self):
        if not filechooser:
            self.show_message("File picker unavailable")
            return

        filechooser.open_file(
            on_selection=self.on_image_selected,
            filters=["*.jpg;*.jpeg;*.png;*.webp"],
            multiple=False,
        )

    def on_image_selected(self, selection):
        if selection:
            self.selected_image_path = selection[0]
            s = self.root.ids.sm.get_screen("scan")
            s.ids.selected_image_label.text = self.selected_image_path

    def scan_image(self):
        s = self.root.ids.sm.get_screen("scan")
        api_key = self.config_data.get("api_key", "").strip()

        if not api_key:
            self.show_message("Set API key in Settings first")
            return

        if not self.selected_image_path:
            self.show_message("Pick image first")
            return

        s.ids.scan_btn.disabled = True
        s.ids.scan_btn.text = "Analyzing..."
        ask_ai_image(self.selected_image_path, api_key, self.on_scan_result)

    def on_scan_result(self, result: Dict, error: str):
        s = self.root.ids.sm.get_screen("scan")
        s.ids.scan_btn.disabled = False
        s.ids.scan_btn.text = "Analyze with AI"

        if error:
            self.show_message(f"Scan failed: {error[:120]}")
            return

        self.pending_transaction = {
            "amount": float(result.get("amount", 0)),
            "category": normalize_category(result.get("category", "other")),
            "note": (result.get("note") or "").strip(),
        }

        s.ids.scan_result_label.text = (
            f"Amount: {self.pending_transaction['amount']}\n"
            f"Category: {self.pending_transaction['category']}\n"
            f"Note: {self.pending_transaction['note']}"
        )
        s.ids.scan_result_card.opacity = 1
        s.ids.scan_result_card.disabled = False

    def hide_scan_result(self):
        s = self.root.ids.sm.get_screen("scan")
        s.ids.scan_result_card.opacity = 0
        s.ids.scan_result_card.disabled = True

    def confirm_scan_transaction(self):
        if not self.pending_transaction:
            return
        add_transaction(
            self.pending_transaction["amount"],
            self.pending_transaction["category"],
            self.pending_transaction["note"],
        )
        self.pending_transaction = {}
        self.hide_scan_result()
        self.selected_image_path = ""

        s = self.root.ids.sm.get_screen("scan")
        s.ids.selected_image_label.text = "No image selected"

        self.show_message("Saved from scan")
        self.refresh_all()
        self.go_to_screen("home")

    # -------- History --------

    def refresh_history(self):
        s = self.root.ids.sm.get_screen("history")
        box = s.ids.history_box
        box.clear_widgets()

        rows = load_data()
        if not rows:
            box.add_widget(
                MDLabel(text="No transactions", size_hint_y=None, height=dp(32))
            )
            return

        for rev_i, tx in enumerate(rows[::-1]):
            real_i = len(rows) - 1 - rev_i
            box.add_widget(self._history_card(tx, real_i))

    def _history_card(self, tx: Dict, index: int) -> MDCard:
        amount = float(tx.get("amount", 0))
        amount_color = (0.06, 0.72, 0.51, 1) if amount >= 0 else (0.9, 0.25, 0.25, 1)

        card = MDCard(
            size_hint_y=None, height=dp(110), radius=[10], elevation=2, padding=dp(10)
        )
        col = MDBoxLayout(orientation="vertical")

        row1 = MDBoxLayout(size_hint_y=None, height=dp(32))
        row1.add_widget(
            MDLabel(
                text=f"[{tx.get('category', 'other')}] {tx.get('note', '')}", bold=True
            )
        )
        row1.add_widget(
            MDFlatButton(
                text="Delete", on_release=lambda x, i=index: self.delete_and_refresh(i)
            )
        )

        col.add_widget(row1)
        col.add_widget(
            MDLabel(
                text=tx.get("date", ""),
                theme_text_color="Hint",
                size_hint_y=None,
                height=dp(22),
            )
        )
        col.add_widget(
            MDLabel(
                text=self.money(amount),
                theme_text_color="Custom",
                text_color=amount_color,
            )
        )
        card.add_widget(col)
        return card

    def delete_and_refresh(self, index: int):
        delete_transaction(index)
        self.refresh_all()

    # -------- Settings --------

    def refresh_settings(self):
        s = self.root.ids.sm.get_screen("settings")
        s.ids.api_key.text = self.config_data.get("api_key", "")

    def save_api_key(self):
        s = self.root.ids.sm.get_screen("settings")
        self.config_data["api_key"] = s.ids.api_key.text.strip()
        save_config(self.config_data)
        self.show_message("API key saved")

    def set_theme(self, style: str):
        self.theme_cls.theme_style = style
        self.config_data["theme"] = style
        save_config(self.config_data)
        self.show_message(f"Theme set to {style}")

    def confirm_clear_data(self):
        self._dialog = MDDialog(
            title="Clear all data?",
            text="This will delete all transactions.",
            buttons=[
                MDFlatButton(
                    text="Cancel", on_release=lambda x: self._dialog.dismiss()
                ),
                MDFlatButton(text="Clear", on_release=lambda x: self._clear_data()),
            ],
        )
        self._dialog.open()

    def _clear_data(self):
        save_data([])
        if self._dialog:
            self._dialog.dismiss()
        self.refresh_all()
        self.show_message("All data cleared")


if __name__ == "__main__":
    FinanceApp().run()
