# game.py - Rad Earth
# Версия: 1.0.0
# Главное окно tkinter. Меню, стек экранов, навигация, тема.

import tkinter as tk
from tkinter import messagebox

from config import (
    GAME_NAME, GAME_VERSION, GAME_SUBTITLE,
    FACTION_COLORS, get_faction_color,
)
from database import (
    get_players_session, Player,
    get_world_session, Faction, NPC, Location,
)
from theme import (
    BG_DARK, BG_MID, BG_PANEL, BG_CARD, BG_HOVER,
    FG_MAIN, FG_DIM, FG_ACCENT, FG_WARN, FG_DANGER,
    FONT_TITLE, FONT_HEADER, FONT_SUB, FONT_BODY, FONT_SMALL, FONT_TINY,
    setup_theme,
)


# ==================== ГЛАВНОЕ ПРИЛОЖЕНИЕ ====================

class RadEarthApp:
    def __init__(self, root, player_id=None):
        self.root = root
        self.root.title(f"{GAME_NAME} v{GAME_VERSION}")
        self.root.configure(bg=BG_DARK)
        self.root.attributes("-fullscreen", True)

        self.root.bind("<Escape>", self._on_escape)
        self.root.bind("<F11>", self._toggle_fullscreen)
        self.root.bind("<Control-q>", lambda e: self._quit())

        self.player_id = player_id
        self.player = None
        self.current_frame = None
        self.screen_stack = []

        self._load_player()

        if not self.player:
            self.show_login()
        else:
            self.show_main_menu()

    # ==================== ЗАГРУЗКА ИГРОКА ====================

    def _load_player(self):
        if not self.player_id:
            return
        players = get_players_session()
        try:
            self.player = players.query(Player).filter_by(id=self.player_id).first()
        finally:
            players.close()

    def refresh_player(self):
        """Перечитать игрока из базы."""
        if not self.player_id:
            return
        players = get_players_session()
        try:
            self.player = players.query(Player).filter_by(id=self.player_id).first()
        finally:
            players.close()

    def save_player(self):
        """Сохранить игрока (в базе через expire_on_commit=False — уже сохраняется)."""
        self.refresh_player()

    # ==================== НАВИГАЦИЯ ====================

    def _toggle_fullscreen(self, event=None):
        self.root.attributes("-fullscreen",
                             not self.root.attributes("-fullscreen"))

    def _on_escape(self, event=None):
        self.pop_screen()

    def _quit(self):
        if messagebox.askyesno("Выход", "Выйти из игры?"):
            self.root.quit()

    def push_screen(self, func):
        self.screen_stack.append(func)

    def pop_screen(self):
        if len(self.screen_stack) > 1:
            self.screen_stack.pop()
            prev = self.screen_stack.pop()
            prev()
        else:
            self.show_main_menu()

    def go_main(self):
        self.screen_stack = []
        self.refresh_player()
        self.show_main_menu()

    # ==================== UI-ХЕЛПЕРЫ ====================

    def clear(self):
        if self.current_frame:
            self.current_frame.destroy()
        self.current_frame = tk.Frame(self.root, bg=BG_DARK)
        self.current_frame.pack(fill="both", expand=True)
        return self.current_frame

    def make_button(self, parent, text, command, bg=BG_MID, fg=FG_MAIN,
                    font=FONT_BODY, width=None, height=None, pad=(15, 8)):
        btn = tk.Button(
            parent, text=text, command=command,
            bg=bg, fg=fg,
            activebackground=BG_HOVER, activeforeground="#ffffff",
            font=font, relief="flat", cursor="hand2",
            borderwidth=0, highlightthickness=0,
            padx=pad[0], pady=pad[1],
        )
        if width:
            btn.configure(width=width)
        if height:
            btn.configure(height=height)
        return btn

    def make_label(self, parent, text, font=FONT_BODY, fg=FG_MAIN, bg=BG_DARK,
                   anchor="w", wraplength=0):
        return tk.Label(parent, text=text, font=font, fg=fg, bg=bg,
                        anchor=anchor, justify="left", wraplength=wraplength)

    def make_screen(self, title, color=FG_ACCENT, subtitle=None):
        """Стандартный экран с шапкой и подвалом. Возвращает content-frame."""
        f = self.clear()

        header = tk.Frame(f, bg=BG_PANEL)
        header.pack(fill="x")
        tk.Label(header, text=title, bg=BG_PANEL, fg=color,
                 font=FONT_HEADER).pack(pady=12)
        if subtitle:
            tk.Label(header, text=subtitle, bg=BG_PANEL, fg=FG_DIM,
                     font=FONT_SMALL).pack(pady=(0, 10))

        content = tk.Frame(f, bg=BG_DARK)
        content.pack(fill="both", expand=True, padx=40, pady=15)

        bottom = tk.Frame(f, bg=BG_DARK)
        bottom.pack(side="bottom", fill="x", pady=6)
        tk.Label(bottom,
                 text="Esc — назад  |  F11 — оконный режим  |  Ctrl+Q — выход",
                 font=FONT_TINY, fg=FG_DIM, bg=BG_DARK).pack()

        return content

    # ==================== ЭКРАН ЛОГИНА ====================

    def show_login(self):
        f = self.clear()
        center = tk.Frame(f, bg=BG_DARK)
        center.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(center, text=f"☢️  {GAME_NAME}  ☢️", font=FONT_TITLE,
                 fg=FG_ACCENT, bg=BG_DARK).pack(pady=(0, 10))
        tk.Label(center, text=f"— {GAME_SUBTITLE} —",
                 font=("Consolas", 15), fg=FG_DIM, bg=BG_DARK).pack(pady=(0, 50))

        tk.Label(center, text="Имя выжившего:",
                 font=FONT_BODY, fg=FG_DIM, bg=BG_DARK).pack()

        entry = tk.Entry(center, font=("Consolas", 20), bg=BG_PANEL,
                         fg=FG_MAIN, insertbackground=FG_ACCENT,
                         relief="flat", justify="center", width=20)
        entry.pack(pady=15, ipady=10)
        entry.insert(0, "диаз")
        entry.focus()

        def do_login():
            name = entry.get().strip()
            if not name:
                messagebox.showwarning("Ошибка", "Введите имя")
                return
            if self._create_or_load_player(name):
                self.show_main_menu()

        entry.bind("<Return>", lambda e: do_login())
        self.make_button(center, "▶  ВОЙТИ В ПУСТОШЬ", do_login,
                         bg="#1a3a1a", fg=FG_ACCENT, font=FONT_SUB).pack(
            pady=25)

    def _create_or_load_player(self, name):
        """Создать нового игрока или загрузить существующего."""
        players = get_players_session()
        try:
            existing = players.query(Player).filter_by(username=name).first()
            if existing:
                self.player = existing
                self.player_id = existing.id
                return True

            from config import (
                START_RADCOINS, START_RADFRAGMENTS, START_RADCRYSTALS,
                START_LEVEL, START_EXPERIENCE, START_LOCATION,
            )
            player = Player(
                username=name,
                radcoins=START_RADCOINS,
                radfragments=START_RADFRAGMENTS,
                radcrystals=START_RADCRYSTALS,
                level=START_LEVEL,
                experience=START_EXPERIENCE,
                current_location=START_LOCATION,
                faction_rep='{}',
                inventory='[]',
                equipped='{}',
                achievements='[]',
            )
            players.add(player)
            players.commit()
            self.player = player
            self.player_id = player.id
            return True
        except Exception as e:
            players.rollback()
            messagebox.showerror("Ошибка", f"Не удалось создать игрока: {e}")
            return False
        finally:
            players.close()

    # ==================== ГЛАВНОЕ МЕНЮ ====================

    def show_main_menu(self):
        self.screen_stack = [self.show_main_menu]
        self.refresh_player()

        if not self.player:
            self.show_login()
            return

        f = self.clear()

        # Заголовок
        header = tk.Frame(f, bg=BG_PANEL, height=64)
        header.pack(fill="x")
        header.pack_propagate(False)

        left_header = tk.Frame(header, bg=BG_PANEL)
        left_header.pack(side="left", padx=30, pady=12)
        tk.Label(left_header, text=f"☢️  {GAME_NAME}",
                 bg=BG_PANEL, fg=FG_ACCENT,
                 font=("Consolas", 22, "bold")).pack(anchor="w")

        # Текущая локация
        loc_name = "—"
        if self.player.current_location:
            world = get_world_session()
            try:
                loc = world.query(Location).filter_by(
                    id=self.player.current_location
                ).first()
                if loc:
                    loc_name = loc.name
            finally:
                world.close()

        tk.Label(left_header, text=f"📍 {loc_name}",
                 bg=BG_PANEL, fg=FG_DIM, font=FONT_SMALL).pack(anchor="w")

        # Правая часть — фракция игрока
        right_header = tk.Frame(header, bg=BG_PANEL)
        right_header.pack(side="right", padx=30, pady=12)

        if self.player.faction_id:
            faction_name = self.player.faction_id
            world = get_world_session()
            try:
                faction = world.query(Faction).filter_by(
                    id=self.player.faction_id
                ).first()
                if faction:
                    faction_name = faction.name
            finally:
                world.close()
            tk.Label(right_header, text=faction_name,
                     bg=BG_PANEL,
                     fg=get_faction_color(self.player.faction_id),
                     font=("Consolas", 12, "bold")).pack(anchor="e")
            tk.Label(right_header, text=f"Ранг: {self.player.faction_rank or '—'}",
                     bg=BG_PANEL, fg=FG_DIM, font=FONT_TINY).pack(anchor="e")
        else:
            tk.Label(right_header, text="Без фракции",
                     bg=BG_PANEL, fg=FG_DIM,
                     font=("Consolas", 12, "bold")).pack(anchor="e")

        # Статус-бар
        self._render_status_bar(f)

        # Сетка кнопок
        grid = tk.Frame(f, bg=BG_DARK)
        grid.pack(expand=True, fill="both", padx=50, pady=15)

        menu = [
            ("🎲", "ВЫЛАЗКА", "В пустошь", self.show_expedition, "#1a3a1a", FG_ACCENT),
            ("🏹", "ОХОТА", "Выследить", self.show_hunt, "#3a1a1a", "#ffaa44"),
            ("🗺️", "КАРТА", "Путешествие", self.show_map, "#1a1a3a", "#66ccff"),
            ("🏭", "БИЗНЕС", "Управление", self.show_business, "#1a1a3a", "#66ccff"),
            ("🎁", "СУНДУКИ", "Открыть", self.show_chests, "#3a3a1a", "#ffee66"),
            ("📦", "ИНВЕНТАРЬ", "Вещи", self.show_inventory, "#1a3a3a", "#88ffff"),
            ("🧙", "ТОРГОВЕЦ", "Местный", self.show_trader, "#2a1a3a", "#cc88ff"),
            ("👤", "ПРОФИЛЬ", "Статы", self.show_profile, BG_CARD, FG_MAIN),
            ("🏰", "ФРАКЦИИ", "Отношения", self.show_factions, BG_CARD, "#ffaa44"),
            ("👥", "NPC", "Память", self.show_npc_memory, BG_CARD, "#88ffff"),
            ("🏆", "ТОПЫ", "Рейтинг", self.show_top, BG_CARD, "#ffee66"),
            ("📻", "РАДИО", "Эфир", self.show_radio, BG_CARD, "#66ccff"),
            ("🏅", "ДОСТИЖЕНИЯ", "Награды", self.show_achievements, BG_CARD, "#ffee66"),
            ("❓", "ПОМОЩЬ", "Подсказки", self.show_help, BG_CARD, FG_DIM),
        ]

        cols = 5
        for i, (emoji, name, desc, cmd, bg, fg) in enumerate(menu):
            r, c = i // cols, i % cols
            card = tk.Frame(grid, bg=bg, cursor="hand2")
            card.grid(row=r, column=c, padx=6, pady=6, sticky="nsew")
            inner = tk.Frame(card, bg=bg)
            inner.pack(expand=True, fill="both", padx=10, pady=10)

            tk.Label(inner, text=emoji, font=("Consolas", 32),
                     bg=bg, fg=fg).pack(pady=(0, 2))
            tk.Label(inner, text=name, font=("Consolas", 12, "bold"),
                     bg=bg, fg=fg).pack()
            tk.Label(inner, text=desc, font=FONT_SMALL,
                     bg=bg, fg=FG_DIM).pack(pady=(1, 0))

            def make_click(c=cmd):
                return lambda e: c()

            def make_hover(card=card, inner=inner, bg=bg):
                def enter(e):
                    card.configure(bg=BG_HOVER)
                    inner.configure(bg=BG_HOVER)
                    for w in inner.winfo_children():
                        w.configure(bg=BG_HOVER)
                def leave(e):
                    card.configure(bg=bg)
                    inner.configure(bg=bg)
                    for w in inner.winfo_children():
                        w.configure(bg=bg)
                return enter, leave

            enter, leave = make_hover()
            for w in [card, inner] + list(inner.winfo_children()):
                w.bind("<Button-1>", make_click())
                w.bind("<Enter>", enter)
                w.bind("<Leave>", leave)

        for i in range(cols):
            grid.grid_columnconfigure(i, weight=1)
        for i in range((len(menu) + cols - 1) // cols):
            grid.grid_rowconfigure(i, weight=1)

        # Подвал
        bottom = tk.Frame(f, bg=BG_DARK)
        bottom.pack(side="bottom", fill="x", pady=8)
        self.make_button(bottom, "❌ ВЫХОД", self._quit,
                         bg="#3a1a1a", fg=FG_DANGER).pack(side="left", padx=30)
        tk.Label(bottom,
                 text="Esc — назад  |  F11 — оконный режим  |  Ctrl+Q — выход",
                 font=FONT_SMALL, fg=FG_DIM, bg=BG_DARK).pack(side="right", padx=30)

    def _render_status_bar(self, parent):
        p = self.player

        bar = tk.Frame(parent, bg=BG_MID, height=80)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        # Левая часть — имя и класс
        left = tk.Frame(bar, bg=BG_MID)
        left.pack(side="left", padx=30, pady=10)
        tk.Label(left, text=f"👤 {p.username}", bg=BG_MID, fg=FG_MAIN,
                 font=("Consolas", 16, "bold"), anchor="w").pack(anchor="w")

        class_ru = {
            'stalker': '🟢 Сталкер',
            'military': '🔫 Военный',
            'bandit': '🗡️ Бандит',
            'scientist': '🔬 Учёный',
        }
        cls = class_ru.get(p.user_class, p.user_class)
        tk.Label(left, text=f"🎭 {cls}", bg=BG_MID, fg=FG_DIM,
                 font=FONT_SMALL, anchor="w").pack(anchor="w")

        # Центр — ресурсы
        center = tk.Frame(bar, bg=BG_MID)
        center.pack(side="left", expand=True)
        res = tk.Frame(center, bg=BG_MID)
        res.pack()

        tk.Label(res, text=f"⚠️ Ур.{p.level}", bg=BG_MID, fg="#ffaa44",
                 font=("Consolas", 15, "bold")).pack(side="left", padx=15)
        tk.Label(res, text=f"☢️ {int(p.radcoins)}", bg=BG_MID, fg=FG_ACCENT,
                 font=("Consolas", 15, "bold")).pack(side="left", padx=15)
        tk.Label(res, text=f"☣️ {p.radfragments}", bg=BG_MID, fg="#cc88ff",
                 font=("Consolas", 15, "bold")).pack(side="left", padx=15)
        tk.Label(res, text=f"💎 {p.radcrystals}", bg=BG_MID, fg="#66ccff",
                 font=("Consolas", 15, "bold")).pack(side="left", padx=15)

        # Правая часть — экипировка и питомец
        right = tk.Frame(bar, bg=BG_MID)
        right.pack(side="right", padx=30, pady=10)

        extras = []
        try:
            import json as _json
            eq = _json.loads(p.equipped or '{}')
            if eq.get('armor'): extras.append(f"🛡 {eq['armor']}")
            if eq.get('weapon'): extras.append(f"⚔ {eq['weapon']}")
        except Exception:
            pass
        if p.pet:
            extras.append(f"🐾 {p.pet}")

        tk.Label(right,
                 text="   ".join(extras) if extras else "— без экипировки —",
                 bg=BG_MID, fg=FG_DIM, font=FONT_SMALL,
                 anchor="e").pack(anchor="e")

    # ==================== ЭКРАНЫ-ЗАГЛУШКИ (будут в screen_*.py) ====================

    def show_expedition(self):
        try:
            from screen_expedition import ExpeditionScreen
            ExpeditionScreen(self)
        except ImportError:
            self._stub("Вылазка в разработке")

    def show_hunt(self):
        self._stub("Охота в разработке")

    def show_map(self):
        try:
            from screen_map import MapScreen
            MapScreen(self)
        except ImportError:
            self._stub("Карта в разработке")

    def show_business(self):
        self._stub("Бизнес в разработке")

    def show_chests(self):
        self._stub("Сундуки в разработке")

    def show_inventory(self):
        try:
            from screen_inventory import InventoryScreen
            InventoryScreen(self)
        except ImportError:
            self._stub("Инвентарь в разработке")

    def show_trader(self):
        self._stub("Торговец в разработке")

    def show_profile(self):
        try:
            from screen_profile import ProfileScreen
            ProfileScreen(self)
        except ImportError:
            self._stub("Профиль в разработке")

    def show_factions(self):
        try:
            from screen_faction import FactionScreen
            FactionScreen(self)
        except ImportError:
            self._stub("Фракции в разработке")

    def show_npc_memory(self):
        self._stub("Память NPC в разработке")

    def show_top(self):
        self._stub("Топы в разработке")

    def show_radio(self):
        try:
            from screen_radio import RadioScreen
            RadioScreen(self)
        except ImportError:
            self._stub("Радио в разработке")

    def show_achievements(self):
        self._stub("Достижения в разработке")

    def show_help(self):
        self._stub("Помощь в разработке")

    def _stub(self, message):
        content = self.make_screen("🚧", color=FG_WARN)
        tk.Label(content, text=message, font=FONT_HEADER,
                 fg=FG_DIM, bg=BG_DARK).pack(pady=40)
        self.make_button(content, "🔙 В МЕНЮ", self.go_main,
                         bg=BG_MID, fg=FG_MAIN).pack(pady=10)


# ==================== ЗАПУСК ====================

def run(player_id=None):
    """Запустить игру. Если player_id=None — показать логин."""
    root = tk.Tk()
    app = RadEarthApp(root, player_id=player_id)
    root.mainloop()


if __name__ == '__main__':
    run()