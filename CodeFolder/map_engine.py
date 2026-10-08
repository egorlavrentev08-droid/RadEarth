# map_engine.py - Rad Earth
# Версия: 1.0.0
# Карта. Загрузка локаций из JSON, связи, доступность, контроль фракций.

import os
import json
import random
from datetime import datetime

from config import (
    logger, JSON_LOCATIONS, LOCATIONS_LIST,
    TRAVEL_TIME_PER_HOP,
)
from database import (
    get_world_session, get_players_session,
    Location, Faction, NPC, Player,
)
from faction_engine import get_player_rep


# ==================== ЗАГРУЗКА ЛОКАЦИЙ ====================

def load_location_json(location_id):
    """Загрузить JSON локации."""
    path = os.path.join(JSON_LOCATIONS, f"{location_id}.json")
    if not os.path.exists(path):
        logger.warning(f"JSON локации не найден: {location_id}")
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка чтения {location_id}: {e}")
        return None


def create_location_from_json(location_id, world):
    """Создать Location в БД из JSON."""
    data = load_location_json(location_id)
    if not data:
        return None

    existing = world.query(Location).filter_by(id=location_id).first()
    if existing:
        return existing

    loc = Location(
        id=location_id,
        name=data.get('name', location_id),
        type=data.get('type', 'wild'),
        desc=data.get('desc', ''),
        controller_faction_id=data.get('controller_faction_id'),
        rc_mult=data.get('rc_mult', 1.0),
        rf_mult=data.get('rf_mult', 1.0),
        exp_mult=data.get('exp_mult', 1.0),
        pet_mult=data.get('pet_mult', 1.0),
        chest_mult=data.get('chest_mult', 1.0),
        danger_bonus=data.get('danger_bonus', 0),
        encounter_chance=data.get('encounter_chance', 0.1),
        has_trader=data.get('has_trader', False),
        has_business=data.get('has_business', False),
        has_shops=data.get('has_shops', False),
        has_medbay=data.get('has_medbay', False),
        has_barracks=data.get('has_barracks', False),
        connections=json.dumps(data.get('connections', [])),
    )
    world.add(loc)
    world.commit()
    logger.info(f"✅ Создана локация: {loc.name}")
    return loc


def load_all_locations():
    """Загрузить все локации из JSON."""
    world = get_world_session()
    try:
        for loc_id in LOCATIONS_LIST:
            create_location_from_json(loc_id, world)
        world.commit()
        logger.info(f"✅ Загружено {len(LOCATIONS_LIST)} локаций")
    except Exception as e:
        logger.error(f"Ошибка загрузки локаций: {e}")
        world.rollback()
    finally:
        world.close()


# ==================== ПОЛУЧЕНИЕ ====================

def get_location(location_id):
    """Получить локацию по ID."""
    world = get_world_session()
    try:
        return world.query(Location).filter_by(id=location_id).first()
    finally:
        world.close()


def get_all_locations():
    """Все локации."""
    world = get_world_session()
    try:
        return world.query(Location).all()
    finally:
        world.close()


def get_location_view(location_id, player_id=None):
    """Полная информация о локации с точки зрения игрока."""
    world = get_world_session()
    players = get_players_session()
    try:
        loc = world.query(Location).filter_by(id=location_id).first()
        if not loc:
            return None

        player = None
        if player_id:
            player = players.query(Player).filter_by(id=player_id).first()

        # Владелец территории
        controller = None
        controller_color = None
        if loc.controller_faction_id:
            faction = world.query(Faction).filter_by(
                id=loc.controller_faction_id
            ).first()
            if faction:
                controller = {
                    'id': faction.id,
                    'name': faction.name,
                    'color': faction.color,
                }
                controller_color = faction.color

        # Доступность
        can_enter = True
        enter_reason = ''
        if player and loc.controller_faction_id:
            rep = get_player_rep(player, loc.controller_faction_id)
            if rep <= -50:
                can_enter = False
                enter_reason = 'Фракция-контроллер враждебна'

        return {
            'id': loc.id,
            'name': loc.name,
            'type': loc.type,
            'desc': loc.desc,
            'controller': controller,
            'controller_color': controller_color,
            'connections': json.loads(loc.connections or '[]'),
            'has_trader': loc.has_trader,
            'has_business': loc.has_business,
            'has_shops': loc.has_shops,
            'has_medbay': loc.has_medbay,
            'has_barracks': loc.has_barracks,
            'danger_bonus': loc.danger_bonus,
            'rc_mult': loc.rc_mult,
            'rf_mult': loc.rf_mult,
            'exp_mult': loc.exp_mult,
            'pet_mult': loc.pet_mult,
            'chest_mult': loc.chest_mult,
            'can_enter': can_enter,
            'enter_reason': enter_reason,
        }
    finally:
        world.close()
        players.close()


def get_connected_locations(location_id, player_id=None):
    """Список локаций, куда можно перейти."""
    world = get_world_session()
    players = get_players_session()
    try:
        loc = world.query(Location).filter_by(id=location_id).first()
        if not loc:
            return []

        connections = json.loads(loc.connections or '[]')
        player = None
        if player_id:
            player = players.query(Player).filter_by(id=player_id).first()

        result = []
        for conn_id in connections:
            other = world.query(Location).filter_by(id=conn_id).first()
            if not other:
                continue

            controller_name = None
            controller_color = None
            if other.controller_faction_id:
                faction = world.query(Faction).filter_by(
                    id=other.controller_faction_id
                ).first()
                if faction:
                    controller_name = faction.name
                    controller_color = faction.color

            can_enter = True
            reason = ''
            if player and other.controller_faction_id:
                rep = get_player_rep(player, other.controller_faction_id)
                if rep <= -50:
                    can_enter = False
                    reason = f'{controller_name} не пустит'

            result.append({
                'id': other.id,
                'name': other.name,
                'type': other.type,
                'desc': other.desc,
                'controller': controller_name,
                'controller_color': controller_color,
                'can_enter': can_enter,
                'reason': reason,
                'travel_time': TRAVEL_TIME_PER_HOP,
            })
        return result
    finally:
        world.close()
        players.close()


# ==================== ПЕРЕМЕЩЕНИЕ ====================

def travel_player(player_id, to_location_id):
    """Переместить игрока в другую локацию."""
    players = get_players_session()
    world = get_world_session()
    try:
        player = players.query(Player).filter_by(id=player_id).first()
        if not player:
            return {'ok': False, 'message': 'Игрок не найден'}

        from_loc = world.query(Location).filter_by(
            id=player.current_location
        ).first()
        if not from_loc:
            return {'ok': False, 'message': 'Текущая локация не найдена'}

        to_loc = world.query(Location).filter_by(id=to_location_id).first()
        if not to_loc:
            return {'ok': False, 'message': 'Локация не найдена'}

        connections = json.loads(from_loc.connections or '[]')
        if to_location_id not in connections:
            return {'ok': False, 'message': 'Нет пути в эту локацию'}

        # Враждебная территория
        if to_loc.controller_faction_id:
            rep = get_player_rep(player, to_loc.controller_faction_id)
            if rep <= -50:
                controller = world.query(Faction).filter_by(
                    id=to_loc.controller_faction_id
                ).first()
                name = controller.name if controller else to_loc.controller_faction_id
                return {'ok': False,
                        'message': f'{name} не пустит вас (репутация {rep})'}

        player.current_location = to_location_id
        player.last_travel = datetime.now()

        # История
        history = json.loads(player.location_history or '[]')
        history.append(to_location_id)
        player.location_history = json.dumps(history[-20:])

        players.commit()

        return {
            'ok': True,
            'message': f'Вы прибыли в {to_loc.name}',
            'location': get_location_view(to_location_id, player_id),
        }
    except Exception as e:
        logger.error(f"Ошибка перемещения: {e}")
        players.rollback()
        return {'ok': False, 'message': str(e)}
    finally:
        players.close()
        world.close()


# ==================== NPC В ЛОКАЦИИ ====================

def get_npcs_in_location(location_id, alive_only=True, limit=None):
    """Список NPC в локации."""
    world = get_world_session()
    try:
        q = world.query(NPC).filter_by(location_id=location_id)
        if alive_only:
            q = q.filter_by(is_alive=True)
        if limit:
            q = q.limit(limit)
        return q.all()
    finally:
        world.close()


def get_named_npcs_in_location(location_id):
    """Ключевые NPC в локации."""
    world = get_world_session()
    try:
        return world.query(NPC).filter_by(
            location_id=location_id, is_alive=True, is_named=True
        ).all()
    finally:
        world.close()


def get_traders_in_location(location_id):
    """Торговцы в локации."""
    world = get_world_session()
    try:
        return world.query(NPC).filter_by(
            location_id=location_id, is_alive=True, is_trader=True
        ).all()
    finally:
        world.close()


# ==================== КОНТРОЛЬ ====================

def set_controller(location_id, faction_id):
    """Назначить контроллера локации."""
    world = get_world_session()
    try:
        loc = world.query(Location).filter_by(id=location_id).first()
        if not loc:
            return False

        old_faction_id = loc.controller_faction_id

        # Убрать из старого владельца
        if old_faction_id:
            old_faction = world.query(Faction).filter_by(id=old_faction_id).first()
            if old_faction:
                locs = json.loads(old_faction.controlled_locations or '[]')
                if location_id in locs:
                    locs.remove(location_id)
                old_faction.controlled_locations = json.dumps(locs)

        # Добавить новому
        loc.controller_faction_id = faction_id
        if faction_id:
            new_faction = world.query(Faction).filter_by(id=faction_id).first()
            if new_faction:
                locs = json.loads(new_faction.controlled_locations or '[]')
                if location_id not in locs:
                    locs.append(location_id)
                new_faction.controlled_locations = json.dumps(locs)

        world.commit()
        logger.info(f"🗺️ Локация {location_id} теперь под {faction_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка смены контроллера: {e}")
        world.rollback()
        return False
    finally:
        world.close()


def get_locations_by_controller(faction_id):
    """Локации под контролем фракции."""
    world = get_world_session()
    try:
        return world.query(Location).filter_by(
            controller_faction_id=faction_id
        ).all()
    finally:
        world.close()


# ==================== СОСЕДИ И ПУТИ ====================

def get_neighbors(location_id, depth=1):
    """Соседние локации на N шагов."""
    world = get_world_session()
    try:
        visited = set()
        current = {location_id}
        for _ in range(depth):
            next_layer = set()
            for loc_id in current:
                if loc_id in visited:
                    continue
                visited.add(loc_id)
                loc = world.query(Location).filter_by(id=loc_id).first()
                if loc:
                    for conn in json.loads(loc.connections or '[]'):
                        if conn not in visited:
                            next_layer.add(conn)
            current = next_layer
        visited.discard(location_id)
        return list(visited)
    finally:
        world.close()


def find_path(from_id, to_id):
    """Найти кратчайший путь между локациями (BFS)."""
    world = get_world_session()
    try:
        from collections import deque
        queue = deque([(from_id, [from_id])])
        visited = {from_id}

        while queue:
            current, path = queue.popleft()
            if current == to_id:
                return path

            loc = world.query(Location).filter_by(id=current).first()
            if not loc:
                continue

            for conn in json.loads(loc.connections or '[]'):
                if conn not in visited:
                    visited.add(conn)
                    queue.append((conn, path + [conn]))

        return None
    finally:
        world.close()


# ==================== СТАТИСТИКА ====================

def count_npcs_by_location(location_id):
    """Сколько живых NPC в локации."""
    world = get_world_session()
    try:
        return world.query(NPC).filter_by(
            location_id=location_id, is_alive=True
        ).count()
    finally:
        world.close()


def get_map_summary():
    """Сводка по карте."""
    world = get_world_session()
    try:
        locations = world.query(Location).all()
        result = []
        for loc in locations:
            npc_count = world.query(NPC).filter_by(
                location_id=loc.id, is_alive=True
            ).count()

            controller = None
            if loc.controller_faction_id:
                faction = world.query(Faction).filter_by(
                    id=loc.controller_faction_id
                ).first()
                if faction:
                    controller = {'id': faction.id, 'name': faction.name,
                                  'color': faction.color}

            result.append({
                'id': loc.id,
                'name': loc.name,
                'type': loc.type,
                'controller': controller,
                'connections': json.loads(loc.connections or '[]'),
                'npc_count': npc_count,
                'danger_bonus': loc.danger_bonus,
                'has_trader': loc.has_trader,
                'has_business': loc.has_business,
                'has_shops': loc.has_shops,
            })
        return result
    finally:
        world.close()