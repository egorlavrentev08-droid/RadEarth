# screen_map.py - Rad Earth
# Версия: 1.0.0
# Экран карты. Текущая локация, доступные переходы, NPC рядом, действия.

import tkinter as tk
from tkinter import messagebox

from theme import (
    BG_DARK, BG_MID, BG_PANEL, BG_CARD, BG_HOVER,
    FG_MAIN, FG_DIM, FG_ACCENT, FG_WARN, FG_DANGER, FG_BLUE, FG_PURPLE, FG_YELLOW,
    FONT_HEADER, FONT_SUB, FONT_BODY, FONT_SMALL, FONT_TINY,
    get_faction_color,
)
from map_engine import (
    get_location_view, get_connected_locations,
    travel_player, get_npcs_in_location, get_named_npcs_in_location,
    get_traders_in_location, count_npcs_by_location,
)
from npc_engine import get_npc_view
from player_logic import get_player_faction


LOCATION_TYPE_ICONS = {
    'wild': '🌿',
    'city': '🏙️',
    'abandoned_city': '🏚️',
    'military_base': '🏴',
    'settlement': '🏘️',
    'business': '🏭',
    'lab': '🧪',
    'forest': '🌲',
    'swamp': '🌊',
    'mountain': '⛰️',
    'underground': '🕳️',
    'anomaly': '✨',
}


class MapScreen:
    """Экран карты."""

    def __init__(self, app):
        self.app = app
        self._render()

    # ==================== РЕНДЕР ====================

    def _render(self):
        loc = get_location_view(
            self.app.player.current_location,
            player_id=self.app.player_id
        )

        if not loc:
            messagebox.showerror("Карта", "Локация не найдена")
            self.app.pop_screen()
            return

        content = self.app.make_screen(
            "🗺️ КАРТА",
            color=FG_BLUE,
            subtitle=self._subtitle(loc)
        )

        main = tk.Frame(content, bg=BG_DARK)
        main.pack(fill="both", expand=True)

        # Левая колонка — текущая локация
        left = tk.Frame(main, bg=BG_CARD, width=420)
        left.pack(side="left", fill="both", padx=(0, 15))
        left.pack_propagate(False)
        self._render_current_location(left, loc)

        # Правая колонка — соседние локации
        right = tk.Frame(main, bg=BG_DARK)
        right.pack(side="left", fill="both", expand=True)
        self._render_connections(right)

    def _subtitle(self, loc):
        parts = [loc['name']]
        if loc.get('controller'):
            parts.append(f"контроль: {loc['controller']['name']}")
        return "  |  ".join(parts)

    # ==================== ТЕКУЩАЯ ЛОКАЦИЯ ====================

    def _render_current_location(self, parent, loc):
        # Заголовок
        icon = LOCATION_TYPE_ICONS.get(loc['type'], '📍')
        tk.Label(parent, text=f"{icon} {loc['name']}",
                 bg=BG_CARD, fg=FG_MAIN,
                 font=FONT_HEADER).pack(anchor="w", padx=15, pady=(15, 3))

        # Контроллер
        if loc.get('controller'):
            tk.Label(parent, text=f"🏴 Под контролем: {loc['controller']['name']}",
                     bg=BG_CARD,
                     fg=loc['controller'].get('color', FG_MAIN),
                     font=FONT_BODY).pack(anchor="w", padx=15, pady=(0, 10))
        else:
            tk.Label(parent, text="🌿 Нейтральная территория",
                     bg=BG_CARD, fg=FG_DIM,
                     font=FONT_BODY).pack(anchor="w", padx=15, pady=(0, 10))

        # Описание
        tk.Label(parent, text=loc.get('desc', ''),
                 bg=BG_CARD, fg=FG_DIM,
                 font=FONT_BODY,
                 wraplength=380, justify="left").pack(anchor="w", padx=15, pady=5)

        # Что есть в локации
        tk.Frame(parent, bg=BG_MID, height=1).pack(fill="x", padx=15, pady=10)

        tk.Label(parent, text="ЧТО ЕСТЬ:",
                 bg=BG_CARD, fg=FG_DIM,
                 font=FONT_SMALL).pack(anchor="w", padx=15, pady=(0, 3))

        features = []
        if loc.get('has_trader'): features.append("🧙 Торговец")
        if loc.get('has_business'): features.append("🏭 Бизнес")
        if loc.get('has_shops'): features.append("🛒 Магазины")
        if loc.get('has_medbay'): features.append("💉 Медпункт")
        if loc.get('has_barracks'): features.append("🛏️ Казармы")

        if features:
            for feat in features:
                tk.Label(parent, text=f"  {feat}",
                         bg=BG_CARD, fg=FG_MAIN,
                         font=FONT_BODY).pack(anchor="w", padx=15)
        else:
            tk.Label(parent, text="  — Только руины —",
                     bg=BG_CARD, fg=FG_DIM,
                     font=FONT_SMALL).pack(anchor="w", padx=15)

        # Опасность и множители
        tk.Frame(parent, bg=BG_MID, height=1).pack(fill="x", padx=15, pady=10)

        tk.Label(parent, text="ХАРАКТЕРИСТИКИ:",
                 bg=BG_CARD, fg=FG_DIM,
                 font=FONT_SMALL).pack(anchor="w", padx=15, pady=(0, 3))

        stats = [
            ("☢️ Опасность", f"+{loc['danger_bonus']}"),
            ("💰 RC множитель", f"x{loc['rc_mult']}"),
            ("☣️ RF множитель", f"x{loc['rf_mult']}"),
            ("⚠️ Опыт множитель", f"x{loc['exp_mult']}"),
        ]
        for label, value in stats:
            row = tk.Frame(parent, bg=BG_CARD)
            row.pack(fill="x", padx=15, pady=1)
            tk.Label(row, text=label, bg=BG_CARD, fg=FG_DIM,
                     font=FONT_SMALL).pack(side="left")
            tk.Label(row, text=value, bg=BG_CARD, fg=FG_MAIN,
                     font=FONT_SMALL).pack(side="right")

        # NPC в локации
        tk.Frame(parent, bg=BG_MID, height=1).pack(fill="x", padx=15, pady=10)

        npc_count = count_npcs_by_location(loc['id'])
        tk.Label(parent, text=f"👥 NPC: {npc_count}",
                 bg=BG_CARD, fg=FG_DIM,
                 font=FONT_SMALL).pack(anchor="w", padx=15, pady=(0, 3))

        # Список ключевых NPC
        named_npcs = get_named_npcs_in_location(loc['id'])
        if named_npcs:
            for npc in named_npcs[:4]:
                row = tk.Frame(parent, bg=BG_CARD)
                row.pack(fill="x", padx=15, pady=1)

                name_text = f"👤 {npc.name}"
                if npc.callsign:
                    name_text += f" «{npc.callsign}»"
                if npc.role == 'leader':
                    name_text = "👑 " + name_text
                elif npc.role == 'advisor':
                    name_text = "📜 " + name_text

                tk.Label(row, text=name_text,
                         bg=BG_CARD, fg=FG_YELLOW,
                         font=FONT_SMALL, anchor="w").pack(side="left")

                # Кнопка поговорить
                self.app.make_button(
                    row, "💬",
                    lambda n=npc: self._talk_to(n.id),
                    bg=BG_MID, fg=FG_ACCENT,
                    font=FONT_TINY,
                    pad=(8, 2),
                ).pack(side="right", padx=3)

        # Кнопки действий
        tk.Frame(parent, bg=BG_MID, height=1).pack(fill="x", padx=15, pady=10)

        actions = tk.Frame(parent, bg=BG_CARD)
        actions.pack(fill="x", padx=15, pady=(0, 15))

        if loc.get('has_trader') or get_traders_in_location(loc['id']):
            self.app.make_button(
                actions, "🧙 ТОРГОВЕЦ",
                self._open_trader,
                bg=BG_MID, fg=FG_PURPLE,
                font=FONT_SMALL,
            ).pack(fill="x", pady=2)

        if loc.get('has_business'):
            self.app.make_button(
                actions, "🏭 БИЗНЕС",
                self._open_business,
                bg=BG_MID, fg=FG_BLUE,
                font=FONT_SMALL,
            ).pack(fill="x", pady=2)

    # ==================== СОСЕДНИЕ ЛОКАЦИИ ====================

    def _render_connections(self, parent):
        connections = get_connected_locations(
            self.app.player.current_location,
            player_id=self.app.player_id
        )

        tk.Label(parent, text="🧭 ДОСТУПНЫЕ ПЕРЕХОДЫ",
                 bg=BG_DARK, fg=FG_YELLOW,
                 font=FONT_SUB).pack(anchor="w", pady=(0, 10))

        if not connections:
            tk.Label(parent, text="Нет доступных переходов",
                     bg=BG_DARK, fg=FG_DIM,
                     font=FONT_BODY).pack(pady=40)
            return

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

        for conn in connections:
            self._render_connection_card(inner, conn)

    def _render_connection_card(self, parent, conn):
        card_bg = BG_CARD if conn['can_enter'] else "#2a1a1a"

        card = tk.Frame(parent, bg=card_bg)
        card.pack(fill="x", pady=4, padx=5)

        # Верхняя строка — имя и иконка
        top = tk.Frame(card, bg=card_bg)
        top.pack(fill="x", padx=15, pady=(10, 2))

        icon = LOCATION_TYPE_ICONS.get(conn['type'], '📍')
        tk.Label(top, text=f"{icon} {conn['name']}",
                 bg=card_bg, fg=FG_MAIN,
                 font=FONT_SUB).pack(side="left")

        # Контроллер
        if conn.get('controller'):
            tk.Label(top, text=f"🏴 {conn['controller']}",
                     bg=card_bg,
                     fg=conn.get('controller_color', FG_DIM),
                     font=FONT_SMALL).pack(side="right")

        # Описание
        tk.Label(card, text=conn.get('desc', ''),
                 bg=card_bg, fg=FG_DIM,
                 font=FONT_SMALL,
                 wraplength=600, justify="left",
                 anchor="w").pack(anchor="w", padx=15, pady=(0, 5))

        # Нижняя строка — действие
        bottom = tk.Frame(card, bg=card_bg)
        bottom.pack(fill="x", padx=15, pady=(5, 10))

        if not conn['can_enter']:
            tk.Label(bottom, text=f"⛔ {conn['reason']}",
                     bg=card_bg, fg=FG_DANGER,
                     font=FONT_SMALL).pack(side="left")
        else:
            tk.Label(bottom, text=f"⏱ {conn.get('travel_time', 30)} мин",
                     bg=card_bg, fg=FG_DIM,
                     font=FONT_SMALL).pack(side="left")

            self.app.make_button(
                bottom, "🚶 ПЕРЕЙТИ",
                lambda cid=conn['id']: self._travel(cid),
                bg="#1a3a1a", fg=FG_ACCENT,
                font=FONT_SMALL,
            ).pack(side="right")

    # ==================== ДЕЙСТВИЯ ====================

    def _travel(self, to_location_id):
        result = travel_player(self.app.player_id, to_location_id)
        if result.get('ok'):
            messagebox.showinfo("Переход", result['message'])
            self.app.refresh_player()
            self._render()
        else:
            messagebox.showwarning("Переход", result.get('message', 'Ошибка'))

    def _talk_to(self, npc_id):
        from screen_dialog import DialogScreen
        DialogScreen(self.app, npc_id)

    def _open_trader(self):
        messagebox.showinfo("Торговец", "Торговля в разработке")

    def _open_business(self):
        messagebox.showinfo("Бизнес", "Бизнес в разработке")