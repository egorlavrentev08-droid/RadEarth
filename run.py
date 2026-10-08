# run.py - Rad Earth
# Версия: 1.0.0
# Корневой лаунчер. Запускает игру: загружает мир, инициализирует БД,
# открывает главное окно tkinter, запускает тикер мира.

import os
import sys
import traceback
from datetime import datetime


# ==================== ПУТИ ====================

# Корень проекта — папка, где лежит run.py
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.join(ROOT_DIR, 'CodeFolder')

# Добавляем CodeFolder в PYTHONPATH, чтобы импорты работали
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)


# ==================== БАННЕР ====================

def print_banner():
    """Красивый баннер при запуске."""
    banner = r"""
    ____        _   _____      _   _   
   |  _ \ __ _ | | | ____|__ _| |_| |_ 
   | |_) / _` || | |  _| / _` | __| __|
   |  _ < (_| || | | |__| (_| | |_| |_ 
   |_| \_\__,_||_| |_____\__,_|\__|\__|
    """
    print(banner)
    print("    Симуляция Пустоши  |  v1.0.0")
    print("    " + "─" * 50)
    print()


# ==================== ЗАПУСК ====================

def main():
    """Точка входа."""
    print_banner()

    try:
        # 1. Загружаем конфиг (создаёт папки)
        print("⚙️  Загрузка конфигурации...")
        import config
        print(f"   ✅ {config.GAME_NAME} v{config.GAME_VERSION}")
        print(f"   📂 ROOT: {config.ROOT_DIR}")
        print()

        # 2. Инициализируем БД (создаёт таблицы)
        print("💾 Инициализация баз данных...")
        import database
        print(f"   ✅ players.db: {os.path.basename(database.PLAYERS_DB)}")
        print(f"   ✅ world.db: {os.path.basename(database.WORLD_DB)}")
        print()

        # 3. Загружаем мир (если ещё не загружен)
        print("🌍 Проверка мира...")
        from world_loader import ensure_world_loaded
        ensure_world_loaded()
        print()

        # 4. Инициализируем погоду
        print("🌤️  Инициализация погоды...")
        from weather_system import init_weather
        init_weather()
        weather_current = None
        try:
            from weather_system import get_weather_view
            weather_current = get_weather_view()
        except Exception:
            pass
        if weather_current:
            print(f"   ✅ Текущая: {weather_current.get('name', '—')}")
        print()

        # 5. Проверяем ключевые модули на импорт
        print("🔍 Проверка модулей...")
        modules = [
            'utils',
            'economy_system',
            'faction_engine',
            'npc_engine',
            'map_engine',
            'radio_system',
            'dialog_system',
            'game_logic',
            'player_logic',
            'world_tick',
            'theme',
        ]
        for mod in modules:
            try:
                __import__(mod)
                print(f"   ✅ {mod}")
            except Exception as e:
                print(f"   ⚠️  {mod}: {e}")
        print()

        # 6. Открываем главное окно
        print("🖥️  Запуск интерфейса...")
        print("   " + "─" * 50)

        import tkinter as tk
        from game import RadEarthApp
        from world_tick import start_ticker

        root = tk.Tk()
        app = RadEarthApp(root, player_id=None)

        # Запускаем тикер мира (в tkinter-потоке через root.after)
        start_ticker(root, interval_seconds=60)

        print()
        print("   ✅ Игра запущена. Закрывайте окно — завершение.")
        print("   " + "─" * 50)
        print()

        root.mainloop()

        # После закрытия окна
        print("\n👋 Игра завершена. До встречи в Пустоши.\n")

    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем. Выход...\n")
    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ ОШИБКА ЗАПУСКА")
        print("=" * 60)
        traceback.print_exc()
        print("=" * 60)
        print(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60 + "\n")
        sys.exit(1)


# ==================== ЗАПУСК ====================

if __name__ == '__main__':
    main()
