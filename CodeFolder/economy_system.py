# economy_system.py - Rad Earth
# Версия: 1.0.0
# Экономика. Цены, модификаторы по репутации, продажа/покупка, дефицит.

import os
import json
import random
from datetime import datetime

from config import (
    logger, JSON_ECONOMY, JSON_ITEMS,
    get_rep_price_modifier, get_rep_sell_modifier,
    REP_MIN, REP_MAX, clamp,
)
from database import (
    get_world_session, get_players_session,
    Player, NPC, Faction, Location, PlayerLog,
)


# ==================== ЗАГРУЗКА ПРЕДМЕТОВ ====================

_ITEMS_CACHE = None
_PRICES_CACHE = None


def _load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка чтения {path}: {e}")
        return default if default is not None else {}


def _load_items():
    """Загрузить все предметы из JsonFolder/items/*.json."""
    global _ITEMS_CACHE
    if _ITEMS_CACHE is not None:
        return _ITEMS_CACHE

    items = {}
    for fname in ['weapons.json', 'armor.json', 'junk.json',
                  'components.json', 'consumables.json']:
        path = os.path.join(JSON_ITEMS, fname)
        data = _load_json(path, {})
        category = fname.replace('.json', '')
        if isinstance(data, dict):
            for item_id, item_data in data.items():
                item_data['category'] = category
                items[item_id] = item_data
        elif isinstance(data, list):
            for item_data in data:
                iid = item_data.get('id')
                if iid:
                    item_data['category'] = category
                    items[iid] = item_data

    _ITEMS_CACHE = items
    logger.info(f"📦 Загружено {len(items)} предметов")
    return items


def _load_prices():
    """Загрузить базовые цены."""
    global _PRICES_CACHE
    if _PRICES_CACHE is not None:
        return _PRICES_CACHE

    path = os.path.join(JSON_ECONOMY, 'prices.json')
    _PRICES_CACHE = _load_json(path, {})
    return _PRICES_CACHE


def get_item(item_id):
    """Получить данные предмета."""
    return _load_items().get(item_id)


def get_base_price(item_id, buy=True):
    """Базовая цена предмета (до репутации)."""
    item = get_item(item_id)
    if not item:
        return None
    if buy:
        return item.get('price_buy', item.get('price', 0))
    return item.get('price_sell', int(item.get('price', 0) * 0.6))


# ==================== ЦЕНЫ С РЕПУТАЦИЕЙ ====================

def get_price_for_player(player, item_id, faction_id=None, buy=True):
    """Итоговая цена с учётом репутации игрока к фракции-торговцу."""
    base = get_base_price(item_id, buy=buy)
    if base is None:
        return None

    # Модификатор репутации
    rep = 0
    if faction_id:
        try:
            reps = json.loads(player.faction_rep or '{}')
            rep = reps.get(faction_id, 0)
        except Exception:
            rep = 0

    if buy:
        mult = get_rep_price_modifier(rep)
    else:
        mult = get_rep_sell_modifier(rep)

    final = int(base * mult)

    # Скидка друзьям фракции игрока
    if faction_id and player.faction_id == faction_id and buy:
        final = int(final * 0.9)

    return {
        'base': base,
        'final': max(1, final),
        'mult': mult,
        'rep': rep,
    }


# ==================== ПОКУПКА ====================

def buy_item(player_id, item_id, count=1, trader_faction=None):
    """Купить предмет у торговца."""
    players = get_players_session()
    try:
        player = players.query(Player).filter_by(id=player_id).first()
        if not player:
            return {'ok': False, 'message': 'Игрок не найден'}

        item = get_item(item_id)
        if not item:
            return {'ok': False, 'message': 'Товар не найден'}

        # Проверка уровня
        req_level = item.get('level_required', 1)
        if player.level < req_level:
            return {'ok': False, 'message': f'Нужен {req_level} уровень'}

        price_info = get_price_for_player(player, item_id, trader_faction, buy=True)
        total = price_info['final'] * count

        if player.radcoins < total:
            return {'ok': False, 'message': f'Нужно {total} RC, у вас {int(player.radcoins)}'}

        player.radcoins -= total
        _add_to_inventory(player, item_id, count)
        player.total_purchases = (player.total_purchases or 0) + count

        log = PlayerLog(player_id=player_id, action='buy',
                        amount_rc=-total, item=f"{item_id}x{count}")
        players.add(log)
        players.commit()

        return {
            'ok': True,
            'message': f"Куплено {item.get('name', item_id)} x{count} за {total} RC",
            'total': total,
            'price_info': price_info,
        }
    except Exception as e:
        logger.error(f"Ошибка покупки: {e}")
        players.rollback()
        return {'ok': False, 'message': str(e)}
    finally:
        players.close()


# ==================== ПРОДАЖА ====================

def sell_item(player_id, item_id, count=1, trader_faction=None):
    """Продать предмет торговцу."""
    players = get_players_session()
    try:
        player = players.query(Player).filter_by(id=player_id).first()
        if not player:
            return {'ok': False, 'message': 'Игрок не найден'}

        have = _count_in_inventory(player, item_id)
        if have < count:
            return {'ok': False, 'message': f'У вас только {have} шт'}

        price_info = get_price_for_player(player, item_id, trader_faction, buy=False)
        total = price_info['final'] * count

        _remove_from_inventory(player, item_id, count)
        player.radcoins += total

        log = PlayerLog(player_id=player_id, action='sell',
                        amount_rc=total, item=f"{item_id}x{count}")
        players.add(log)
        players.commit()

        item = get_item(item_id) or {}
        return {
            'ok': True,
            'message': f"Продано {item.get('name', item_id)} x{count} за {total} RC",
            'total': total,
            'price_info': price_info,
        }
    except Exception as e:
        logger.error(f"Ошибка продажи: {e}")
        players.rollback()
        return {'ok': False, 'message': str(e)}
    finally:
        players.close()


# ==================== ИНВЕНТАРЬ ====================

def _add_to_inventory(player, item_id, count=1):
    inv = json.loads(player.inventory or '[]')
    for entry in inv:
        if entry.get('item') == item_id:
            entry['count'] = entry.get('count', 0) + count
            break
    else:
        inv.append({'item': item_id, 'count': count})
    player.inventory = json.dumps(inv)


def _remove_from_inventory(player, item_id, count=1):
    inv = json.loads(player.inventory or '[]')
    new_inv = []
    for entry in inv:
        if entry.get('item') == item_id:
            entry['count'] = entry.get('count', 0) - count
            if entry['count'] > 0:
                new_inv.append(entry)
        else:
            new_inv.append(entry)
    player.inventory = json.dumps(new_inv)


def _count_in_inventory(player, item_id):
    inv = json.loads(player.inventory or '[]')
    for entry in inv:
        if entry.get('item') == item_id:
            return entry.get('count', 0)
    return 0


# ==================== СПИСОК ТОВАРОВ ТОРГОВЦА ====================

def get_trader_stock(faction_id, trader_type='mixed'):
    """Список товаров, которые продаёт торговец фракции."""
    items = _load_items()
    stock = []

    for item_id, item in items.items():
        # Фильтр по типу торговца
        if trader_type != 'mixed':
            cat = item.get('category', '')
            if trader_type == 'weapons' and cat != 'weapons':
                continue
            if trader_type == 'armor' and cat != 'armor':
                continue
            if trader_type == 'junk' and cat not in ('junk', 'components'):
                continue

        stock.append({
            'id': item_id,
            'name': item.get('name', item_id),
            'category': item.get('category', 'misc'),
            'base_price': item.get('price_buy', item.get('price', 0)),
            'level_required': item.get('level_required', 1),
        })

    return stock


# ==================== ДИНАМИЧЕСКИЕ ЦЕНЫ (дефицит) ====================

def apply_scarcity(item_id, base_price, location_id, world_session):
    """Учесть дефицит предмета в локации. Если локация бедная — цена выше."""
    # Пока — заглушка. Позже: считать количество предметов у NPC в локации.
    return base_price


# ==================== ПРОЧЕЕ ====================

def reload_items():
    """Сбросить кэш предметов (после изменения JSON)."""
    global _ITEMS_CACHE, _PRICES_CACHE
    _ITEMS_CACHE = None
    _PRICES_CACHE = None
    logger.info("🔄 Кэш предметов сброшен")


def get_all_items():
    """Все предметы."""
    return _load_items()


def get_items_by_category(category):
    """Предметы по категории."""
    return {iid: it for iid, it in _load_items().items()
            if it.get('category') == category}