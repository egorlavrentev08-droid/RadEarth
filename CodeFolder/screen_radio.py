# screen_radio.py - Rad Earth
# Версия: 1.0.0
# Экран радио. Ведущий, история эфира, анимация частот, кнопки действий.

import tkinter as tk
from tkinter import messagebox
import random
from datetime import datetime

from theme import (
    BG_DARK, BG_MID, BG_PANEL, BG_CARD, BG_HOVER,
    FG_MAIN, FG_DIM, FG_ACCENT, FG_WARN, FG_DANGER, FG_BLUE, FG_PURPLE, FG_YELLOW,
    FONT_HEADER, FONT_SUB, FONT_BODY, FONT_SMALL, FONT_TINY, FONT_MONO,
    get_faction_color,
)
from radio_system import (
    compose_broadcast, get_history, get_last_broadcast,
    force_broadcast, get_active_host,
)


class RadioScreen:
    """Экран радиоэфира."""

    def __init__(self, app):
        self.app = app
        self.animation_running = False
        self.animation_phase = 0
        self.animation_canvas = None
        self._render()

    # ==================== РЕНДЕР ====================

    def _render(self):
        content = self.app.make_screen(
            "📻 РАДИОЭФИР",
            color=FG_BLUE,
            subtitle=self._subtitle()
        )

        # Основная сетка: слева — эфир, справа — история
        main = tk.Frame(content, bg=BG_DARK)
        main.pack(fill="both", expand=True)

        left = tk.Frame(main, bg=BG_CARD)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))

        right = tk.Frame(main, bg=BG_CARD, width=420)
        right.pack(side="left", fill="y", padx=(8, 0))
        right.pack_propagate(False)

        self._render_broadcast(left)
        self._render_history(right)

    def _subtitle(self):
        host = get_active_host()
        if host:
            return f"Ведущий: {host.name}"
        return "Ведущий: неизвестен"

    # ==================== ЭФИР ====================

    def _render_broadcast(self, parent):
        # Верх — анимация частоты
        tk.Label(parent, text="📡 ЧАСТОТА",
                 bg=BG_CARD, fg=FG_DIM,
                 font=FONT_SMALL).pack(anchor="w", padx=15, pady=(15, 5))

        self.animation_canvas = tk.Canvas(parent, bg=BG_PANEL,
                                          height=80, highlightthickness=0)
        self.animation_canvas.pack(fill="x", padx=15, pady=(0, 10))

        # Запуск анимации
        self.animation_running = True
        self._animate_radio()

        # Текущий эфир
        tk.Label(parent, text="🔊 СЕЙЧАС В ЭФИРЕ",
                 bg=BG_CARD, fg=FG_DIM,
                 font=FONT_SMALL).pack(anchor="w", padx=15, pady=(5, 5))

        broadcast = get_last_broadcast()
        if not broadcast:
            tk.Label(parent, text="— Тишина в эфире —",
                     bg=BG_CARD, fg=FG_DIM,
                     font=FONT_BODY).pack(anchor="w", padx=15, pady=20)
        else:
            self._render_broadcast_text(parent, broadcast)

        # Кнопки
        btn_frame = tk.Frame(parent, bg=BG_CARD)
        btn_frame.pack(fill="x", padx=15, pady=15)

        self.app.make_button(
            btn_frame, "🔄 ОБНОВИТЬ ЭФИР",
            self._force_broadcast,
            bg="#1a3a1a", fg=FG_ACCENT,
            font=FONT_BODY,
        ).pack(side="left", padx=5)

        self.app.make_button(
            btn_frame, "📻 СЛУШАТЬ",
            self._listen,
            bg=BG_MID, fg=FG_BLUE,
            font=FONT_BODY,
        ).pack(side="left", padx=5)

    def _render_broadcast_text(self, parent, broadcast):
        # Ведущий
        host_frame = tk.Frame(parent, bg=BG_PANEL)
        host_frame.pack(fill="x", padx=15, pady=(0, 10))

        tk.Label(host_frame, text=f"🎙 {broadcast.get('host_name', 'Неизвестный')}",
                 bg=BG_PANEL, fg=FG_BLUE,
                 font=FONT_BODY).pack(anchor="w", padx=10, pady=8)

        # Текст
        text_frame = tk.Frame(parent, bg=BG_PANEL)
        text_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        for part in broadcast.get('parts', []):
            tk.Label(text_frame, text=part,
                     bg=BG_PANEL, fg=FG_MAIN,
                     font=FONT_BODY,
                     wraplength=700, justify="left",
                     anchor="w").pack(anchor="w", padx=15, pady=4)

    # ==================== АНИМАЦИЯ ====================

    def _animate_radio(self):
        if not self.animation_running or not self.animation_canvas:
            return

        try:
            self.animation_canvas.delete("wave")
            w = self.animation_canvas.winfo_width() or 600
            h = 80
            mid = h // 2

            # Рисуем волну
            points = []
            for x in range(0, w, 4):
                # Две синусоиды для эффекта
                y1 = mid + int(15 * self._wave(x, self.animation_phase))
                y2 = mid + int(10 * self._wave(x, self.animation_phase * 0.7 + 1.5))
                points.append((x, y1, y2))

            for x, y1, y2 in points:
                self.animation_canvas.create_line(
                    x, y1, x + 4, y1,
                    fill="#66ccff", width=2, tags="wave"
                )
                self.animation_canvas.create_line(
                    x, y2, x + 4, y2,
                    fill="#1a4a6a", width=1, tags="wave"
                )

            # Точка "жизни"
            self.animation_canvas.create_oval(
                w - 30, mid - 5, w - 20, mid + 5,
                fill="#00ff88", outline="", tags="wave"
            )

            self.animation_phase += 0.3
            self.app.root.after(80, self._animate_radio)
        except tk.TclError:
            self.animation_running = False

    def _wave(self, x, phase):
        import math
        return math.sin((x * 0.05) + phase)

    # ==================== ИСТОРИЯ ====================

    def _render_history(self, parent):
        tk.Label(parent, text="📜 ИСТОРИЯ ЭФИРА",
                 bg=BG_CARD, fg=FG_DIM,
                 font=FONT_SMALL).pack(anchor="w", padx=15, pady=(15, 8))

        history = get_history(limit=10)

        if not history:
            tk.Label(parent, text="— Пока ничего не было —",
                     bg=BG_CARD, fg=FG_DIM,
                     font=FONT_SMALL).pack(anchor="w", padx=15)
            return

        # Скролл
        canvas = tk.Canvas(parent, bg=BG_CARD, highlightthickness=0)
        scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG_CARD)

        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(5, 0))
        scrollbar.pack(side="right", fill="y", pady=5)

        for b in reversed(history):
            self._render_history_item(inner, b)

    def _render_history_item(self, parent, broadcast):
        card = tk.Frame(parent, bg=BG_PANEL)
        card.pack(fill="x", padx=5, pady=4)

        # Время
        ts = broadcast.get('timestamp', '')
        try:
            dt = datetime.fromisoformat(ts)
            ts_str = dt.strftime('%H:%M')
        except Exception:
            ts_str = '—'

        tk.Label(card, text=f"🕐 {ts_str}",
                 bg=BG_PANEL, fg=FG_DIM,
                 font=FONT_TINY).pack(anchor="w", padx=10, pady=(6, 2))

        # Ведущий
        tk.Label(card, text=f"🎙 {broadcast.get('host_name', '?')}",
                 bg=BG_PANEL, fg=FG_BLUE,
                 font=FONT_SMALL).pack(anchor="w", padx=10)

        # Краткое содержание — первые 2 строки
        parts = broadcast.get('parts', [])
        for part in parts[:2]:
            text = part[:80] + ('...' if len(part) > 80 else '')
            tk.Label(card, text=text,
                     bg=BG_PANEL, fg=FG_MAIN,
                     font=FONT_TINY, wraplength=380,
                     justify="left", anchor="w").pack(anchor="w", padx=10, pady=1)

        if len(parts) > 2:
            tk.Label(card, text=f"  (+{len(parts) - 2} строк)",
                     bg=BG_PANEL, fg=FG_DIM,
                     font=FONT_TINY).pack(anchor="w", padx=10, pady=(0, 6))
        else:
            tk.Label(card, text="",
                     bg=BG_PANEL).pack(pady=2)

    # ==================== ДЕЙСТВИЯ ====================

    def _force_broadcast(self):
        broadcast = force_broadcast()
        messagebox.showinfo("Радио", "Новый эфир выпущен в свет")
        self._render()

    def _listen(self):
        broadcast = get_last_broadcast()
        if not broadcast:
            messagebox.showinfo("Радио", "Тишина в эфире...")
            return

        # Показать полный текст
        text = broadcast.get('text', '')
        messagebox.showinfo(
            f"Эфир — {broadcast.get('host_name', '?')}",
            text[:2000] if text else "Пусто"
        )

    def _stop_animation(self):
        self.animation_running = False