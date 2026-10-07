# utils.py - Rad Earth
# Версия: 1.0.0
# Утилиты. Инвентарь, экипировка, опыт, уровни, лут, расчёты, логирование.

import os
import json
import random
from datetime import datetime

from config import (
    logger, MAX_LEVEL, MAX_INVENTORY_STACK, get_exp_for_level, clamp,
)
from database import (
    get_players_session, get_world_session,
    Player, PlayerLog,
)


# ==================== ИНВЕНТАРЬ ====================

def get_inventory(player):
    """Получить инвентарь как список."""
    if not player or not player.inventory:
        return []
    try:
        return json.loads(player.inventory)
    except Exception:
        return []


def save_inventory(player, inventory):
    """Сохранить инвентарь."""
    player.inventory = json.dumps(inventory, ensure_ascii=False)


def add_item_to_inventory(player, item_id, count=1):
    """Добавить предмет в инвентарь."""
    if count <= 0:
        return
    inv = get_inventory(player)
    for entry in inv:
        if entry.get('item') == item_id:
            entry['count'] = min(
                MAX_INVENTORY_STACK,
                entry.get('count', 0) + count
            )
            save_inventory(player, inv)
            return
    inv.append({'item': item_id, 'count': min(count, MAX_INVENTORY_STACK)})
    save_inventory(player, inv)


def remove_item_from_inventory(player, item_id, count=1):
    """Убрать предмет из инвентаря."""
    if count <= 0:
        return False
    inv = get_inventory(player)
    new_inv = []
    found = False
    for entry in inv:
        if entry.get('item') == item_id:
            entry['count'] = entry.get('count', 0) - count
            if entry['count'] > 0:
                new_inv.append(entry)
            found = True
        else:
            new_inv.append(entry)
    if found:
        save_inventory(player, new_inv)
    return found


def get_item_count(player, item_id):
    """Сколько предметов данного типа в инвентаре."""
    inv = get_inventory(player)
    for entry in inv:
        if entry.get('item') == item_id:
            return entry.get('count', 0)
    return 0


def has_item(player, item_id, count=1):
    """Есть ли предмет в нужном количестве."""
    return get_item_count(player, item_id) >= count


# ==================== ЭКИПИРОВКА ====================

def get_equipped(player):
    """Получить экипировку."""
    if not player or not player.equipped:
        return {'weapon': None, 'armor': None}
    try:
        eq = json.loads(player.equipped)
        eq.setdefault('weapon', None)
        eq.setdefault('armor', None)
        return eq
    except Exception:
        return {'weapon': None, 'armor': None}


def save_equipped(player, equipped):
    """Сохранить экипировку."""
    player.equipped = json.dumps(equipped)


def get_weapon_damage(player):
    """Урон текущего оружия."""
    from economy_system import get_item
    eq = get_equipped(player)
    weapon_id = eq.get('weapon')
    if not weapon_id:
        return 10
    item = get_item(weapon_id)
    return item.get('damage', 10) if item else 10


def get_armor_defense(player):
    """Защита текущей брони (0..1)."""
    from economy_system import get_item
    eq = get_equipped(player)
    armor_id = eq.get('armor')
    if not armor_id:
        return 0.0
    item = get_item(armor_id)
    return item.get('defense', 0.0) if item else 0.0


# ==================== ОПЫТ И УРОВНИ ====================

def add_experience(player, exp_gain):
    """Начислить опыт (без проверки уровня)."""
    if exp_gain <= 0:
        return
    player.experience = (player.experience or 0) + exp_gain


def check_level_up(player, exp_gain=0):
    """Начислить опыт и повысить уровни, если хватает. Возвращает True при level up."""
    if exp_gain:
        player.experience = (player.experience or 0) + exp_gain

    leveled = False
    while player.level < MAX_LEVEL:
        next_exp = get_exp_for_level(player.level + 1)
        if player.experience >= next_exp:
            player.level += 1
            leveled = True
        else:
            break
    return leveled


def get_progress_to_next_level(player):
    """Прогресс до следующего уровня: (текущий, всего)."""
    current = player.experience or 0
    current_level_exp = get_exp_for_level(player.level)
    next_level_exp = get_exp_for_level(player.level + 1)
    progress = current - current_level_exp
    total = next_level_exp - current_level_exp
    return max(0, progress), max(1, total)


# ==================== ЛОГИРОВАНИЕ ====================

def safe_log(player, action, rc=0, rf=0, crystals=0, item=None, details=None):
    """Записать действие игрока в лог."""
    if not player:
        return
    try:
        players = get_players_session()
        try:
            log = PlayerLog(
                player_id=player.id,
                action=action,
                amount_rc=rc,
                amount_rf=rf,
                amount_crystals=crystals,
                item=item,
                details=json.dumps(details) if details else None,
                timestamp=datetime.now(),
            )
            players.add(log)
            players.commit()
        finally:
            players.close()
    except Exception as e:
        logger.error(f"Ошибка логирования: {e}")


# ==================== ЛУТ ====================

JUNK_POOL = [
    'ручка_пластик', 'бутылка_пластик', 'пакет',
    'гайка', 'болт', 'гвоздь', 'проволока', 'жесть', 'труба_металл',
    'бутылка_стекло', 'осколок',
    'микросхема', 'провод', 'батарейка', 'телефон_старый', 'радио_деталь',
    'покрышка', 'резина_полоса',
    'тряпка', 'ботинок', 'перчатка',
    'термос', 'ложка', 'кружка', 'книга', 'фото', 'кукла',
    'наручные_часы', 'монета', 'ключ', 'линза', 'магнит',
    'пружина', 'шестеренка', 'лампочка',
]


def roll_loot(multiplier=1.0, count=None):
    """Случайный лут. Возвращает список (item_id, item_name, count)."""
    from economy_system import get_all_items
    items = get_all_items()

    # Сколько попыток
    if count is None:
        count = random.randint(1, 3)

    found = []
    for _ in range(count):
        chance = random.random() * 100 * multiplier
        # Простой ролл по хламу
        if chance < 30 and JUNK_POOL:
            item_id = random.choice(JUNK_POOL)
            item = items.get(item_id, {})
            found.append((item_id, item.get('name', item_id), 1))

    return found


def roll_rare_loot(multiplier=1.0):
    """Редкий лут (из оружия/брони)."""
    from economy_system import get_items_by_category
    weapons = list(get_items_by_category('weapons').values())
    armors = list(get_items_by_category('armor').values())

    pool = weapons + armors
    if not pool:
        return []

    if random.random() * 100 < 5 * multiplier:
        item = random.choice(pool)
        return [(item.get('id'), item.get('name', item.get('id')), 1)]
    return []


# ==================== БОЕВЫЕ РАСЧЁТЫ ====================

def calculate_survive_chance(player, enemy_tier=1):
    """Шанс выжить в бою с врагом указанного уровня (в %)."""
    base = 20  # базовый шанс
    defense = get_armor_defense(player)
    base += int(defense * 50)

    # Питомец-волк даёт бонус
    if player.pet == 'волк':
        base += 10

    # Уровень врага
    base -= (enemy_tier - 1) * 15

    return clamp(base, 5, 95)


# ==================== ПРОЧЕЕ ====================

def safe_json_load(text, default=None):
    """Безопасный JSON-парсинг."""
    if default is None:
        default = {}
    if not text:
        return default
    try:
        return json.loads(text)
    except Exception:
        return default


def format_seconds(seconds):
    """Форматировать секунды в читаемый вид."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}с"
    if seconds < 3600:
        return f"{seconds // 60}м"
    if seconds < 86400:
        return f"{seconds // 3600}ч {(seconds % 3600) // 60}м"
    return f"{seconds // 86400}д {(seconds % 86400) // 3600}ч"


def format_number(num):
    """Форматировать число с разрядами."""
    try:
        return f"{int(num):,}".replace(',', ' ')
    except Exception:
        return str(num)


def get_username_by_id(player_id):
    """Имя игрока по ID."""
    players = get_players_session()
    try:
        p = players.query(Player).filter_by(id=player_id).first()
        return p.username if p else f"Player{player_id}"
    finally:
        players.close()