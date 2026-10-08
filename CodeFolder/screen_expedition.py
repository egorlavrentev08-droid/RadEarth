# screen_expedition.py - Rad Earth
# Версия: 1.0.0
# Экран вылазки. События, выбор, лог, прогресс опасности, диалоги, финал.

import tkinter as tk
from tkinter import messagebox
import random

from theme import (
    BG_DARK, BG_MID, BG_PANEL, BG_CARD, BG_HOVER,
    FG_MAIN, FG_DIM, FG_ACCENT, FG_WARN, FG_DANGER, FG_BLUE, FG_PURPLE, FG_YELLOW,
    FONT_HEADER, FONT_SUB, FONT_BODY, FONT_SMALL, FONT_TINY,
)
from game_logic import (
    start_expedition, expedition_next_event, expedition_choice,
)
from database import get_players_session, Player


class ExpeditionScreen:
    """Экран вылазки."""

    def __init__(self, app):
        self.app = app
        self.state = None
        self._start()

    # ==================== СТАРТ ====================

    def _start(self):
        result = start_expedition(self.app.player_id)
        if not result.get('ok'):
            messagebox.showwarning("Вылазка", result.get('message', 'Ошибка'))
            self.app.pop_screen()
            return

        self.state = result['state']
        self.state['current_event'] = None
        self._render()

    # ==================== РЕНДЕР ====================

    def _render(self):
        s = self.state

        if not s['alive']:
            self._render_death()
            return
        if s['visited'] >= s['max_events']:
            self._render_end()
            return

        content = self.app.make_screen(
            "🎲 ВЫЛАЗКА",
            color=FG_ACCENT,
            subtitle=f"Шаг {s['visited'] + 1}/{s['max_events']}  |  {s['location_name']}"
        )

        # Опасность
        self._render_danger_bar(content)

        # Журнал
        self._render_log(content)

        # Текущее событие
        if s['current_event'] is None:
            s['current_event'] = expedition_next_event(
                self.app.player_id, s
            )

        self._render_event(content, s['current_event'])

    def _render_danger_bar(self, parent):
        s = self.state
        dl = min(100, s['danger'])

        if dl < 30:
            dc = FG_ACCENT
        elif dl < 70:
            dc = FG_WARN
        else:
            dc = FG_DANGER

        bar_frame = tk.Frame(parent, bg=BG_PANEL, height=32)
        bar_frame.pack(fill="x", pady=(0, 10))
        bar_frame.pack_propagate(False)

        tk.Label(bar_frame, text=f"  ☢️ ОПАСНОСТЬ: {dl}%",
                 bg=BG_PANEL, fg=dc,
                 font=FONT_SMALL).pack(side="left", pady=6)

        fill = tk.Frame(bar_frame, bg=dc, height=12, width=int(dl * 8))
        fill.pack(side="left", pady=10, padx=5)

        # Итого собрано
        totals = f"☢️ {s['total_rc']}   ☣️ {s['total_rf']}   ⚠️ {s['total_exp']}"
        tk.Label(bar_frame, text=totals,
                 bg=BG_PANEL, fg=FG_DIM,
                 font=FONT_SMALL).pack(side="right", padx=15)

    def _render_log(self, parent):
        s = self.state
        log_frame = tk.Frame(parent, bg=BG_PANEL)
        log_frame.pack(fill="x", pady=(0, 10))

        tk.Label(log_frame, text="📜 ЖУРНАЛ",
                 bg=BG_PANEL, fg=FG_DIM,
                 font=FONT_SMALL).pack(anchor="w", padx=15, pady=(6, 2))

        for line in s['log'][-5:]:
            tk.Label(log_frame, text=line,
                     bg=BG_PANEL, fg=FG_MAIN,
                     font=FONT_SMALL,
                     wraplength=900, justify="left",
                     anchor="w").pack(anchor="w", padx=15, pady=1)

        if not s['log']:
            tk.Label(log_frame, text="— Пока тихо —",
                     bg=BG_PANEL, fg=FG_DIM,
                     font=FONT_SMALL).pack(anchor="w", padx=15, pady=1)

        tk.Label(log_frame, text="", bg=BG_PANEL).pack(pady=2)

    def _render_event(self, parent, event):
        card = tk.Frame(parent, bg=BG_CARD)
        card.pack(fill="both", expand=True, pady=10)

        # Заголовок события
        tk.Label(card, text=event.get('title', '???'),
                 bg=BG_CARD, fg=FG_MAIN,
                 font=FONT_SUB).pack(pady=(20, 5))

        # Описание
        tk.Label(card, text=event.get('desc', ''),
                 bg=BG_CARD, fg=FG_DIM,
                 font=FONT_BODY,
                 wraplength=900, justify="center").pack(pady=(5, 20), padx=30)

        # Варианты
        choices_frame = tk.Frame(card, bg=BG_CARD)
        choices_frame.pack(pady=(0, 20))

        choices = event.get('choices', [])
        for choice in choices:
            self.app.make_button(
                choices_frame,
                choice.get('text', '???'),
                lambda a=choice.get('action'): self._on_choice(a),
                bg=BG_MID, fg=FG_MAIN, font=FONT_BODY,
            ).pack(side="left", padx=8)

    # ==================== ВЫБОР ====================

    def _on_choice(self, action):
        if not action:
            return

        result = expedition_choice(self.app.player_id, self.state, action)
        self.app.refresh_player()

        if not result.get('ok'):
            messagebox.showwarning("Событие", result.get('message', 'Ошибка'))
            return

        # Обновляем state
        new_state = result.get('state')
        if new_state:
            self.state = new_state

        # Следующий шаг
        self.state['current_event'] = None

        if result.get('died'):
            self._render_death()
            return
        if result.get('ended'):
            self._render_end()
            return

        self._render()

    # ==================== ФИНАЛ ====================

    def _render_death(self):
        s = self.state
        content = self.app.make_screen("💀 СМЕРТЬ", color=FG_DANGER)

        box = tk.Frame(content, bg=BG_CARD)
        box.pack(pady=30, padx=100, fill="x")

        tk.Label(box, text="☠️ ВЫ ПОГИБЛИ",
                 bg=BG_CARD, fg=FG_DANGER,
                 font=("Consolas", 28, "bold")).pack(pady=20)

        tk.Label(box, text="Пустошь забрала ещё одного...",
                 bg=BG_CARD, fg=FG_DIM,
                 font=FONT_BODY).pack(pady=5)

        tk.Label(box, text=f"Собрано: ☢️{s['total_rc']} RC  ☣️{s['total_rf']} RF",
                 bg=BG_CARD, fg=FG_MAIN,
                 font=FONT_BODY).pack(pady=10)

        tk.Label(box, text="Половина ресурсов потеряна. Снаряжение могло пострадать.",
                 bg=BG_CARD, fg=FG_DIM,
                 font=FONT_SMALL).pack(pady=5)

        btns = tk.Frame(content, bg=BG_DARK)
        btns.pack(pady=20)

        self.app.make_button(btns, "🎲 СНОВА",
                             self._restart,
                             bg="#1a3a1a", fg=FG_ACCENT).pack(side="left", padx=8)
        self.app.make_button(btns, "🔙 В МЕНЮ",
                             self._end,
                             bg=BG_MID, fg=FG_MAIN).pack(side="left", padx=8)

    def _render_end(self):
        s = self.state
        content = self.app.make_screen("✅ ВЫЛАЗКА ЗАВЕРШЕНА", color=FG_ACCENT)

        box = tk.Frame(content, bg=BG_CARD)
        box.pack(pady=30, padx=100, fill="x")

        tk.Label(box, text="🌅 ВЫ ВЕРНУЛИСЬ",
                 bg=BG_CARD, fg=FG_ACCENT,
                 font=("Consolas", 26, "bold")).pack(pady=20)

        tk.Label(box, text="Пустошь отпустила вас.",
                 bg=BG_CARD, fg=FG_DIM,
                 font=FONT_BODY).pack(pady=5)

        tk.Label(box, text=f"☢️ +{s['total_rc']} RC",
                 bg=BG_CARD, fg=FG_ACCENT,
                 font=FONT_SUB).pack(pady=3)
        tk.Label(box, text=f"☣️ +{s['total_rf']} RF",
                 bg=BG_CARD, fg=FG_PURPLE,
                 font=FONT_SUB).pack(pady=3)
        tk.Label(box, text=f"⚠️ +{s['total_exp']} опыта",
                 bg=BG_CARD, fg=FG_WARN,
                 font=FONT_SUB).pack(pady=3)

        if s.get('total_items'):
            tk.Label(box, text=f"📦 {', '.join(s['total_items'][:6])}",
                     bg=BG_CARD, fg=FG_MAIN,
                     font=FONT_SMALL,
                     wraplength=700).pack(pady=10)

        btns = tk.Frame(content, bg=BG_DARK)
        btns.pack(pady=20)

        self.app.make_button(btns, "🎲 СНОВА",
                             self._restart,
                             bg="#1a3a1a", fg=FG_ACCENT).pack(side="left", padx=8)
        self.app.make_button(btns, "🔙 В МЕНЮ",
                             self._end,
                             bg=BG_MID, fg=FG_MAIN).pack(side="left", padx=8)

    # ==================== УПРАВЛЕНИЕ ====================

    def _restart(self):
        self.state = None
        self._start()

    def _end(self):
        self.app.refresh_player()
        self.app.pop_screen()