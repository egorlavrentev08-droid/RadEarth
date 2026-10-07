# screen_dialog.py - Rad Earth
# Версия: 1.0.0
# Экран диалога с NPC. Реплика NPC, варианты ответа, эффекты, лог.

import tkinter as tk
from tkinter import messagebox

from theme import (
    BG_DARK, BG_MID, BG_PANEL, BG_CARD, BG_HOVER,
    FG_MAIN, FG_DIM, FG_ACCENT, FG_WARN, FG_DANGER,
    FONT_HEADER, FONT_SUB, FONT_BODY, FONT_SMALL, FONT_TINY,
    get_faction_color,
)
from dialog_system import start_dialog, process_choice
from npc_engine import get_npc_view
from database import get_players_session, Player


class DialogScreen:
    """Экран диалога с NPC."""

    def __init__(self, app, npc_id):
        self.app = app
        self.npc_id = npc_id
        self.history = []
        self.session = None

        self._start()

    # ==================== СТАРТ ====================

    def _start(self):
        # Начать диалог
        result = start_dialog(self.app.player_id, self.npc_id)

        if not result or 'error' in result:
            msg = result.get('error', 'Не удалось начать диалог') if result else 'Ошибка'
            messagebox.showwarning("Диалог", msg)
            self.app.pop_screen()
            return

        self.session = result
        self.history.append({
            'speaker': 'npc',
            'text': result.get('greeting', '...'),
        })
        self._render()

    # ==================== РЕНДЕР ====================

    def _render(self):
        npc = self.session
        content = self.app.make_screen(
            f"💬 {npc.get('npc_name', 'NPC')}",
            color=get_faction_color(npc.get('faction_id')),
            subtitle=self._npc_subtitle(),
        )

        # Основной контейнер — слева инфо, справа история/выбор
        main = tk.Frame(content, bg=BG_DARK)
        main.pack(fill="both", expand=True, padx=20, pady=10)

        # Левая колонка — инфо о NPC
        left = tk.Frame(main, bg=BG_CARD, width=320)
        left.pack(side="left", fill="y", padx=(0, 15))
        left.pack_propagate(False)
        self._render_npc_info(left)

        # Правая колонка — диалог
        right = tk.Frame(main, bg=BG_DARK)
        right.pack(side="left", fill="both", expand=True)
        self._render_dialog(right)

    def _npc_subtitle(self):
        n = self.session
        parts = []
        if n.get('rank'):
            parts.append(f"Ранг: {n['rank']}")
        if n.get('faction_id'):
            from faction_engine import get_faction
            f = get_faction(n['faction_id'])
            if f:
                parts.append(f.name)
        return "  |  ".join(parts) if parts else None

    def _render_npc_info(self, parent):
        n = self.session

        # Имя / позывной
        tk.Label(parent, text=n.get('npc_name', '???'),
                 bg=BG_CARD, fg=FG_MAIN,
                 font=FONT_SUB).pack(anchor="w", padx=15, pady=(15, 2))

        if n.get('npc_callsign'):
            tk.Label(parent, text=f"«{n['npc_callsign']}»",
                     bg=BG_CARD, fg=FG_DIM,
                     font=FONT_SMALL).pack(anchor="w", padx=15)

        # Фракция
        if n.get('faction_id'):
            from faction_engine import get_faction
            f = get_faction(n['faction_id'])
            if f:
                tk.Label(parent, text=f.name,
                         bg=BG_CARD, fg=f.color,
                         font=FONT_BODY).pack(anchor="w", padx=15, pady=(10, 0))

        # Отношение
        attitude = n.get('npc_attitude', 0)
        if attitude <= -50:
            at_color, at_text = FG_DANGER, "Враждебен"
        elif attitude <= -20:
            at_color, at_text = FG_WARN, "Недружелюбен"
        elif attitude < 20:
            at_color, at_text = FG_DIM, "Нейтрален"
        elif attitude < 50:
            at_color, at_text = FG_ACCENT, "Дружелюбен"
        else:
            at_color, at_text = FG_ACCENT, "Союзник"

        tk.Label(parent, text=f"Отношение: {at_text} ({attitude})",
                 bg=BG_CARD, fg=at_color,
                 font=FONT_SMALL).pack(anchor="w", padx=15, pady=(10, 0))

        # Репутация с фракцией
        if n.get('faction_id'):
            rep = n.get('faction_rep', 0)
            from config import get_rep_tier
            _, rep_name = get_rep_tier(rep)
            tk.Label(parent, text=f"Репутация: {rep_name} ({rep})",
                     bg=BG_CARD, fg=FG_DIM,
                     font=FONT_SMALL).pack(anchor="w", padx=15, pady=(3, 0))

        # Разделитель
        tk.Frame(parent, bg=BG_MID, height=1).pack(fill="x", padx=15, pady=15)

        # Кнопки
        self.app.make_button(parent, "🔙 Закончить разговор",
                             self._end_dialog,
                             bg=BG_MID, fg=FG_MAIN,
                             font=FONT_SMALL).pack(pady=5, padx=15)

    def _render_dialog(self, parent):
        # История — прокручиваемая область
        canvas = tk.Canvas(parent, bg=BG_DARK, highlightthickness=0)
        scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        history_frame = tk.Frame(canvas, bg=BG_DARK)

        history_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=history_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="top", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for entry in self.history:
            self._render_history_entry(history_frame, entry)

        # Прокрутка вниз
        canvas.update_idletasks()
        canvas.yview_moveto(1.0)

        # Область выбора
        choices_frame = tk.Frame(parent, bg=BG_DARK)
        choices_frame.pack(side="bottom", fill="x", pady=10)

        self._render_choices(choices_frame)

    def _render_history_entry(self, parent, entry):
        if entry['speaker'] == 'npc':
            bg = BG_CARD
            fg = FG_MAIN
            prefix = ""
        elif entry['speaker'] == 'player':
            bg = "#1a2a1a"
            fg = FG_ACCENT
            prefix = "▶ "
        else:  # system
            bg = BG_PANEL
            fg = FG_DIM
            prefix = ""

        frame = tk.Frame(parent, bg=bg)
        frame.pack(fill="x", padx=10, pady=4)

        tk.Label(frame, text=prefix + entry['text'],
                 bg=bg, fg=fg,
                 font=FONT_BODY,
                 wraplength=800, justify="left",
                 anchor="w").pack(fill="x", padx=15, pady=10)

    def _render_choices(self, parent):
        choices = self.session.get('choices', [])

        if not choices:
            # Диалог закончился
            tk.Label(parent, text="— Разговор окончен —",
                     bg=BG_DARK, fg=FG_DIM,
                     font=FONT_SMALL).pack(pady=10)
            self.app.make_button(parent, "🔙 Вернуться",
                                 self._end_dialog,
                                 bg=BG_MID, fg=FG_MAIN).pack(pady=5)
            return

        tk.Label(parent, text="Ваш ответ:",
                 bg=BG_DARK, fg=FG_DIM,
                 font=FONT_SMALL).pack(anchor="w", padx=10)

        for i, choice in enumerate(choices):
            text = choice.get('text', f'Вариант {i+1}')
            effects = choice.get('effects', {})

            # Краткая подсказка об эффектах
            hint = self._format_effects_hint(effects)

            btn_text = text
            if hint:
                btn_text = f"{text}   {hint}"

            self.app.make_button(
                parent, btn_text,
                lambda idx=i: self._on_choice(idx),
                bg=BG_CARD, fg=FG_MAIN,
                font=FONT_BODY,
            ).pack(fill="x", padx=10, pady=3)

    def _format_effects_hint(self, effects):
        """Подсказка об эффектах в скобках."""
        parts = []
        if 'rep' in effects:
            d = effects['rep']
            if d > 0:
                parts.append(f"📈 +{d} реп")
            elif d < 0:
                parts.append(f"📉 {d} реп")
        if 'rc' in effects:
            d = effects['rc']
            if d > 0:
                parts.append(f"☢️ +{d}")
            elif d < 0:
                parts.append(f"☢️ {d}")
        if 'rf' in effects:
            d = effects['rf']
            if d > 0:
                parts.append(f"☣️ +{d}")
            elif d < 0:
                parts.append(f"☣️ {d}")
        if 'item' in effects:
            parts.append("📦 предмет")
        if 'npc_attitude' in effects:
            d = effects['npc_attitude']
            if d > 0:
                parts.append(f"😊 +{d}")
            elif d < 0:
                parts.append(f"😠 {d}")
        return " ".join(parts)

    # ==================== ВЫБОР ====================

    def _on_choice(self, choice_index):
        """Игрок выбрал вариант."""
        choices = self.session.get('choices', [])
        if choice_index < 0 or choice_index >= len(choices):
            return

        # Записать выбор игрока
        chosen = choices[choice_index]
        player_text = chosen.get('text', '...')
        self.history.append({'speaker': 'player', 'text': player_text})

        # Обработать
        result = process_choice(self.app.player_id, self.npc_id, choice_index)

        if not result or 'error' in result:
            msg = result.get('error', 'Ошибка') if result else 'Ошибка'
            self.history.append({'speaker': 'system', 'text': f'⚠️ {msg}'})
            self.session['choices'] = []
            self._render()
            return

        # Ответ NPC
        reply = result.get('reply', '...')
        self.history.append({'speaker': 'npc', 'text': reply})

        # Эффекты — показать как систему
        eff = result.get('effects', {})
        if eff:
            self.history.append({
                'speaker': 'system',
                'text': self._format_effects_applied(eff),
            })

        # Действия
        action = result.get('action')
        if action:
            self._handle_action(action)

        # Обновить игрока
        self.app.refresh_player()

        # Продолжение или конец
        if action in ('end', 'leave', 'attack', 'join_faction', 'leave_faction'):
            self.session['choices'] = []
        else:
            # Проверить: есть ли следующий набор choices
            next_choices = self._get_next_choices()
            self.session['choices'] = next_choices

        self._render()

    def _format_effects_applied(self, effects):
        parts = []
        if 'rep' in effects:
            d = effects['rep']
            parts.append(f"Репутация {'+' if d > 0 else ''}{d}")
        if 'npc_attitude' in effects:
            d = effects['npc_attitude']
            parts.append(f"Отношение NPC {'+' if d > 0 else ''}{d}")
        if 'rc' in effects:
            parts.append(f"RC {'+' if effects['rc'] > 0 else ''}{effects['rc']}")
        if 'rf' in effects:
            parts.append(f"RF {'+' if effects['rf'] > 0 else ''}{effects['rf']}")
        if 'item' in effects:
            parts.append(f"Получено: {effects['item']}")
        return "📋 " + ", ".join(parts) if parts else ""

    def _get_next_choices(self):
        """Продолжение диалога после выбора."""
        # Если в NPC-файле есть continuation — использовать.
        # Пока — базовые варианты из dialog_system.
        from dialog_system import load_dialog, get_generic_dialog
        npc = self.session

        if npc.get('npc_name'):
            npc_data = None
            try:
                from npc_engine import get_npc
                npc_obj = get_npc(self.npc_id)
                if npc_obj:
                    if npc_obj.is_named and npc_obj.dialog_file:
                        npc_data = load_dialog(npc_obj.dialog_file)
                    else:
                        npc_data = get_generic_dialog(
                            npc_obj.faction_id, npc_obj.role or 'soldier'
                        )
            except Exception:
                npc_data = None

            if npc_data:
                return npc_data.get('choices', [])

        # Fallback — базовые
        return [
            {'text': '👋 Поздороваться', 'reply': '— Приветствую.', 'effects': {'rep': 1}},
            {'text': '❓ Спросить о делах', 'reply': '— Дела как обычно.', 'effects': {}},
            {'text': '🚶 Уйти', 'reply': '— Ходи с миром.', 'effects': {}, 'action': 'end'},
        ]

    def _handle_action(self, action):
        """Обработать действие из диалога."""
        if action == 'trade':
            self.history.append({
                'speaker': 'system',
                'text': '💰 Торговец открывает товары...',
            })
            # Здесь можно перейти на торговый экран

        elif action == 'attack':
            self.history.append({
                'speaker': 'system',
                'text': '⚔️ Вы атаковали NPC!',
            })

        elif action == 'join_faction':
            self.history.append({
                'speaker': 'system',
                'text': '✅ Вы присоединились к фракции!',
            })

        elif action == 'leave_faction':
            self.history.append({
                'speaker': 'system',
                'text': '🚪 Вы покинули фракцию.',
            })

        elif action == 'end':
            pass

    # ==================== ВЫХОД ====================

    def _end_dialog(self):
        self.app.refresh_player()
        self.app.pop_screen()