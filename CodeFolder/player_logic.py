# player_logic.py - Rad Earth
# Версия: 1.0.0
# Логика игрока. Профиль, статистика, инвентарь, экипировка, эффекты,
# переходы между локациями, сон, еда, лечение.

import os
import json
import random
from datetime import datetime, timedelta

from config import (
    logger, MAX_LEVEL, MAX_INVENTORY_STACK,
    START_LOCATION, get_exp_for_level, clamp,
)
from database import (
    get_players_session, get_world_session,
    Player, PlayerLog, PlayerRelation, NPC, Faction, Location,
)
from utils import (
    get_inventory, add_item_to_inventory, remove_item_from_inventory,
    get_item_count, get_equipped, save_equipped,
    add_experience, check_level_up, safe_log,
)
from economy_system import get_item, get_all_items
from faction_engine import get_player_rep_all, get_rep_status


# ==================== ПРОФИЛЬ ====================

def get_profile(player_id):
    """Полный профиль игрока для UI."""
    players = get_players_session()
    world = get_world_session()
    try:
        player = players.query(Player).filter_by(id=player_id).first()
        if not player:
            return None

        # Локация
        loc = world.query(Location).filter_by(id=player.current_location).first()
        loc_data = None
        if loc:
            loc_data = {
                'id': loc.id,
                'name': loc.name,
                'type': loc.type,
                'desc': loc.desc,
            }

        # Фракция
        faction_data = None
        if player.faction_id:
            faction = world.query(Faction).filter_by(id=player.faction_id).first()
            if faction:
                faction_data = {
                    'id': faction.id,
                    'name': faction.name,
                    'color': faction.color,
                }

        # Ранг
        rank_name = player.faction_rank
        if player.faction_id and player.faction_rank:
            from config import FACTION_RANKS
            rank_name = FACTION_RANKS.get(player.faction_id, {}).get(
                player.faction_rank, player.faction_rank
            )

        # Прогресс уровня
        next_level_exp = get_exp_for_level(player.level + 1) if player.level < MAX_LEVEL else None
        current_level_exp = get_exp_for_level(player.level)
        exp_to_next = (next_level_exp - player.experience) if next_level_exp else 0

        # Экипировка
        equipped = get_equipped(player)

        # Эффекты
        now = datetime.now()
        effects = []
        if player.energy_drink_until and player.energy_drink_until > now:
            remaining = player.energy_drink_until - now
            effects.append({
                'type': 'energy',
                'name': 'Энергетик',
                'remaining_sec': int(remaining.total_seconds()),
            })
        if player.cooldown_reducer_until and player.cooldown_reducer_until > now:
            remaining = player.cooldown_reducer_until - now
            effects.append({
                'type': 'reducer',
                'name': 'Редуктор',
                'remaining_sec': int(remaining.total_seconds()),
            })

        # Репутации
        reps = get_player_rep_all(player)
        rep_list = []
        for fid, value in reps.items():
            tier, tier_name = get_rep_status(value)
            faction = world.query(Faction).filter_by(id=fid).first()
            rep_list.append({
                'faction_id': fid,
                'faction_name': faction.name if faction else fid,
                'faction_color': faction.color if faction else '#aaaaaa',
                'value': value,
                'tier': tier,
                'tier_name': tier_name,
            })

        # Питомец
        pet = player.pet

        return {
            'id': player.id,
            'username': player.username,
            'level': player.level,
            'experience': player.experience,
            'current_level_exp': current_level_exp,
            'next_level_exp': next_level_exp,
            'exp_to_next': exp_to_next,

            'radcoins': player.radcoins,
            'radfragments': player.radfragments,
            'radcrystals': player.radcrystals,

            'user_class': player.user_class,
            'faction': faction_data,
            'faction_rank': player.faction_rank,
            'faction_rank_name': rank_name,

            'location': loc_data,
            'pet': pet,
            'equipped': equipped,
            'effects': effects,
            'reputations': rep_list,

            'stats': {
                'total_collects': player.total_collects or 0,
                'total_rc_earned': player.total_rc_earned or 0,
                'best_collect': player.best_collect or 0,
                'mutants_killed': player.mutants_killed or 0,
                'bosses_killed': player.bosses_killed or 0,
                'npcs_killed': player.npcs_killed or 0,
                'npcs_helped': player.npcs_helped or 0,
                'deaths': player.deaths or 0,
                'daily_streak': player.daily_streak or 0,
            },
        }
    finally:
        players.close()
        world.close()


def get_inventory_view(player_id):
    """Инвентарь игрока с названиями и ценами."""
    players = get_players_session()
    try:
        player = players.query(Player).filter_by(id=player_id).first()
        if not player:
            return []

        inv = get_inventory(player)
        items_catalog = get_all_items()
        result = []

        for entry in inv:
            item_id = entry.get('item')
            count = entry.get('count', 0)
            item = items_catalog.get(item_id)
            if item:
                result.append({
                    'id': item_id,
                    'name': item.get('name', item_id),
                    'category': item.get('category', 'misc'),
                    'count': count,
                    'price_sell': item.get('price_sell', int(item.get('price', 0) * 0.6)),
                    'desc': item.get('desc', ''),
                })
            else:
                result.append({
                    'id': item_id,
                    'name': item_id,
                    'category': 'misc',
                    'count': count,
                    'price_sell': 1,
                    'desc': '',
                })

        return result
    finally:
        players.close()


# ==================== ЭКИПИРОВКА ====================

def equip_item(player_id, item_id):
    """Экипировать предмет."""
    players = get_players_session()
    try:
        player = players.query(Player).filter_by(id=player_id).first()
        if not player:
            return {'ok': False, 'message': 'Игрок не найден'}

        item = get_item(item_id)
        if not item:
            return {'ok': False, 'message': 'Предмет не найден'}

        category = item.get('category')
        if category not in ('weapons', 'armor'):
            return {'ok': False, 'message': 'Это нельзя экипировать'}

        if get_item_count(player, item_id) <= 0:
            return {'ok': False, 'message': 'Нет в инвентаре'}

        slot = 'weapon' if category == 'weapons' else 'armor'
        equipped = get_equipped(player)

        # Снять старое
        old = equipped.get(slot)
        if old:
            add_item_to_inventory(player, old, 1)

        # Надеть новое
        remove_item_from_inventory(player, item_id, 1)
        equipped[slot] = item_id
        save_equipped(player, equipped)

        # Уровень
        req_level = item.get('level_required', 1)
        if player.level < req_level:
            return {'ok': False,
                    'message': f'Нужен {req_level} уровень'}

        players.commit()
        safe_log(player, 'equip', item=item_id)

        return {
            'ok': True,
            'message': f"Экипировано: {item.get('name', item_id)}",
        }
    except Exception as e:
        logger.error(f"Ошибка экипировки: {e}")
        players.rollback()
        return {'ok': False, 'message': str(e)}
    finally:
        players.close()


def unequip_item(player_id, slot):
    """Снять предмет."""
    players = get_players_session()
    try:
        player = players.query(Player).filter_by(id=player_id).first()
        if not player:
            return {'ok': False, 'message': 'Игрок не найден'}

        if slot not in ('weapon', 'armor'):
            return {'ok': False, 'message': 'Неверный слот'}

        equipped = get_equipped(player)
        old = equipped.get(slot)
        if not old:
            return {'ok': False, 'message': 'Нечего снимать'}

        add_item_to_inventory(player, old, 1)
        equipped[slot] = None
        save_equipped(player, equipped)

        players.commit()
        return {'ok': True, 'message': f'Снято: {old}'}
    finally:
        players.close()


# ==================== ИСПОЛЬЗОВАНИЕ ПРЕДМЕТОВ ====================

def use_item(player_id, item_id):
    """Использовать расходник."""
    players = get_players_session()
    try:
        player = players.query(Player).filter_by(id=player_id).first()
        if not player:
            return {'ok': False, 'message': 'Игрок не найден'}

        if get_item_count(player, item_id) <= 0:
            return {'ok': False, 'message': 'Нет в инвентаре'}

        item = get_item(item_id)
        if not item:
            return {'ok': False, 'message': 'Предмет не найден'}

        category = item.get('category')
        if category != 'consumables':
            return {'ok': False, 'message': 'Это нельзя использовать'}

        effect = item.get('effect', {})
        now = datetime.now()
        msg = f"Использовано: {item.get('name', item_id)}"

        # Аптечка
        if effect.get('type') == 'heal':
            pass  # Обрабатывается в бою
            msg = 'Аптечка сохранена для боя'

        # Энергетик
        elif effect.get('type') == 'energy':
            duration = effect.get('duration_hours', 6)
            if player.energy_drink_until and player.energy_drink_until > now:
                player.energy_drink_until += timedelta(hours=duration)
                player.energy_drink_stacks = (player.energy_drink_stacks or 0) + 1
            else:
                player.energy_drink_until = now + timedelta(hours=duration)
                player.energy_drink_stacks = 1
            player.energy_drink_level = item_id.replace('энергетик_', '')

        # Редуктор
        elif effect.get('type') == 'reducer':
            duration = effect.get('duration_days', 3)
            if player.cooldown_reducer_until and player.cooldown_reducer_until > now:
                player.cooldown_reducer_until += timedelta(days=duration)
                player.reducer_stacks = (player.reducer_stacks or 0) + 1
            else:
                player.cooldown_reducer_until = now + timedelta(days=duration)
                player.reducer_stacks = 1
            player.reducer_level = item_id.replace('редуктор_', '')

        remove_item_from_inventory(player, item_id, 1)
        safe_log(player, 'use_item', item=item_id)
        players.commit()

        return {'ok': True, 'message': msg}
    except Exception as e:
        logger.error(f"Ошибка использования: {e}")
        players.rollback()
        return {'ok': False, 'message': str(e)}
    finally:
        players.close()


# ==================== СМЕНА КЛАССА ====================

CLASS_CHANGE_COST = 5000


def change_class(player_id, new_class, free=False):
    """Сменить класс игрока."""
    players = get_players_session()
    try:
        player = players.query(Player).filter_by(id=player_id).first()
        if not player:
            return {'ok': False, 'message': 'Игрок не найден'}

        valid = ['stalker', 'military', 'bandit', 'scientist']
        if new_class not in valid:
            return {'ok': False, 'message': 'Неверный класс'}

        if player.user_class == new_class:
            return {'ok': False, 'message': 'Уже этот класс'}

        if not free:
            if player.radcoins < CLASS_CHANGE_COST:
                return {'ok': False,
                        'message': f'Нужно {CLASS_CHANGE_COST} RC'}
            player.radcoins -= CLASS_CHANGE_COST

        player.user_class = new_class
        player.last_free_class_change = datetime.now()

        safe_log(player, 'change_class', rc=0 if free else -CLASS_CHANGE_COST,
                 item=new_class)
        players.commit()

        return {'ok': True, 'message': f'Класс изменён на {new_class}'}
    finally:
        players.close()


# ==================== СОН И ОТДЫХ ====================

def rest(player_id, location_id=None):
    """Отдохнуть. Сбрасывает усталость, восстанавливает HP (если есть система HP)."""
    players = get_players_session()
    try:
        player = players.query(Player).filter_by(id=player_id).first()
        if not player:
            return {'ok': False, 'message': 'Игрок не найден'}

        # Сброс кулдауна сбора (частичный)
        player.next_collection_time = None
        player.last_collection = None

        players.commit()
        return {'ok': True, 'message': 'Вы отдохнули. Кулдаун сбора сброшен'}
    finally:
        players.close()


# ==================== ПЕРЕМЕЩЕНИЕ ИГРОКА ====================

def get_current_location(player_id):
    """Текущая локация игрока."""
    players = get_players_session()
    world = get_world_session()
    try:
        player = players.query(Player).filter_by(id=player_id).first()
        if not player:
            return None
        loc = world.query(Location).filter_by(id=player.current_location).first()
        return loc
    finally:
        players.close()
        world.close()


def get_player_faction(player_id):
    """Фракция игрока."""
    players = get_players_session()
    world = get_world_session()
    try:
        player = players.query(Player).filter_by(id=player_id).first()
        if not player or not player.faction_id:
            return None
        return world.query(Faction).filter_by(id=player.faction_id).first()
    finally:
        players.close()
        world.close()


# ==================== ПАМЯТЬ О NPC ====================

def get_npc_memory(player_id, limit=50):
    """Список NPC, которых игрок встречал."""
    from npc_engine import get_met_npcs
    return get_met_npcs(player_id, limit)


# ==================== ДОСТИЖЕНИЯ ====================

def get_achievements(player_id):
    """Список достижений игрока."""
    players = get_players_session()
    try:
        player = players.query(Player).filter_by(id=player_id).first()
        if not player:
            return []
        try:
            return json.loads(player.achievements or '[]')
        except Exception:
            return []
    finally:
        players.close()


def unlock_achievement(player_id, achievement_id):
    """Разблокировать достижение."""
    players = get_players_session()
    try:
        player = players.query(Player).filter_by(id=player_id).first()
        if not player:
            return False

        try:
            achievements = json.loads(player.achievements or '[]')
        except Exception:
            achievements = []

        if achievement_id in achievements:
            return False

        achievements.append(achievement_id)
        player.achievements = json.dumps(achievements)
        players.commit()

        safe_log(player, 'achievement', item=achievement_id)
        logger.info(f"🏆 Достижение: {achievement_id}")
        return True
    finally:
        players.close()


# ==================== ЭФФЕКТЫ ====================

def clear_effects(player_id):
    """Очистить все эффекты игрока."""
    players = get_players_session()
    try:
        player = players.query(Player).filter_by(id=player_id).first()
        if not player:
            return {'ok': False, 'message': 'Игрок не найден'}

        player.energy_drink_until = None
        player.energy_drink_stacks = 0
        player.cooldown_reducer_until = None
        player.reducer_stacks = 0

        players.commit()
        return {'ok': True, 'message': 'Все эффекты очищены'}
    finally:
        players.close()


# ==================== УДАЛЕНИЕ ИГРОКА ====================

def delete_player(player_id):
    """Удалить игрока (для тестов)."""
    players = get_players_session()
    try:
        player = players.query(Player).filter_by(id=player_id).first()
        if not player:
            return False

        # Удаляем связи
        players.query(PlayerRelation).filter_by(player_id=player_id).delete()
        players.query(PlayerLog).filter_by(player_id=player_id).delete()
        players.delete(player)
        players.commit()
        logger.info(f"🗑️ Игрок удалён: {player_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления игрока: {e}")
        players.rollback()
        return False
    finally:
        players.close()


# ==================== СТАТИСТИКА ПО ВСЕМУ ====================

def get_global_stats():
    """Общая статистика по игрокам."""
    players = get_players_session()
    try:
        total = players.query(Player).count()
        richest = players.query(Player).order_by(
            Player.radcoins.desc()
        ).first()
        highest_level = players.query(Player).order_by(
            Player.level.desc()
        ).first()

        return {
            'total_players': total,
            'richest': {
                'name': richest.username if richest else None,
                'radcoins': richest.radcoins if richest else 0,
            },
            'highest_level': {
                'name': highest_level.username if highest_level else None,
                'level': highest_level.level if highest_level else 0,
            },
        }
    finally:
        players.close()