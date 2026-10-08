# faction_engine.py - Rad Earth
# Версия: 1.0.0
# Фракции. Загрузка, репутация, дипломатия, войны, территории.

import os
import json
import random
from datetime import datetime

from config import (
    logger, JSON_FACTIONS, JSON_FACTIONS_MINOR,
    MAJOR_FACTIONS, FACTION_RANKS, FACTION_COLORS,
    REP_MIN, REP_MAX, REP_WAR_THRESHOLD, REP_ALLY_THRESHOLD,
    clamp,
)
from database import (
    get_world_session, get_players_session,
    Faction, FactionRelation, War, NPC, Location,
    Player, PlayerLog,
)


# ==================== ЗАГРУЗКА ФРАКЦИЙ ====================

def load_faction_json(faction_id):
    """Загрузить JSON фракции."""
    path = os.path.join(JSON_FACTIONS, f"{faction_id}.json")
    if not os.path.exists(path):
        logger.warning(f"JSON фракции не найден: {faction_id}")
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка чтения {faction_id}: {e}")
        return None


def create_faction_from_json(faction_id, world):
    """Создать запись Faction в БД из JSON."""
    data = load_faction_json(faction_id)
    if not data:
        return None

    existing = world.query(Faction).filter_by(id=faction_id).first()
    if existing:
        return existing

    faction = Faction(
        id=faction_id,
        name=data.get('name', faction_id),
        type=data.get('type', 'mixed'),
        desc=data.get('desc', ''),
        color=data.get('color', FACTION_COLORS.get(faction_id, '#aaaaaa')),
        treasury_coins=data.get('treasury_coins', 0),
        treasury_fragments=data.get('treasury_fragments', 0),
        treasury_crystals=data.get('treasury_crystals', 0),
        military_strength=data.get('military_strength', 100),
        discipline=data.get('discipline', 50),
        morale=data.get('morale', 50),
        is_at_war=json.dumps(data.get('at_war_with', [])),
        is_ally=json.dumps(data.get('allied_with', [])),
        is_neutral=json.dumps(data.get('neutral_with', [])),
        controlled_locations=json.dumps(data.get('controlled_locations', [])),
    )
    world.add(faction)
    world.commit()
    logger.info(f"✅ Создана фракция: {faction.name}")
    return faction


def load_all_factions():
    """Загрузить все крупные фракции из JSON."""
    world = get_world_session()
    try:
        for fid in MAJOR_FACTIONS:
            create_faction_from_json(fid, world)
        world.commit()
        logger.info(f"✅ Загружено {len(MAJOR_FACTIONS)} фракций")
    except Exception as e:
        logger.error(f"Ошибка загрузки фракций: {e}")
        world.rollback()
    finally:
        world.close()


def get_faction(faction_id):
    """Получить фракцию по ID."""
    world = get_world_session()
    try:
        return world.query(Faction).filter_by(id=faction_id).first()
    finally:
        world.close()


def get_all_factions():
    """Все фракции."""
    world = get_world_session()
    try:
        return world.query(Faction).all()
    finally:
        world.close()


# ==================== РЕПУТАЦИЯ ====================

def get_player_rep(player, faction_id):
    """Репутация игрока с фракцией."""
    if not player:
        return 0
    try:
        reps = json.loads(player.faction_rep or '{}')
        return reps.get(faction_id, 0)
    except Exception:
        return 0


def get_player_rep_all(player):
    """Все репутации игрока."""
    if not player:
        return {}
    try:
        return json.loads(player.faction_rep or '{}')
    except Exception:
        return {}


def change_player_rep(player, faction_id, delta):
    """Изменить репутацию игрока с фракцией + отголоски у друзей/врагов."""
    if not player or not faction_id:
        return 0

    reps = json.loads(player.faction_rep or '{}')
    current = reps.get(faction_id, 0)
    new_rep = clamp(current + delta, REP_MIN, REP_MAX)
    reps[faction_id] = new_rep

    # Отголоски у союзников и врагов
    world = get_world_session()
    try:
        faction = world.query(Faction).filter_by(id=faction_id).first()
        if faction:
            allies = json.loads(faction.is_ally or '[]')
            enemies = json.loads(faction.is_at_war or '[]')

            for ally_id in allies:
                ally_rep = reps.get(ally_id, 0)
                reps[ally_id] = clamp(ally_rep + int(delta * 0.5), REP_MIN, REP_MAX)

            for enemy_id in enemies:
                enemy_rep = reps.get(enemy_id, 0)
                reps[enemy_id] = clamp(enemy_rep - int(delta * 0.5), REP_MIN, REP_MAX)
    finally:
        world.close()

    player.faction_rep = json.dumps(reps)
    return new_rep


def get_rep_status(rep):
    """Категория репутации."""
    if rep <= REP_WAR_THRESHOLD:
        return 'war', 'Враг'
    if rep <= -20:
        return 'unfriendly', 'Недруг'
    if rep < 20:
        return 'neutral', 'Нейтрал'
    if rep < REP_ALLY_THRESHOLD:
        return 'friendly', 'Друг'
    return 'ally', 'Союзник'


# ==================== ДИПЛОМАТИЯ ====================

def get_relation(world, faction_a, faction_b):
    """Отношение между фракциями. Симметрично."""
    if faction_a == faction_b:
        return None
    a, b = sorted([faction_a, faction_b])
    rel = world.query(FactionRelation).filter_by(
        faction_a=a, faction_b=b
    ).first()
    if not rel:
        rel = FactionRelation(faction_a=a, faction_b=b, relation=0, status='neutral')
        world.add(rel)
        world.commit()
    return rel


def set_relation(world, faction_a, faction_b, relation, status):
    """Установить отношение между фракциями."""
    rel = get_relation(world, faction_a, faction_b)
    if not rel:
        return
    rel.relation = clamp(relation, REP_MIN, REP_MAX)
    rel.status = status
    rel.last_change = datetime.now()


def declare_war(world, faction_a, faction_b, reason=''):
    """Объявить войну."""
    if faction_a == faction_b:
        return
    set_relation(world, faction_a, faction_b, REP_MIN, 'war')

    war = War(
        faction_a=faction_a,
        faction_b=faction_b,
        started_at=datetime.now(),
        reason=reason,
        is_active=True,
    )
    world.add(war)

    # Обновляем фракции
    for fid in (faction_a, faction_b):
        faction = world.query(Faction).filter_by(id=fid).first()
        if faction:
            at_war = json.loads(faction.is_at_war or '[]')
            other = faction_b if fid == faction_a else faction_a
            if other not in at_war:
                at_war.append(other)
            faction.is_at_war = json.dumps(at_war)

            allies = json.loads(faction.is_ally or '[]')
            if other in allies:
                allies.remove(other)
            faction.is_ally = json.dumps(allies)

    world.commit()
    logger.info(f"⚔️ Война: {faction_a} vs {faction_b}")


def make_peace(world, faction_a, faction_b):
    """Заключить мир."""
    set_relation(world, faction_a, faction_b, 0, 'neutral')
    for fid in (faction_a, faction_b):
        faction = world.query(Faction).filter_by(id=fid).first()
        if faction:
            at_war = json.loads(faction.is_at_war or '[]')
            other = faction_b if fid == faction_a else faction_a
            if other in at_war:
                at_war.remove(other)
            faction.is_at_war = json.dumps(at_war)
    world.commit()


def make_alliance(world, faction_a, faction_b):
    """Союз."""
    set_relation(world, faction_a, faction_b, REP_ALLY_THRESHOLD, 'ally')
    for fid in (faction_a, faction_b):
        faction = world.query(Faction).filter_by(id=fid).first()
        if faction:
            allies = json.loads(faction.is_ally or '[]')
            other = faction_b if fid == faction_a else faction_a
            if other not in allies:
                allies.append(other)
            faction.is_ally = json.dumps(allies)
    world.commit()


def get_active_wars():
    """Активные войны."""
    world = get_world_session()
    try:
        return world.query(War).filter_by(is_active=True).all()
    finally:
        world.close()


def get_wars_for_faction(faction_id):
    """Войны конкретной фракции."""
    world = get_world_session()
    try:
        return world.query(War).filter(
            War.is_active == True,
            (War.faction_a == faction_id) | (War.faction_b == faction_id)
        ).all()
    finally:
        world.close()


# ==================== ЧИСЛЕННОСТЬ ====================

def recalculate_population(faction_id):
    """Пересчитать численность фракции по живым NPC."""
    world = get_world_session()
    try:
        faction = world.query(Faction).filter_by(id=faction_id).first()
        if not faction:
            return

        total = world.query(NPC).filter_by(faction_id=faction_id).count()
        alive = world.query(NPC).filter(
            NPC.faction_id == faction_id,
            NPC.is_alive == True
        ).count()

        faction.population_total = total
        faction.population_alive = alive
        faction.updated_at = datetime.now()
        world.commit()
    finally:
        world.close()


def recalculate_all_populations():
    """Пересчитать численность всех фракций."""
    for fid in MAJOR_FACTIONS:
        recalculate_population(fid)


# ==================== ТЕРРИТОРИИ ====================

def get_controlled_locations(faction_id):
    """Локации под контролем фракции."""
    world = get_world_session()
    try:
        faction = world.query(Faction).filter_by(id=faction_id).first()
        if not faction:
            return []
        loc_ids = json.loads(faction.controlled_locations or '[]')
        return world.query(Location).filter(Location.id.in_(loc_ids)).all()
    finally:
        world.close()


def assign_location_to_faction(location_id, faction_id):
    """Назначить локацию фракции."""
    world = get_world_session()
    try:
        loc = world.query(Location).filter_by(id=location_id).first()
        if not loc:
            return False

        # Убираем у старого контроллера
        old_controller = loc.controller_faction_id
        if old_controller:
            old_faction = world.query(Faction).filter_by(id=old_controller).first()
            if old_faction:
                locs = json.loads(old_faction.controlled_locations or '[]')
                if location_id in locs:
                    locs.remove(location_id)
                old_faction.controlled_locations = json.dumps(locs)

        # Назначаем новому
        loc.controller_faction_id = faction_id
        if faction_id:
            new_faction = world.query(Faction).filter_by(id=faction_id).first()
            if new_faction:
                locs = json.loads(new_faction.controlled_locations or '[]')
                if location_id not in locs:
                    locs.append(location_id)
                new_faction.controlled_locations = json.dumps(locs)

        world.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка назначения локации: {e}")
        world.rollback()
        return False
    finally:
        world.close()


# ==================== ПРИСОЕДИНЕНИЕ ИГРОКА ====================

def can_join_faction(player, faction_id):
    """Может ли игрок присоединиться."""
    if player.faction_id:
        return False, "Вы уже во фракции"
    rep = get_player_rep(player, faction_id)
    if rep < 0:
        return False, "Фракция вас не примет (репутация ниже 0)"
    return True, "OK"


def join_faction(player, faction_id, rank=None):
    """Присоединить игрока к фракции."""
    ok, msg = can_join_faction(player, faction_id)
    if not ok:
        return {'ok': False, 'message': msg}

    faction = get_faction(faction_id)
    if not faction:
        return {'ok': False, 'message': 'Фракция не найдена'}

    if rank is None:
        ranks = FACTION_RANKS.get(faction_id, {})
        rank = list(ranks.keys())[-1] if ranks else 'recruit'

    player.faction_id = faction_id
    player.faction_rank = rank

    change_player_rep(player, faction_id, 10)

    log = PlayerLog(player_id=player.id, action='join_faction', item=faction_id)
    players = get_players_session()
    try:
        players.add(log)
        players.commit()
    finally:
        players.close()

    return {'ok': True, 'message': f"Вы присоединились к {faction.name} как {rank}"}


def leave_faction(player):
    """Покинуть фракцию."""
    if not player.faction_id:
        return {'ok': False, 'message': 'Вы не во фракции'}

    old_faction = player.faction_id
    change_player_rep(player, old_faction, -20)
    player.faction_id = None
    player.faction_rank = None

    log = PlayerLog(player_id=player.id, action='leave_faction', item=old_faction)
    players = get_players_session()
    try:
        players.add(log)
        players.commit()
    finally:
        players.close()

    return {'ok': True, 'message': f"Вы покинули фракцию {old_faction}"}


def promote_player(player, new_rank):
    """Повысить игрока в ранге."""
    if not player.faction_id:
        return {'ok': False, 'message': 'Вы не во фракции'}

    valid_ranks = FACTION_RANKS.get(player.faction_id, {})
    if new_rank not in valid_ranks:
        return {'ok': False, 'message': 'Неверный ранг'}

    player.faction_rank = new_rank

    log = PlayerLog(player_id=player.id, action='promote',
                    item=f"{player.faction_id}:{new_rank}")
    players = get_players_session()
    try:
        players.add(log)
        players.commit()
    finally:
        players.close()

    return {'ok': True, 'message': f"Вы повышены до {valid_ranks[new_rank]}"}


# ==================== СТАТИСТИКА ====================

def get_faction_summary(faction_id):
    """Сводка по фракции для UI."""
    faction = get_faction(faction_id)
    if not faction:
        return None

    return {
        'id': faction.id,
        'name': faction.name,
        'type': faction.type,
        'color': faction.color,
        'desc': faction.desc,
        'population_total': faction.population_total,
        'population_alive': faction.population_alive,
        'military_strength': faction.military_strength,
        'discipline': faction.discipline,
        'morale': faction.morale,
        'treasury_coins': faction.treasury_coins,
        'at_war_with': json.loads(faction.is_at_war or '[]'),
        'allied_with': json.loads(faction.is_ally or '[]'),
        'controlled_locations': json.loads(faction.controlled_locations or '[]'),
    }


def get_leader(faction_id):
    """Лидер фракции."""
    world = get_world_session()
    try:
        faction = world.query(Faction).filter_by(id=faction_id).first()
        if not faction or not faction.leader_id:
            return None
        return world.query(NPC).filter_by(id=faction.leader_id).first()
    finally:
        world.close()


def get_advisor(faction_id):
    """Советник фракции."""
    world = get_world_session()
    try:
        faction = world.query(Faction).filter_by(id=faction_id).first()
        if not faction or not faction.advisor_id:
            return None
        return world.query(NPC).filter_by(id=faction.advisor_id).first()
    finally:
        world.close()