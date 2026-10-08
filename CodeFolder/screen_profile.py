# screen_profile.py - Rad Earth
# Версия: 1.0.0
# Экран профиля. Игрок, статистика, репутации, память о NPC, достижения.

import tkinter as tk
from tkinter import messagebox
import json

from theme import (
    BG_DARK, BG_MID, BG_PANEL, BG_CARD, BG_HOVER,
    FG_MAIN, FG_DIM, FG_ACCENT, FG_WARN, FG_DANGER, FG_BLUE, FG_PURPLE, FG_YELLOW,
    FONT_HEADER, FONT_SUB, FONT_BODY, FONT_SMALL, FONT_TINY,
    get_faction_color,
)
from config import FACTION_RANKS, get_rep_tier, get_exp_for_level
from player_logic import (
    get_profile, get_inventory_view, get_achievements,
    get_npc_memory, get_global_stats,
)
from npc_engine import get_met_npcs


CLASS_NAMES = {
    'stalker': '🟢 Сталкер',
    'military': '🔫 Военный',
    'bandit': '🗡️ Бандит',
    'scientist': '🔬 Учёный',
}


class ProfileScreen:
    """Экран профиля игрока."""

    def __init__(self, app):
        self.app = app
        self.tab = 'main'  # main / stats / rep / memory / achievements
        self._render()

    # ==================== РЕНДЕР ====================

    def _render(self):
        profile = get_profile(self.app.player_id)
        if not profile:
            messagebox.showerror("Профиль", "Не удалось загрузить профиль")
            self.app.pop_screen()
            return

        content = self.app.make_screen(
            "👤 ПРОФИЛЬ",
            color=FG_ACCENT,
            subtitle=f"{profile['username']}  |  Уровень {profile['level']}"
        )

        # Вкладки
        tabs = tk.Frame(content, bg=BG_DARK)
        tabs.pack(fill="x", pady=(0, 10))

        tab_defs = [
            ('main', '👤 Основное'),
            ('stats', '📊 Статистика'),
            ('rep', '🏰 Репутации'),
            ('memory', '👥 Память'),
            ('achievements', '🏅 Достижения'),
        ]

        for tab_id, tab_name in tab_defs:
            is_active = (self.tab == tab_id)
            bg = BG_HOVER if is_active else BG_MID
            fg = FG_ACCENT if is_active else FG_MAIN

            self.app.make_button(
                tabs, tab_name,
                lambda tid=tab_id: self._switch_tab(tid),
                bg=bg, fg=fg, font=FONT_SMALL,
            ).pack(side="left", padx=3)

        # Контент вкладки
        if self.tab == 'main':
            self._render_main(content, profile)
        elif self.tab == 'stats':
            self._render_stats(content, profile)
        elif self.tab == 'rep':
            self._render_reputations(content, profile)
        elif self.tab == 'memory':
            self._render_memory(content)
        elif self.tab == 'achievements':
            self._render_achievements(content)

    def _switch_tab(self, tab_id):
        self.tab = tab_id
        self._render()

    # ==================== ОСНОВНОЕ ====================

    def _render_main(self, parent, profile):
        # Две колонки
        cols = tk.Frame(parent, bg=BG_DARK)
        cols.pack(fill="both", expand=True)

        left = tk.Frame(cols, bg=BG_CARD)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))

        right = tk.Frame(cols, bg=BG_CARD)
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))

        # ==== ЛЕВАЯ ====
        tk.Label(left, text="👤 ИГРОК",
                 bg=BG_CARD, fg=FG_DIM,
                 font=FONT_SMALL).pack(anchor="w", padx=15, pady=(15, 5))

        rows = [
            ("Имя", profile['username']),
            ("Класс", CLASS_NAMES.get(profile['user_class'], profile['user_class'])),
            ("Уровень", str(profile['level'])),
            ("Опыт", f"{profile['experience']} / {profile['next_level_exp'] or '—'}"),
        ]

        # Прогресс до следующего уровня
        if profile.get('next_level_exp'):
            remaining = profile['exp_to_next']
            rows.append(("До след. уровня", f"{remaining} XP"))

        for label, value in rows:
            row = tk.Frame(left, bg=BG_CARD)
            row.pack(fill="x", padx=15, pady=2)
            tk.Label(row, text=label + ":", bg=BG_CARD, fg=FG_DIM,
                     font=FONT_SMALL, width=18, anchor="w").pack(side="left")
            tk.Label(row, text=value, bg=BG_CARD, fg=FG_MAIN,
                     font=FONT_BODY, anchor="w").pack(side="left")

        # Фракция
        tk.Frame(left, bg=BG_MID, height=1).pack(fill="x", padx=15, pady=10)

        tk.Label(left, text="🏰 ФРАКЦИЯ",
                 bg=BG_CARD, fg=FG_DIM,
                 font=FONT_SMALL).pack(anchor="w", padx=15, pady=(5, 5))

        if profile.get('faction'):
            f = profile['faction']
            tk.Label(left, text=f['name'],
                     bg=BG_CARD, fg=f['color'],
                     font=FONT_SUB).pack(anchor="w", padx=15)
            tk.Label(left, text=f"Ранг: {profile.get('faction_rank_name', '—')}",
                     bg=BG_CARD, fg=FG_DIM,
                     font=FONT_BODY).pack(anchor="w", padx=15)
        else:
            tk.Label(left, text="— Без фракции —",
                     bg=BG_CARD, fg=FG_DIM,
                     font=FONT_BODY).pack(anchor="w", padx=15)

        # Питомец
        tk.Frame(left, bg=BG_MID, height=1).pack(fill="x", padx=15, pady=10)

        tk.Label(left, text="🐾 ПИТОМЕЦ",
                 bg=BG_CARD, fg=FG_DIM,
                 font=FONT_SMALL).pack(anchor="w", padx=15, pady=(5, 5))
        tk.Label(left, text=profile.get('pet') or "— Нет —",
                 bg=BG_CARD, fg=FG_MAIN,
                 font=FONT_BODY).pack(anchor="w", padx=15)

        # ==== ПРАВАЯ ====
        tk.Label(right, text="💰 РЕСУРСЫ",
                 bg=BG_CARD, fg=FG_DIM,
                 font=FONT_SMALL).pack(anchor="w", padx=15, pady=(15, 5))

        res_rows = [
            ("☢️ РадКоины", f"{int(profile['radcoins'])}"),
            ("☣️ РадФрагменты", f"{profile['radfragments']}"),
            ("💎 РадКристаллы", f"{profile['radcrystals']}"),
        ]
        for label, value in res_rows:
            row = tk.Frame(right, bg=BG_CARD)
            row.pack(fill="x", padx=15, pady=2)
            tk.Label(row, text=label, bg=BG_CARD, fg=FG_DIM,
                     font=FONT_SMALL).pack(side="left")
            tk.Label(row, text=value, bg=BG_CARD, fg=FG_ACCENT,
                     font=FONT_BODY).pack(side="right")

        # Локация
        tk.Frame(right, bg=BG_MID, height=1).pack(fill="x", padx=15, pady=10)

        tk.Label(right, text="📍 ЛОКАЦИЯ",
                 bg=BG_CARD, fg=FG_DIM,
                 font=FONT_SMALL).pack(anchor="w", padx=15, pady=(5, 5))

        if profile.get('location'):
            tk.Label(right, text=profile['location']['name'],
                     bg=BG_CARD, fg=FG_BLUE,
                     font=FONT_BODY).pack(anchor="w", padx=15)

        # Экипировка
        tk.Frame(right, bg=BG_MID, height=1).pack(fill="x", padx=15, pady=10)

        tk.Label(right, text="🛡 ЭКИПИРОВКА",
                 bg=BG_CARD, fg=FG_DIM,
                 font=FONT_SMALL).pack(anchor="w", padx=15, pady=(5, 5))

        eq = profile.get('equipped', {})
        for slot, label in [('weapon', '⚔ Оружие'), ('armor', '🛡 Броня')]:
            row = tk.Frame(right, bg=BG_CARD)
            row.pack(fill="x", padx=15, pady=2)
            tk.Label(row, text=label, bg=BG_CARD, fg=FG_DIM,
                     font=FONT_SMALL).pack(side="left")
            tk.Label(row, text=eq.get(slot) or "—", bg=BG_CARD, fg=FG_MAIN,
                     font=FONT_BODY).pack(side="right")

        # Эффекты
        if profile.get('effects'):
            tk.Frame(right, bg=BG_MID, height=1).pack(fill="x", padx=15, pady=10)

            tk.Label(right, text="⚙️ ЭФФЕКТЫ",
                     bg=BG_CARD, fg=FG_DIM,
                     font=FONT_SMALL).pack(anchor="w", padx=15, pady=(5, 5))

            for effect in profile['effects']:
                remaining = effect['remaining_sec']
                h = remaining // 3600
                m = (remaining % 3600) // 60
                tk.Label(right, text=f"  {effect['name']} — {h}ч {m}мин",
                         bg=BG_CARD, fg=FG_PURPLE,
                         font=FONT_SMALL).pack(anchor="w", padx=15)

    # ==================== СТАТИСТИКА ====================

    def _render_stats(self, parent, profile):
        stats = profile.get('stats', {})

        # Две колонки
        cols = tk.Frame(parent, bg=BG_DARK)
        cols.pack(fill="both", expand=True)

        left = tk.Frame(cols, bg=BG_CARD)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))

        right = tk.Frame(cols, bg=BG_CARD)
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))

        tk.Label(left, text="💰 ДОБЫЧА",
                 bg=BG_CARD, fg=FG_DIM,
                 font=FONT_SMALL).pack(anchor="w", padx=15, pady=(15, 5))

        left_rows = [
            ("🎲 Сборов", stats.get('total_collects', 0)),
            ("💰 Всего RC собрано", int(stats.get('total_rc_earned', 0))),
            ("🏆 Лучший сбор", int(stats.get('best_collect', 0))),
            ("📈 Серия дней", stats.get('daily_streak', 0)),
        ]
        for label, value in left_rows:
            row = tk.Frame(left, bg=BG_CARD)
            row.pack(fill="x", padx=15, pady=2)
            tk.Label(row, text=label, bg=BG_CARD, fg=FG_DIM,
                     font=FONT_SMALL).pack(side="left")
            tk.Label(row, text=str(value), bg=BG_CARD, fg=FG_MAIN,
                     font=FONT_BODY).pack(side="right")

        tk.Label(right, text="⚔️ БОИ",
                 bg=BG_CARD, fg=FG_DIM,
                 font=FONT_SMALL).pack(anchor="w", padx=15, pady=(15, 5))

        right_rows = [
            ("🧬 Мутантов", stats.get('mutants_killed', 0)),
            ("👑 Боссов", stats.get('bosses_killed', 0)),
            ("💀 Убито NPC", stats.get('npcs_killed', 0)),
            ("🤝 Помощь NPC", stats.get('npcs_helped', 0)),
            ("☠️ Смертей", stats.get('deaths', 0)),
        ]
        for label, value in right_rows:
            row = tk.Frame(right, bg=BG_CARD)
            row.pack(fill="x", padx=15, pady=2)
            tk.Label(row, text=label, bg=BG_CARD, fg=FG_DIM,
                     font=FONT_SMALL).pack(side="left")
            tk.Label(row, text=str(value), bg=BG_CARD, fg=FG_MAIN,
                     font=FONT_BODY).pack(side="right")

    # ==================== РЕПУТАЦИИ ====================

    def _render_reputations(self, parent, profile):
        reps = profile.get('reputations', [])

        if not reps:
            tk.Label(parent, text="Репутаций пока нет",
                     bg=BG_DARK, fg=FG_DIM,
                     font=FONT_BODY).pack(pady=60)
            return

        tk.Label(parent, text="Ваши отношения с фракциями:",
                 bg=BG_DARK, fg=FG_DIM,
                 font=FONT_BODY).pack(anchor="w", pady=(0, 10))

        # Сортируем по величине репутации
        reps_sorted = sorted(reps, key=lambda x: x['value'], reverse=True)

        for rep in reps_sorted:
            card = tk.Frame(parent, bg=BG_CARD)
            card.pack(fill="x", pady=3)

            # Название фракции
            tk.Label(card, text=rep.get('faction_name', rep['faction_id']),
                     bg=BG_CARD, fg=rep.get('faction_color', FG_MAIN),
                     font=FONT_SUB,
                     anchor="w").pack(side="left", padx=15, pady=10)

            # Значение
            value = rep['value']
            if value >= 20:
                v_color = FG_ACCENT
            elif value <= -50:
                v_color = FG_DANGER
            elif value <= -20:
                v_color = FG_WARN
            else:
                v_color = FG_DIM

            tk.Label(card, text=f"{value:+d}  ({rep.get('tier_name', '')})",
                     bg=BG_CARD, fg=v_color,
                     font=FONT_BODY).pack(side="right", padx=15)

    # ==================== ПАМЯТЬ О NPC ====================

    def _render_memory(self, parent):
        memory = get_met_npcs(self.app.player_id, limit=100)

        if not memory:
            tk.Label(parent, text="Вы ещё никого не встретили",
                     bg=BG_DARK, fg=FG_DIM,
                     font=FONT_BODY).pack(pady=60)
            return

        tk.Label(parent, text=f"Всего встреч: {len(memory)}",
                 bg=BG_DARK, fg=FG_DIM,
                 font=FONT_BODY).pack(anchor="w", pady=(0, 10))

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

        for npc in memory:
            self._render_memory_row(inner, npc)

    def _render_memory_row(self, parent, npc):
        row = tk.Frame(parent, bg=BG_CARD)
        row.pack(fill="x", pady=2, padx=5)

        # Статус (живой / мёртвый)
        status_icon = "💚" if npc.get('is_alive') else "💀"
        tk.Label(row, text=status_icon,
                 bg=BG_CARD, fg=FG_MAIN,
                 font=FONT_BODY).pack(side="left", padx=10, pady=8)

        # Имя
        name = npc.get('npc_name', '???')
        if npc.get('callsign'):
            name += f" «{npc['callsign']}»"
        tk.Label(row, text=name,
                 bg=BG_CARD, fg=FG_MAIN,
                 font=FONT_BODY, anchor="w").pack(side="left", pady=8)

        # Фракция
        if npc.get('faction_name'):
            tk.Label(row, text=npc['faction_name'],
                     bg=BG_CARD, fg=FG_DIM,
                     font=FONT_SMALL).pack(side="left", padx=15)

        # Отношение
        att = npc.get('attitude', 0)
        if att >= 20:
            a_color = FG_ACCENT
        elif att <= -20:
            a_color = FG_DANGER
        else:
            a_color = FG_DIM

        tk.Label(row, text=f"{att:+d}",
                 bg=BG_CARD, fg=a_color,
                 font=FONT_BODY).pack(side="right", padx=15)

    # ==================== ДОСТИЖЕНИЯ ====================

    def _render_achievements(self, parent):
        achievements = get_achievements(self.app.player_id)

        if not achievements:
            tk.Label(parent, text="Достижений пока нет",
                     bg=BG_DARK, fg=FG_DIM,
                     font=FONT_BODY).pack(pady=60)
            tk.Label(parent,
                     text="Выполняйте действия, чтобы разблокировать их.",
                     bg=BG_DARK, fg=FG_DIM,
                     font=FONT_SMALL).pack()
            return

        tk.Label(parent, text=f"Разблокировано: {len(achievements)}",
                 bg=BG_DARK, fg=FG_DIM,
                 font=FONT_BODY).pack(anchor="w", pady=(0, 10))

        # Известные достижения
        known = {
            'first_collect': ('🎯', 'Первый сбор', 'Совершите первый сбор'),
            'collector_100': ('📦', 'Коллекционер', '100 сборов'),
            'first_blood': ('⚔️', 'Первая кровь', 'Убейте первого мутанта'),
            'boss_slayer': ('👑', 'Убийца боссов', 'Убейте босса Пустоши'),
            'rich': ('💰', 'Богач', 'Накопите 100 000 RC'),
            'faction_member': ('🏰', 'Член фракции', 'Присоединитесь к фракции'),
            'peacekeeper': ('🕊️', 'Миротворец', 'Помогите 10 NPC'),
            'survivor': ('💪', 'Выживший', 'Проживите 7 дней'),
            'traveler': ('🗺️', 'Путешественник', 'Посетите 10 локаций'),
        }

        for ach_id in achievements:
            card = tk.Frame(parent, bg=BG_CARD)
            card.pack(fill="x", pady=3)

            icon, name, desc = known.get(ach_id, ('🏅', ach_id, ''))

            tk.Label(card, text=icon,
                     bg=BG_CARD, fg=FG_YELLOW,
                     font=("Consolas", 24)).pack(side="left", padx=15, pady=8)

            info = tk.Frame(card, bg=BG_CARD)
            info.pack(side="left", fill="x", expand=True, pady=8)

            tk.Label(info, text=name,
                     bg=BG_CARD, fg=FG_YELLOW,
                     font=FONT_SUB, anchor="w").pack(anchor="w")

            if desc:
                tk.Label(info, text=desc,
                         bg=BG_CARD, fg=FG_DIM,
                         font=FONT_SMALL, anchor="w").pack(anchor="w")