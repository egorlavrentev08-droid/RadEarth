# screen_inventory.py - Rad Earth
# Версия: 1.0.0
# Экран инвентаря. Список предметов, экипировка, использование, продажа.

import tkinter as tk
from tkinter import messagebox

from theme import (
    BG_DARK, BG_MID, BG_PANEL, BG_CARD, BG_HOVER,
    FG_MAIN, FG_DIM, FG_ACCENT, FG_WARN, FG_DANGER, FG_BLUE, FG_PURPLE, FG_YELLOW,
    FONT_HEADER, FONT_SUB, FONT_BODY, FONT_SMALL, FONT_TINY,
)
from player_logic import (
    get_inventory_view, equip_item, unequip_item, use_item,
)
from economy_system import get_item


CATEGORY_ICONS = {
    'weapons': '🔫',
    'armor': '🛡',
    'junk': '🗑',
    'components': '⚙',
    'consumables': '💊',
    'misc': '📦',
}

CATEGORY_NAMES = {
    'weapons': 'ОРУЖИЕ',
    'armor': 'БРОНЯ',
    'consumables': 'РАСХОДНИКИ',
    'components': 'КОМПОНЕНТЫ',
    'junk': 'ХЛАМ',
    'misc': 'ПРОЧЕЕ',
}


class InventoryScreen:
    """Экран инвентаря."""

    def __init__(self, app):
        self.app = app
        self._render()

    # ==================== РЕНДЕР ====================

    def _render(self):
        content = self.app.make_screen(
            "📦 ИНВЕНТАРЬ",
            color=FG_BLUE,
            subtitle=self._subtitle()
        )

        main = tk.Frame(content, bg=BG_DARK)
        main.pack(fill="both", expand=True)

        # Левая колонка — экипировка
        left = tk.Frame(main, bg=BG_CARD, width=340)
        left.pack(side="left", fill="y", padx=(0, 15))
        left.pack_propagate(False)
        self._render_equipped(left)

        # Правая колонка — инвентарь
        right = tk.Frame(main, bg=BG_DARK)
        right.pack(side="left", fill="both", expand=True)
        self._render_inventory(right)

    def _subtitle(self):
        p = self.app.player
        return f"☢️ {int(p.radcoins)} RC   |   ☣️ {p.radfragments} RF"

    # ==================== ЭКИПИРОВКА ====================

    def _render_equipped(self, parent):
        from utils import get_equipped
        equipped = get_equipped(self.app.player)

        tk.Label(parent, text="🟢 ЭКИПИРОВАНО",
                 bg=BG_CARD, fg=FG_ACCENT,
                 font=FONT_SUB).pack(anchor="w", padx=15, pady=(15, 5))

        # Оружие
        weapon = equipped.get('weapon')
        weapon_frame = tk.Frame(parent, bg=BG_PANEL)
        weapon_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(weapon_frame, text="⚔ ОРУЖИЕ",
                 bg=BG_PANEL, fg=FG_DIM,
                 font=FONT_SMALL).pack(anchor="w", padx=10, pady=(8, 3))

        if weapon:
            item = get_item(weapon)
            name = item.get('name', weapon) if item else weapon
            dmg = item.get('damage', '?') if item else '?'
            tk.Label(weapon_frame, text=name,
                     bg=BG_PANEL, fg=FG_MAIN,
                     font=FONT_BODY).pack(anchor="w", padx=10)
            tk.Label(weapon_frame, text=f"Урон: {dmg}",
                     bg=BG_PANEL, fg=FG_DIM,
                     font=FONT_SMALL).pack(anchor="w", padx=10)
            self.app.make_button(weapon_frame, "Снять",
                                 lambda: self._unequip('weapon'),
                                 bg=BG_MID, fg=FG_WARN,
                                 font=FONT_SMALL).pack(anchor="w", padx=10, pady=(5, 8))
        else:
            tk.Label(weapon_frame, text="— Пусто —",
                     bg=BG_PANEL, fg=FG_DIM,
                     font=FONT_SMALL).pack(anchor="w", padx=10, pady=(0, 10))

        # Броня
        armor = equipped.get('armor')
        armor_frame = tk.Frame(parent, bg=BG_PANEL)
        armor_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(armor_frame, text="🛡 БРОНЯ",
                 bg=BG_PANEL, fg=FG_DIM,
                 font=FONT_SMALL).pack(anchor="w", padx=10, pady=(8, 3))

        if armor:
            item = get_item(armor)
            name = item.get('name', armor) if item else armor
            defense = item.get('defense', '?') if item else '?'
            tk.Label(armor_frame, text=name,
                     bg=BG_PANEL, fg=FG_MAIN,
                     font=FONT_BODY).pack(anchor="w", padx=10)
            tk.Label(armor_frame, text=f"Защита: {defense}",
                     bg=BG_PANEL, fg=FG_DIM,
                     font=FONT_SMALL).pack(anchor="w", padx=10)
            self.app.make_button(armor_frame, "Снять",
                                 lambda: self._unequip('armor'),
                                 bg=BG_MID, fg=FG_WARN,
                                 font=FONT_SMALL).pack(anchor="w", padx=10, pady=(5, 8))
        else:
            tk.Label(armor_frame, text="— Пусто —",
                     bg=BG_PANEL, fg=FG_DIM,
                     font=FONT_SMALL).pack(anchor="w", padx=10, pady=(0, 10))

        # Питомец
        pet = self.app.player.pet
        pet_frame = tk.Frame(parent, bg=BG_CARD)
        pet_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(pet_frame, text=f"🐾 Питомец: {pet or '—'}",
                 bg=BG_CARD, fg=FG_DIM,
                 font=FONT_SMALL).pack(anchor="w", padx=10)

    # ==================== ИНВЕНТАРЬ ====================

    def _render_inventory(self, parent):
        items = get_inventory_view(self.app.player_id)

        if not items:
            tk.Label(parent, text="📦 Инвентарь пуст",
                     bg=BG_DARK, fg=FG_DIM,
                     font=FONT_HEADER).pack(pady=80)
            return

        # Группируем по категории
        by_cat = {}
        for item in items:
            cat = item.get('category', 'misc')
            by_cat.setdefault(cat, []).append(item)

        # Скроллируемая область
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

            # Заголовок категории
            cat_frame = tk.Frame(inner, bg=BG_PANEL)
            cat_frame.pack(fill="x", padx=5, pady=(10, 3))

            icon = CATEGORY_ICONS.get(cat, '📦')
            name = CATEGORY_NAMES.get(cat, cat.upper())
            tk.Label(cat_frame, text=f"{icon}  {name}",
                     bg=BG_PANEL, fg=FG_YELLOW,
                     font=FONT_SUB).pack(anchor="w", padx=15, pady=8)

            # Предметы
            for item in sorted(by_cat[cat], key=lambda x: x.get('name', '')):
                self._render_item_row(inner, item)

    def _render_item_row(self, parent, item):
        row = tk.Frame(parent, bg=BG_CARD)
        row.pack(fill="x", padx=15, pady=2)

        # Иконка и имя
        icon = CATEGORY_ICONS.get(item.get('category'), '📦')
        name = item.get('name', item.get('id', '???'))
        count = item.get('count', 0)

        tk.Label(row, text=f"{icon} {name}",
                 bg=BG_CARD, fg=FG_MAIN,
                 font=FONT_BODY, anchor="w").pack(
            side="left", padx=10, pady=6, fill="x", expand=True)

        # Количество
        tk.Label(row, text=f"x{count}",
                 bg=BG_CARD, fg=FG_DIM,
                 font=FONT_BODY).pack(side="left", padx=5)

        # Кнопки
        btn_frame = tk.Frame(row, bg=BG_CARD)
        btn_frame.pack(side="right", padx=5)

        cat = item.get('category')

        # Кнопка экипировки
        if cat in ('weapons', 'armor'):
            self.app.make_button(
                btn_frame, "Надеть",
                lambda i=item['id']: self._equip(i),
                bg=BG_MID, fg=FG_ACCENT,
                font=FONT_SMALL,
            ).pack(side="left", padx=2)

        # Кнопка использования (расходники)
        if cat == 'consumables':
            self.app.make_button(
                btn_frame, "Использовать",
                lambda i=item['id']: self._use(i),
                bg=BG_MID, fg=FG_PURPLE,
                font=FONT_SMALL,
            ).pack(side="left", padx=2)

        # Кнопка продажи
        self.app.make_button(
            btn_frame, f"💰 {item.get('price_sell', 1)}",
            lambda i=item['id']: self._sell(i),
            bg=BG_MID, fg=FG_YELLOW,
            font=FONT_SMALL,
        ).pack(side="left", padx=2)

    # ==================== ДЕЙСТВИЯ ====================

    def _equip(self, item_id):
        result = equip_item(self.app.player_id, item_id)
        if result.get('ok'):
            messagebox.showinfo("Экипировка", result['message'])
            self.app.refresh_player()
            self._render()
        else:
            messagebox.showwarning("Экипировка", result.get('message', 'Ошибка'))

    def _unequip(self, slot):
        result = unequip_item(self.app.player_id, slot)
        if result.get('ok'):
            messagebox.showinfo("Экипировка", result['message'])
            self.app.refresh_player()
            self._render()
        else:
            messagebox.showwarning("Экипировка", result.get('message', 'Ошибка'))

    def _use(self, item_id):
        result = use_item(self.app.player_id, item_id)
        if result.get('ok'):
            messagebox.showinfo("Использование", result['message'])
            self.app.refresh_player()
            self._render()
        else:
            messagebox.showwarning("Использование", result.get('message', 'Ошибка'))

    def _sell(self, item_id):
        count = self._ask_count("Продать сколько?")
        if count <= 0:
            return

        from economy_system import sell_item
        trader_faction = self._get_trader_faction()
        result = sell_item(self.app.player_id, item_id, count, trader_faction)

        if result.get('ok'):
            messagebox.showinfo("Продажа", result['message'])
            self.app.refresh_player()
            self._render()
        else:
            messagebox.showwarning("Продажа", result.get('message', 'Ошибка'))

    def _ask_count(self, prompt):
        from tkinter import simpledialog
        return simpledialog.askinteger(
            "Количество", prompt,
            initialvalue=1, minvalue=1, maxvalue=999
        ) or 0

    def _get_trader_faction(self):
        """Фракция текущего торговца (если в локации есть)."""
        from map_engine import get_location
        loc = get_location(self.app.player.current_location)
        if loc and loc.controller_faction_id:
            return loc.controller_faction_id
        return None