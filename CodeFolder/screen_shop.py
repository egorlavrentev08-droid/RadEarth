# screen_shop.py - Rad Earth
# Версия: 1.0.0
# Экран магазина. Товары торговца, покупка, продажа, репутационные цены.

import tkinter as tk
from tkinter import messagebox
from datetime import datetime
import json

from theme import (
    BG_DARK, BG_MID, BG_PANEL, BG_CARD, BG_HOVER,
    FG_MAIN, FG_DIM, FG_ACCENT, FG_WARN, FG_DANGER, FG_BLUE, FG_PURPLE, FG_YELLOW,
    FONT_HEADER, FONT_SUB, FONT_BODY, FONT_SMALL, FONT_TINY,
    get_faction_color,
)
from economy_system import (
    get_trader_stock, get_price_for_player,
    buy_item, sell_item, get_item, get_all_items,
)
from map_engine import get_location
from faction_engine import get_faction, get_player_rep


CATEGORY_NAMES = {
    'weapons': '🔫 ОРУЖИЕ',
    'armor': '🛡 БРОНЯ',
    'consumables': '💊 РАСХОДНИКИ',
    'components': '⚙️ КОМПОНЕНТЫ',
    'junk': '🗑 ХЛАМ',
    'misc': '📦 ПРОЧЕЕ',
}


class ShopScreen:
    """Экран торговца."""

    def __init__(self, app, npc_id=None):
        self.app = app
        self.npc_id = npc_id
        self.tab = 'buy'  # buy / sell
        self._render()

    # ==================== РЕНДЕР ====================

    def _render(self):
        loc = get_location(self.app.player.current_location)
        faction_id = loc.controller_faction_id if loc else None

        content = self.app.make_screen(
            "🛒 ТОРГОВЕЦ",
            color=FG_PURPLE,
            subtitle=self._subtitle(faction_id)
        )

        # Вкладки
        tabs = tk.Frame(content, bg=BG_DARK)
        tabs.pack(fill="x", pady=(0, 10))

        for tab_id, tab_name in [
            ('buy', '💰 Купить'),
            ('sell', '💸 Продать'),
        ]:
            is_active = (self.tab == tab_id)
            bg = BG_HOVER if is_active else BG_MID
            fg = FG_PURPLE if is_active else FG_MAIN

            self.app.make_button(
                tabs, tab_name,
                lambda tid=tab_id: self._switch_tab(tid),
                bg=bg, fg=fg, font=FONT_BODY,
            ).pack(side="left", padx=5)

        # Контент вкладки
        if self.tab == 'buy':
            self._render_buy(content, faction_id)
        else:
            self._render_sell(content, faction_id)

    def _subtitle(self, faction_id):
        p = self.app.player
        text = f"☢️ {int(p.radcoins)} RC"
        if faction_id:
            rep = get_player_rep(p, faction_id)
            from config import get_rep_tier
            _, tier = get_rep_tier(rep)
            f = get_faction(faction_id)
            fname = f.name if f else faction_id
            text += f"   |   {fname}: {tier} ({rep:+d})"
        return text

    def _switch_tab(self, tab_id):
        self.tab = tab_id
        self._render()

    # ==================== ПОКУПКА ====================

    def _render_buy(self, parent, faction_id):
        stock = get_trader_stock(faction_id, trader_type='mixed')

        if not stock:
            tk.Label(parent, text="Товаров нет",
                     bg=BG_DARK, fg=FG_DIM,
                     font=FONT_BODY).pack(pady=60)
            return

        # Группируем по категории
        by_cat = {}
        for item in stock:
            cat = item.get('category', 'misc')
            by_cat.setdefault(cat, []).append(item)

        # Скролл
        canvas = tk.Canvas(parent, bg=BG_DARK, highlightthickness=0)
        scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG_DARK)

        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        order = ['weapons', 'armor', 'consumables', 'components', 'junk', 'misc']

        for cat in order:
            if cat not in by_cat:
                continue

            # Заголовок
            cat_frame = tk.Frame(inner, bg=BG_PANEL)
            cat_frame.pack(fill="x", padx=5, pady=(10, 3))
            tk.Label(cat_frame, text=CATEGORY_NAMES.get(cat, cat.upper()),
                     bg=BG_PANEL, fg=FG_YELLOW,
                     font=FONT_SUB).pack(anchor="w", padx=15, pady=8)

            for item in by_cat[cat]:
                self._render_buy_row(inner, item, faction_id)

    def _render_buy_row(self, parent, item, faction_id):
        item_id = item['id']
        price_info = get_price_for_player(
            self.app.player, item_id, faction_id, buy=True
        )

        if not price_info:
            return

        final_price = price_info['final']
        base_price = price_info['base']
        rep_mult = price_info['mult']

        can_afford = self.app.player.radcoins >= final_price
        level_ok = self.app.player.level >= item.get('level_required', 1)

        # Цвет карточки
        bg = BG_CARD if (can_afford and level_ok) else "#2a1a1a"

        card = tk.Frame(parent, bg=bg)
        card.pack(fill="x", padx=15, pady=2)

        # Левая часть — название и цена
        info = tk.Frame(card, bg=bg)
        info.pack(side="left", fill="x", expand=True, padx=10, pady=8)

        tk.Label(info, text=item.get('name', item_id),
                 bg=bg, fg=FG_MAIN,
                 font=FONT_BODY, anchor="w").pack(anchor="w")

        # Цена + модификатор
        price_text = f"☢️ {final_price}"
        if rep_mult != 1.0:
            sign = "↑" if rep_mult > 1 else "↓"
            price_text += f"   ({sign}{int(abs(rep_mult - 1) * 100)}%)"

        price_color = FG_ACCENT if can_afford else FG_DANGER
        if rep_mult > 1.0:
            price_color = FG_WARN

        tk.Label(info, text=price_text,
                 bg=bg, fg=price_color,
                 font=FONT_SMALL, anchor="w").pack(anchor="w")

        # Требование уровня
        if not level_ok:
            tk.Label(info, text=f"⛔ Нужен {item.get('level_required')} уровень",
                     bg=bg, fg=FG_DANGER,
                     font=FONT_SMALL, anchor="w").pack(anchor="w")

        # Кнопка покупки
        if level_ok and can_afford:
            self.app.make_button(
                card, "Купить",
                lambda i=item_id, f=faction_id: self._buy(i, f),
                bg="#1a3a1a", fg=FG_ACCENT,
                font=FONT_SMALL,
            ).pack(side="right", padx=10)
        elif not level_ok:
            tk.Label(card, text="🔒",
                     bg=bg, fg=FG_DANGER,
                     font=FONT_BODY).pack(side="right", padx=10)
        else:
            tk.Label(card, text="💸",
                     bg=bg, fg=FG_DANGER,
                     font=FONT_BODY).pack(side="right", padx=10)

    # ==================== ПРОДАЖА ====================

    def _render_sell(self, parent, faction_id):
        from player_logic import get_inventory_view
        items = get_inventory_view(self.app.player_id)

        if not items:
            tk.Label(parent, text="Нечего продавать",
                     bg=BG_DARK, fg=FG_DIM,
                     font=FONT_BODY).pack(pady=60)
            return

        # Скролл
        canvas = tk.Canvas(parent, bg=BG_DARK, highlightthickness=0)
        scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG_DARK)

        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for item in items:
            self._render_sell_row(inner, item, faction_id)

    def _render_sell_row(self, parent, item, faction_id):
        item_id = item['id']
        count = item['count']

        price_info = get_price_for_player(
            self.app.player, item_id, faction_id, buy=False
        )
        if not price_info:
            return

        final_price = price_info['final']
        rep_mult = price_info['mult']

        card = tk.Frame(parent, bg=BG_CARD)
        card.pack(fill="x", padx=15, pady=2)

        info = tk.Frame(card, bg=BG_CARD)
        info.pack(side="left", fill="x", expand=True, padx=10, pady=8)

        tk.Label(info, text=f"{item.get('name', item_id)}  x{count}",
                 bg=BG_CARD, fg=FG_MAIN,
                 font=FONT_BODY, anchor="w").pack(anchor="w")

        price_text = f"💰 {final_price} RC / шт"
        if rep_mult != 1.0:
            sign = "↑" if rep_mult > 1 else "↓"
            price_text += f"   ({sign}{int(abs(rep_mult - 1) * 100)}%)"

        price_color = FG_ACCENT if rep_mult >= 1.0 else FG_WARN
        tk.Label(info, text=price_text,
                 bg=BG_CARD, fg=price_color,
                 font=FONT_SMALL, anchor="w").pack(anchor="w")

        # Кнопки
        btn_frame = tk.Frame(card, bg=BG_CARD)
        btn_frame.pack(side="right", padx=10)

        self.app.make_button(
            btn_frame, "Продать 1",
            lambda i=item_id, f=faction_id: self._sell(i, 1, f),
            bg=BG_MID, fg=FG_YELLOW,
            font=FONT_SMALL,
        ).pack(side="left", padx=2)

        if count > 1:
            self.app.make_button(
                btn_frame, f"Продать всё ({count})",
                lambda i=item_id, c=count, f=faction_id: self._sell(i, c, f),
                bg=BG_MID, fg=FG_ACCENT,
                font=FONT_SMALL,
            ).pack(side="left", padx=2)

    # ==================== ДЕЙСТВИЯ ====================

    def _buy(self, item_id, faction_id):
        from tkinter import simpledialog
        count = simpledialog.askinteger(
            "Купить", "Сколько?",
            initialvalue=1, minvalue=1, maxvalue=999
        )
        if not count:
            return

        result = buy_item(self.app.player_id, item_id, count, faction_id)

        if result.get('ok'):
            messagebox.showinfo("Покупка", result['message'])
            self.app.refresh_player()
            self._render()
        else:
            messagebox.showwarning("Покупка", result.get('message', 'Ошибка'))

    def _sell(self, item_id, count, faction_id):
        result = sell_item(self.app.player_id, item_id, count, faction_id)

        if result.get('ok'):
            messagebox.showinfo("Продажа", result['message'])
            self.app.refresh_player()
            self._render()
        else:
            messagebox.showwarning("Продажа", result.get('message', 'Ошибка'))