# screen_faction.py - Rad Earth
# Версия: 1.0.0
# Экран фракций. Список фракций, репутация игрока, дипломатия, вступление/выход.

import tkinter as tk
from tkinter import messagebox
import json

from theme import (
    BG_DARK, BG_MID, BG_PANEL, BG_CARD, BG_HOVER,
    FG_MAIN, FG_DIM, FG_ACCENT, FG_WARN, FG_DANGER, FG_BLUE, FG_PURPLE, FG_YELLOW,
    FONT_HEADER, FONT_SUB, FONT_BODY, FONT_SMALL, FONT_TINY,
    get_faction_color,
)
from config import MAJOR_FACTIONS, FACTION_RANKS, get_rep_tier
from database import get_world_session, Faction, NPC, War, FactionRelation
from faction_engine import (
    get_player_rep, get_rep_status, get_all_factions,
    get_faction_summary, get_leader, get_advisor,
    can_join_faction, join_faction, leave_faction,
)
from npc_engine import get_faction_npc_summary


class FactionScreen:
    """Экран фракций."""

    def __init__(self, app):
        self.app = app
        self.selected_faction_id = None
        self._render()

    # ==================== РЕНДЕР ====================

    def _render(self):
        content = self.app.make_screen(
            "🏰 ФРАКЦИИ",
            color=FG_YELLOW,
            subtitle=self._subtitle()
        )

        main = tk.Frame(content, bg=BG_DARK)
        main.pack(fill="both", expand=True)

        # Левая колонка — список фракций
        left = tk.Frame(main, bg=BG_CARD, width=360)
        left.pack(side="left", fill="y", padx=(0, 15))
        left.pack_propagate(False)
        self._render_faction_list(left)

        # Правая колонка — детали выбранной
        right = tk.Frame(main, bg=BG_DARK)
        right.pack(side="left", fill="both", expand=True)
        self._render_faction_details(right)

    def _subtitle(self):
        p = self.app.player
        if p.faction_id:
            from faction_engine import get_faction
            f = get_faction(p.faction_id)
            fname = f.name if f else p.faction_id
            rank_name = p.faction_rank
            if p.faction_id and p.faction_rank:
                rank_name = FACTION_RANKS.get(p.faction_id, {}).get(
                    p.faction_rank, p.faction_rank
                )
            return f"Вы в: {fname}  |  Ранг: {rank_name}"
        return "Вы не состоите ни в одной фракции"

    # ==================== СПИСОК ФРАКЦИЙ ====================

    def _render_faction_list(self, parent):
        tk.Label(parent, text="СПИСОК ФРАКЦИЙ",
                 bg=BG_CARD, fg=FG_DIM,
                 font=FONT_SMALL).pack(anchor="w", padx=15, pady=(15, 8))

        world = get_world_session()
        try:
            factions = world.query(Faction).filter(
                Faction.id.in_(MAJOR_FACTIONS)
            ).all()
        finally:
            world.close()

        for faction in factions:
            self._render_faction_row(parent, faction)

    def _render_faction_row(self, parent, faction):
        rep = get_player_rep(self.app.player, faction.id)
        _, rep_name = get_rep_status(rep)

        is_my_faction = (self.app.player.faction_id == faction.id)
        is_selected = (self.selected_faction_id == faction.id)

        bg = BG_HOVER if is_selected else (
            "#1a2a1a" if is_my_faction else BG_MID
        )

        row = tk.Frame(parent, bg=bg, cursor="hand2")
        row.pack(fill="x", padx=10, pady=3)

        # Индикатор "моя фракция"
        if is_my_faction:
            tk.Label(row, text="✅",
                     bg=bg, fg=FG_ACCENT,
                     font=FONT_BODY).pack(side="left", padx=(10, 5), pady=8)

        # Имя
        tk.Label(row, text=faction.name,
                 bg=bg, fg=faction.color,
                 font=FONT_BODY, anchor="w").pack(
            side="left", fill="x", expand=True, pady=8)

        # Репутация
        rep_color = FG_ACCENT if rep >= 20 else (
            FG_DANGER if rep <= -50 else (
                FG_WARN if rep <= -20 else FG_DIM
            )
        )
        tk.Label(row, text=f"{rep:+d}",
                 bg=bg, fg=rep_color,
                 font=FONT_SMALL).pack(side="right", padx=10)

        # Клик
        def on_click(fid=faction.id):
            self.selected_faction_id = fid
            self._render()

        for w in [row] + list(row.winfo_children()):
            w.bind("<Button-1>", lambda e, c=on_click: c())

    # ==================== ДЕТАЛИ ФРАКЦИИ ====================

    def _render_faction_details(self, parent):
        if not self.selected_faction_id:
            tk.Label(parent, text="Выберите фракцию",
                     bg=BG_DARK, fg=FG_DIM,
                     font=FONT_HEADER).pack(pady=80)
            return

        fid = self.selected_faction_id
        summary = get_faction_summary(fid)
        if not summary:
            tk.Label(parent, text="Фракция не найдена",
                     bg=BG_DARK, fg=FG_DANGER,
                     font=FONT_HEADER).pack(pady=80)
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

        # Заголовок
        header = tk.Frame(inner, bg=BG_CARD)
        header.pack(fill="x", padx=10, pady=(10, 5))

        tk.Label(header, text=summary['name'],
                 bg=BG_CARD, fg=summary['color'],
                 font=FONT_HEADER).pack(anchor="w", padx=20, pady=(15, 3))

        tk.Label(header, text=summary['desc'],
                 bg=BG_CARD, fg=FG_DIM,
                 font=FONT_BODY,
                 wraplength=600, justify="left").pack(anchor="w", padx=20, pady=(0, 15))

        # Репутация игрока
        rep = get_player_rep(self.app.player, fid)
        _, rep_name = get_rep_status(rep)

        rep_frame = tk.Frame(inner, bg=BG_PANEL)
        rep_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(rep_frame, text="ВАША РЕПУТАЦИЯ:",
                 bg=BG_PANEL, fg=FG_DIM,
                 font=FONT_SMALL).pack(anchor="w", padx=15, pady=(10, 3))

        rep_color = FG_ACCENT if rep >= 20 else (
            FG_DANGER if rep <= -50 else (
                FG_WARN if rep <= -20 else FG_MAIN
            )
        )
        tk.Label(rep_frame, text=f"{rep:+d}  ({rep_name})",
                 bg=BG_PANEL, fg=rep_color,
                 font=FONT_SUB).pack(anchor="w", padx=15, pady=(0, 10))

        # Численность
        stats_frame = tk.Frame(inner, bg=BG_CARD)
        stats_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(stats_frame, text="СОСТАВ:",
                 bg=BG_CARD, fg=FG_DIM,
                 font=FONT_SMALL).pack(anchor="w", padx=15, pady=(10, 3))

        rows = [
            ("👥 Всего в составе", str(summary['population_total'])),
            ("💚 Живых", str(summary['population_alive'])),
            ("⚔️ Боевая мощь", f"{summary['military_strength']}/1000"),
            ("🎖️ Дисциплина", f"{summary['discipline']}/100"),
            ("✊ Мораль", f"{summary['morale']}/100"),
        ]

        for label, value in rows:
            row = tk.Frame(stats_frame, bg=BG_CARD)
            row.pack(fill="x", padx=15, pady=1)
            tk.Label(row, text=label,
                     bg=BG_CARD, fg=FG_DIM,
                     font=FONT_SMALL).pack(side="left")
            tk.Label(row, text=value,
                     bg=BG_CARD, fg=FG_MAIN,
                     font=FONT_SMALL).pack(side="right")

        tk.Label(stats_frame, text="",
                 bg=BG_CARD).pack(pady=3)

        # Руководство
        leadership_frame = tk.Frame(inner, bg=BG_PANEL)
        leadership_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(leadership_frame, text="РУКОВОДСТВО:",
                 bg=BG_PANEL, fg=FG_DIM,
                 font=FONT_SMALL).pack(anchor="w", padx=15, pady=(10, 3))

        leader = get_leader(fid)
        advisor = get_advisor(fid)

        if leader:
            ldr_row = tk.Frame(leadership_frame, bg=BG_PANEL)
            ldr_row.pack(fill="x", padx=15, pady=2)
            tk.Label(ldr_row, text=f"👑 {leader.name}",
                     bg=BG_PANEL, fg=FG_YELLOW,
                     font=FONT_BODY).pack(side="left")
            if leader.callsign:
                tk.Label(ldr_row, text=f"«{leader.callsign}»",
                         bg=BG_PANEL, fg=FG_DIM,
                         font=FONT_SMALL).pack(side="left", padx=5)
        else:
            tk.Label(leadership_frame, text="👑 Лидер: неизвестен",
                     bg=BG_PANEL, fg=FG_DIM,
                     font=FONT_BODY).pack(anchor="w", padx=15)

        if advisor:
            adv_row = tk.Frame(leadership_frame, bg=BG_PANEL)
            adv_row.pack(fill="x", padx=15, pady=2)
            tk.Label(adv_row, text=f"📜 {advisor.name}",
                     bg=BG_PANEL, fg=FG_BLUE,
                     font=FONT_BODY).pack(side="left")
            if advisor.callsign:
                tk.Label(adv_row, text=f"«{advisor.callsign}»",
                         bg=BG_PANEL, fg=FG_DIM,
                         font=FONT_SMALL).pack(side="left", padx=5)

        tk.Label(leadership_frame, text="",
                 bg=BG_PANEL).pack(pady=3)

        # Войны и союзы
        diplo_frame = tk.Frame(inner, bg=BG_CARD)
        diplo_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(diplo_frame, text="ДИПЛОМАТИЯ:",
                 bg=BG_CARD, fg=FG_DIM,
                 font=FONT_SMALL).pack(anchor="w", padx=15, pady=(10, 3))

        if summary['at_war_with']:
            for enemy_id in summary['at_war_with']:
                from faction_engine import get_faction
                ef = get_faction(enemy_id)
                ef_name = ef.name if ef else enemy_id
                tk.Label(diplo_frame, text=f"⚔️ Война с {ef_name}",
                         bg=BG_CARD, fg=FG_DANGER,
                         font=FONT_SMALL).pack(anchor="w", padx=15)
        if summary['allied_with']:
            for ally_id in summary['allied_with']:
                from faction_engine import get_faction
                af = get_faction(ally_id)
                af_name = af.name if af else ally_id
                tk.Label(diplo_frame, text=f"🤝 Союз с {af_name}",
                         bg=BG_CARD, fg=FG_ACCENT,
                         font=FONT_SMALL).pack(anchor="w", padx=15)

        if not summary['at_war_with'] and not summary['allied_with']:
            tk.Label(diplo_frame, text="— Нейтралитет —",
                     bg=BG_CARD, fg=FG_DIM,
                     font=FONT_SMALL).pack(anchor="w", padx=15)

        tk.Label(diplo_frame, text="",
                 bg=BG_CARD).pack(pady=3)

        # Действия
        actions_frame = tk.Frame(inner, bg=BG_DARK)
        actions_frame.pack(fill="x", padx=10, pady=15)

        self._render_actions(actions_frame, fid, rep)

    def _render_actions(self, parent, faction_id, rep):
        """Кнопки действий для фракции."""
        player = self.app.player

        # Уже в этой фракции
        if player.faction_id == faction_id:
            self.app.make_button(
                parent,
                "🚪 ПОКИНУТЬ ФРАКЦИЮ",
                lambda: self._leave_faction(),
                bg="#3a1a1a", fg=FG_DANGER,
                font=FONT_BODY,
            ).pack(side="left", padx=5)
            return

        # Уже в другой фракции
        if player.faction_id:
            tk.Label(parent,
                     text="Вы уже во фракции. Покиньте её, чтобы присоединиться к другой.",
                     bg=BG_DARK, fg=FG_WARN,
                     font=FONT_SMALL).pack(side="left")
            return

        # Может ли присоединиться?
        ok, msg = can_join_faction(player, faction_id)
        if ok:
            self.app.make_button(
                parent,
                f"✅ ПРИСОЕДИНИТЬСЯ К {faction_id.upper()}",
                lambda: self._join_faction(faction_id),
                bg="#1a3a1a", fg=FG_ACCENT,
                font=FONT_BODY,
            ).pack(side="left", padx=5)
        else:
            tk.Label(parent, text=f"⛔ {msg}",
                     bg=BG_DARK, fg=FG_WARN,
                     font=FONT_SMALL).pack(side="left")

    # ==================== ДЕЙСТВИЯ ====================

    def _join_faction(self, faction_id):
        result = join_faction(self.app.player, faction_id)
        if result.get('ok'):
            messagebox.showinfo("Фракция", result['message'])
            self.app.refresh_player()
            self._render()
        else:
            messagebox.showwarning("Фракция", result.get('message', 'Ошибка'))

    def _leave_faction(self):
        if not messagebox.askyesno("Покинуть фракцию?",
                                   "Вы уверены? Репутация упадёт."):
            return
        result = leave_faction(self.app.player)
        if result.get('ok'):
            messagebox.showinfo("Фракция", result['message'])
            self.app.refresh_player()
            self._render()
        else:
            messagebox.showwarning("Фракция", result.get('message', 'Ошибка'))