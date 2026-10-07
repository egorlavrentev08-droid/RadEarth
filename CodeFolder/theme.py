# theme.py - Rad Earth
# Версия: 1.0.0
# Тема оформления. Цвета, шрифты, вспомогательные функции для UI.

import tkinter as tk


# ==================== ЦВЕТА ====================

# Фон
BG_DARK = "#0a0a0c"        # Основной фон окон
BG_MID = "#15151a"          # Средний слой (статус-бар)
BG_PANEL = "#1a1a22"        # Панели, шапка
BG_CARD = "#20202a"         # Карточки, блоки
BG_HOVER = "#2a2a38"        # Наведение

# Текст
FG_MAIN = "#e8e8f0"         # Основной текст
FG_DIM = "#666677"          # Тусклый текст, подписи
FG_ACCENT = "#00ff88"       # Акцент — успех, положительное
FG_WARN = "#ffaa44"         # Предупреждение
FG_DANGER = "#ff5577"       # Опасность, ошибка
FG_BLUE = "#66ccff"         # Информация
FG_PURPLE = "#cc88ff"       # Магия, наука
FG_YELLOW = "#ffee66"       # Важное, редкости


# ==================== ШРИФТЫ ====================

FONT_TITLE = ("Consolas", 38, "bold")
FONT_HEADER = ("Consolas", 22, "bold")
FONT_SUB = ("Consolas", 16, "bold")
FONT_BODY = ("Consolas", 13)
FONT_BUTTON = ("Consolas", 14, "bold")
FONT_SMALL = ("Consolas", 11)
FONT_TINY = ("Consolas", 10)
FONT_MONO = ("Consolas", 12)


# ==================== РАЗМЕРЫ ====================

WINDOW_MIN_WIDTH = 1200
WINDOW_MIN_HEIGHT = 720

HEADER_HEIGHT = 64
STATUSBAR_HEIGHT = 80
BOTTOM_HEIGHT = 40

PADDING_SMALL = 5
PADDING_MEDIUM = 15
PADDING_LARGE = 30


# ==================== ХЕЛПЕРЫ ====================

def get_faction_color(faction_id):
    """Цвет фракции по её id."""
    colors = {
        'volya': '#5fff8f',
        'zavet': '#66ccff',
        'wagner': '#ffaa44',
        'roman': '#ff5577',
        'iskhod': '#cc88ff',
        'orda': '#ffee66',
        'bratva': '#ff8844',
        'neutral': '#aaaaaa',
        'player': '#00ff88',
    }
    return colors.get(faction_id, colors['neutral'])


def get_rep_color(rep_value):
    """Цвет репутации по значению."""
    if rep_value >= 50:
        return FG_ACCENT
    if rep_value >= 20:
        return FG_BLUE
    if rep_value <= -50:
        return FG_DANGER
    if rep_value <= -20:
        return FG_WARN
    return FG_DIM


def get_danger_color(danger_value):
    """Цвет по уровню опасности (0..100)."""
    if danger_value < 30:
        return FG_ACCENT
    if danger_value < 70:
        return FG_WARN
    return FG_DANGER


def setup_theme(root):
    """Базовая настройка темы при запуске."""
    root.configure(bg=BG_DARK)


# ==================== ДЕКОРАТОРЫ И УТИЛИТЫ ====================

def rgb_to_hex(r, g, b):
    """RGB в hex."""
    return f"#{r:02x}{g:02x}{b:02x}"


def hex_to_rgb(hex_color):
    """Hex в RGB."""
    h = hex_color.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def lighten(hex_color, amount=0.15):
    """Осветлить цвет."""
    r, g, b = hex_to_rgb(hex_color)
    r = min(255, int(r + (255 - r) * amount))
    g = min(255, int(g + (255 - g) * amount))
    b = min(255, int(b + (255 - b) * amount))
    return rgb_to_hex(r, g, b)


def darken(hex_color, amount=0.15):
    """Затемнить цвет."""
    r, g, b = hex_to_rgb(hex_color)
    r = max(0, int(r * (1 - amount)))
    g = max(0, int(g * (1 - amount)))
    b = max(0, int(b * (1 - amount)))
    return rgb_to_hex(r, g, b)


# ==================== СТИЛИЗОВАННЫЕ ВИДЖЕТЫ ====================

def make_styled_label(parent, text, font=FONT_BODY, fg=FG_MAIN, bg=BG_DARK,
                     anchor="w", wraplength=0):
    """Стандартная метка."""
    return tk.Label(parent, text=text, font=font, fg=fg, bg=bg,
                    anchor=anchor, justify="left", wraplength=wraplength)


def make_styled_button(parent, text, command, bg=BG_MID, fg=FG_MAIN,
                       font=FONT_BUTTON, **kwargs):
    """Стандартная кнопка."""
    return tk.Button(
        parent, text=text, command=command,
        bg=bg, fg=fg,
        activebackground=BG_HOVER, activeforeground="#ffffff",
        font=font, relief="flat", cursor="hand2",
        borderwidth=0, highlightthickness=0,
        padx=10, pady=6, **kwargs
    )


def make_styled_frame(parent, bg=BG_CARD, **kwargs):
    """Стандартный фрейм."""
    return tk.Frame(parent, bg=bg, **kwargs)


# ==================== ТЕКСТОВЫЕ КОНСТАНТЫ ====================

UI_TEXT = {
    'back': '🔙 Назад',
    'exit': '❌ Выход',
    'main_menu': '🏠 В меню',
    'confirm': 'Подтвердить',
    'cancel': 'Отмена',
    'close': 'Закрыть',
    'yes': 'Да',
    'no': 'Нет',
    'esc_hint': 'Esc — назад  |  F11 — оконный режим  |  Ctrl+Q — выход',
}


# ==================== ИКОНКИ ====================

ICON_MAIN_MENU = '🏠'
ICON_BACK = '🔙'
ICON_EXIT = '❌'
ICON_SUCCESS = '✅'
ICON_WARNING = '⚠️'
ICON_ERROR = '❌'
ICON_INFO = 'ℹ️'
ICON_MONEY = '☢️'
ICON_FRAGMENT = '☣️'
ICON_CRYSTAL = '💎'
ICON_LEVEL = '⚠️'
ICON_HEALTH = '❤️'
ICON_DAMAGE = '⚔️'
ICON_DEFENSE = '🛡'
ICON_PET = '🐾'
ICON_TRADER = '🧙'
ICON_FACTION = '🏰'
ICON_MAP = '🗺️'
ICON_RADIO = '📻'
ICON_SHOP = '🛒'
ICON_INVENTORY = '📦'
ICON_CHEST = '🎁'
ICON_EXPEDITION = '🎲'
ICON_HUNT = '🏹'
ICON_PROFILE = '👤'
ICON_ACHIEVEMENT = '🏅'
ICON_ADMIN = '👑'