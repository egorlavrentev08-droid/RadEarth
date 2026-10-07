# npc_engine.py - Rad Earth
# Версия: 1.0.0
# NPC. Генерация, загрузка из JSON, продвижение, смерть, лояльность.

import os
import json
import random
from datetime import datetime, timedelta

from config import (
    logger, JSON_NPCS, JSON_NPCS_NAMED, JSON_NPCS_TEMPLATES,
    NPC_NAMES_MALE, NPC_NAMES_FEMALE, NPC_CALLSIGNS,
    FACTION_RANKS, MAJOR_FACTIONS, FACTION_START_STRENGTH,
    NPC_AVG_LIFESPAN_DAYS, clamp,
)
from database import (
    get_world_session, get_players_session,
    NPC, Faction, Location, Player, PlayerRelation,
)


# ==================== ЗАГРУЗКА ИМЕНОВАННЫХ NPC ====================

def load_named_npc_json(npc_id):
    """Загрузить JSON ключевого NPC."""
    path = os.path.join(JSON_NPCS_NAMED, f"{npc_id}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка чтения NPC {npc_id}: {e}")
        return None


def create_named_npc_from_json(npc_id, world):
    """Создать ключевого NPC из JSON."""
    data = load_named_npc_json(npc_id)
    if not data:
        return None

    existing = world.query(NPC).filter_by(id=npc_id).first()
    if existing:
        return existing

    npc = NPC(
        id=npc_id,
        name=data.get('name', 'Неизвестный'),
        callsign=data.get('callsign'),
        gender=data.get('gender', 'male'),
        faction_id=data.get('faction_id'),
        rank=data.get('rank'),
        role=data.get('role'),
        is_named=True,
        is_alive=True,
        loyalty=data.get('loyalty', 50),
        aggression=data.get('aggression', 50),
        intelligence=data.get('intelligence', 50),
        combat_skill=data.get('combat_skill', 50),
        hp_current=data.get('hp_max', 100),
        hp_max=data.get('hp_max', 100),
        is_trader=data.get('is_trader', False),
        trader_type=data.get('trader_type'),
        location_id=data.get('location_id'),
        dialog_file=data.get('dialog_file', npc_id),
    )
    world.add(npc)
    world.commit()
    logger.info(f"✅ Создан ключевой NPC: {npc.name} ({npc.id})")
    return npc


# ==================== ГЕНЕРАЦИЯ РЯДОВЫХ ====================

def generate_callsign(used_callsigns):
    """Сгенерировать уникальный позывной."""
    available = [c for c in NPC_CALLSIGNS if c not in used_callsigns]
    if not available:
        base = random.choice(NPC_CALLSIGNS)
        return f"{base}-{random.randint(2, 99)}"
    return random.choice(available)


def generate_npc_name(gender='male'):
    """Имя NPC."""
    if gender == 'female':
        return random.choice(NPC_NAMES_FEMALE)
    return random.choice(NPC_NAMES_MALE)


def _rank_distribution(faction_id, total):
    """Распределение NPC по рангам (от низа к верху)."""
    ranks = FACTION_RANKS.get(faction_id, {})
    rank_keys = list(ranks.keys())

    # Пирамида: много низких, мало высоких
    n = len(rank_keys)
    distribution = {}
    remaining = total

    for i, rank_key in enumerate(rank_keys):
        # Верхний ранг — мало, нижний — много
        weight = 2 ** i  # 1, 2, 4, 8, 16
        distribution[rank_key] = weight
        remaining -= 0  # placeholder

    total_weight = sum(distribution.values())
    result = {}
    for rank_key in rank_keys:
        result[rank_key] = max(1, int(total * distribution[rank_key] / total_weight))

    # Скорректировать чтобы в сумме было total
    diff = total - sum(result.values())
    if diff != 0:
        result[rank_keys[0]] = max(1, result[rank_keys[0]] + diff)

    return result


def generate_faction_npcs(faction_id, world, start_strength=None):
    """Сгенерировать рядовых NPC для фракции."""
    if start_strength is None:
        start_strength = FACTION_START_STRENGTH.get(faction_id, 100)

    # Уже сгенерировано?
    existing = world.query(NPC).filter_by(faction_id=faction_id).count()
    if existing >= start_strength:
        logger.info(f"NPC {faction_id}: уже сгенерированы ({existing})")
        return

    # Основная локация фракции (там где лидер)
    faction = world.query(Faction).filter_by(id=faction_id).first()
    if not faction:
        logger.warning(f"Фракция {faction_id} не найдена")
        return

    main_location_id = None
    if faction.leader_id:
        leader = world.query(NPC).filter_by(id=faction.leader_id).first()
        if leader:
            main_location_id = leader.location_id

    if not main_location_id:
        # Ищем первую контролируемую локацию
        controlled = json.loads(faction.controlled_locations or '[]')
        if controlled:
            main_location_id = controlled[0]

    if not main_location_id:
        logger.warning(f"Не удалось определить главную локацию для {faction_id}")
        return

    # Свободные позывные
    used = set()
    existing_npcs = world.query(NPC).filter_by(faction_id=faction_id).all()
    for n in existing_npcs:
        if n.callsign:
            used.add(n.callsign)

    # Распределение по рангам
    rank_keys = list(FACTION_RANKS.get(faction_id, {}).keys())
    if not rank_keys:
        return

    # Верхний ранг (лидер) уже есть — генерируем со второго
    ranks_to_fill = rank_keys[1:]  # кроме первого

    # Сколько генерировать
    to_generate = start_strength - existing
    logger.info(f"Генерация {to_generate} NPC для {faction_id}")

    # Распределение: пирамида (много низших, мало высших)
    weights = []
    for i in range(len(ranks_to_fill)):
        weights.append(max(1, len(ranks_to_fill) - i))  # больше низших

    total_w = sum(weights)
    counts = {}
    remaining = to_generate
    for i, rank in enumerate(ranks_to_fill):
        if i == len(ranks_to_fill) - 1:
            counts[rank] = remaining
        else:
            c = int(to_generate * weights[i] / total_w)
            counts[rank] = c
            remaining -= c

    npc_counter = existing
    generated = 0
    for rank_key, count in counts.items():
        for _ in range(count):
            npc_counter += 1
            gender = random.choice(['male', 'female', 'male', 'male'])
            name = generate_npc_name(gender)
            callsign = generate_callsign(used)
            used.add(callsign)

            # Локация: в основном главная, иногда — другие контролируемые
            loc_choice = main_location_id
            controlled = json.loads(faction.controlled_locations or '[]')
            if controlled and random.random() < 0.3:
                loc_choice = random.choice(controlled)

            # Характеристики от ранга
            rank_index = ranks_to_fill.index(rank_key) if rank_key in ranks_to_fill else 0
            tier_factor = 1.0 + (len(ranks_to_fill) - rank_index) * 0.15

            npc = NPC(
                id=f"{faction_id}_{npc_counter:04d}",
                name=name,
                callsign=callsign,
                gender=gender,
                faction_id=faction_id,
                rank=rank_key,
                role='soldier',
                is_named=False,
                is_alive=True,
                loyalty=random.randint(30, 90),
                aggression=random.randint(20, 90),
                intelligence=random.randint(20, 90),
                combat_skill=min(100, int(random.randint(30, 70) * tier_factor)),
                hp_current=100,
                hp_max=100,
                location_id=loc_choice,
            )
            world.add(npc)
            generated += 1

    world.commit()
    logger.info(f"✅ Сгенерировано {generated} NPC для {faction_id}")


def generate_all_faction_npcs():
    """Сгенерировать NPC для всех фракций."""
    world = get_world_session()
    try:
        for fid in MAJOR_FACTIONS:
            generate_faction_npcs(fid, world)
        world.commit()
    except Exception as e:
        logger.error(f"Ошибка генерации NPC: {e}")
        world.rollback()
    finally:
        world.close()


# ==================== СОЗДАНИЕ ЛИДЕРОВ ====================

def create_faction_leaders():
    """Создать/назначить лидеров фракций."""
    world = get_world_session()
    try:
        for fid in MAJOR_FACTIONS:
            faction = world.query(Faction).filter_by(id=fid).first()
            if not faction:
                continue

            # Уже есть лидер?
            if faction.leader_id:
                leader = world.query(NPC).filter_by(id=faction.leader_id).first()
                if leader:
                    continue

            # Ищем NPC с верхним рангом
            top_rank = list(FACTION_RANKS.get(fid, {}).keys())[0]
            leader = world.query(NPC).filter_by(
                faction_id=fid, rank=top_rank, is_alive=True
            ).first()

            if leader:
                faction.leader_id = leader.id
                leader.role = 'leader'
                leader.is_named = True

                # Советник — второй по рангу
                second_rank = list(FACTION_RANKS.get(fid, {}).keys())[1]
                advisor = world.query(NPC).filter_by(
                    faction_id=fid, rank=second_rank, is_alive=True
                ).first()
                if advisor:
                    faction.advisor_id = advisor.id
                    advisor.role = 'advisor'
                    advisor.is_named = True

        world.commit()
        logger.info("✅ Лидеры фракций назначены")
    except Exception as e:
        logger.error(f"Ошибка назначения лидеров: {e}")
        world.rollback()
    finally:
        world.close()


# ==================== ПОЛУЧЕНИЕ ====================

def get_npc(npc_id):
    """Получить NPC по ID."""
    world = get_world_session()
    try:
        return world.query(NPC).filter_by(id=npc_id).first()
    finally:
        world.close()


def get_npc_view(npc_id, player_id=None):
    """Информация о NPC для UI."""
    world = get_world_session()
    players = get_players_session()
    try:
        npc = world.query(NPC).filter_by(id=npc_id).first()
        if not npc:
            return None

        faction_name = None
        faction_color = None
        if npc.faction_id:
            faction = world.query(Faction).filter_by(id=npc.faction_id).first()
            if faction:
                faction_name = faction.name
                faction_color = faction.color

        player_attitude = npc.player_relationship
        if player_id:
            rel = players.query(PlayerRelation).filter_by(
                player_id=player_id, npc_id=npc_id
            ).first()
            if rel:
                player_attitude = rel.attitude

        return {
            'id': npc.id,
            'name': npc.name,
            'callsign': npc.callsign,
            'gender': npc.gender,
            'faction_id': npc.faction_id,
            'faction_name': faction_name,
            'faction_color': faction_color,
            'rank': npc.rank,
            'role': npc.role,
            'is_named': npc.is_named,
            'is_alive': npc.is_alive,
            'loyalty': npc.loyalty,
            'aggression': npc.aggression,
            'intelligence': npc.intelligence,
            'combat_skill': npc.combat_skill,
            'hp_current': npc.hp_current,
            'hp_max': npc.hp_max,
            'is_trader': npc.is_trader,
            'trader_type': npc.trader_type,
            'location_id': npc.location_id,
            'player_attitude': player_attitude,
        }
    finally:
        world.close()
        players.close()


def get_npcs_by_faction(faction_id, alive_only=True, limit=None):
    """NPC фракции."""
    world = get_world_session()
    try:
        q = world.query(NPC).filter_by(faction_id=faction_id)
        if alive_only:
            q = q.filter_by(is_alive=True)
        if limit:
            q = q.limit(limit)
        return q.all()
    finally:
        world.close()


def get_named_npcs(faction_id=None):
    """Ключевые NPC."""
    world = get_world_session()
    try:
        q = world.query(NPC).filter_by(is_named=True, is_alive=True)
        if faction_id:
            q = q.filter_by(faction_id=faction_id)
        return q.all()
    finally:
        world.close()


# ==================== СМЕРТЬ И РАНЕНИЕ ====================

def kill_npc(npc_id, reason=''):
    """Убить NPC."""
    world = get_world_session()
    try:
        npc = world.query(NPC).filter_by(id=npc_id).first()
        if not npc or not npc.is_alive:
            return False

        npc.is_alive = False
        npc.death_date = datetime.now()
        npc.death_reason = reason or 'Неизвестно'

        # Если это лидер — ищем замену
        if npc.role == 'leader' and npc.faction_id:
            faction = world.query(Faction).filter_by(id=npc.faction_id).first()
            if faction:
                _promote_new_leader(faction, world)

        # Если советник
        if npc.role == 'advisor' and npc.faction_id:
            faction = world.query(Faction).filter_by(id=npc.faction_id).first()
            if faction and faction.advisor_id == npc.id:
                faction.advisor_id = None

        world.commit()
        logger.info(f"☠️ NPC убит: {npc.name} ({reason})")
        return True
    except Exception as e:
        logger.error(f"Ошибка убийства NPC: {e}")
        world.rollback()
        return False
    finally:
        world.close()


def _promote_new_leader(faction, world):
    """Повысить нового лидера фракции."""
    top_rank = list(FACTION_RANKS.get(faction.id, {}).keys())[0]

    # Ищем живого NPC с высшим рангом
    candidates = world.query(NPC).filter(
        NPC.faction_id == faction.id,
        NPC.is_alive == True,
        NPC.id != faction.leader_id,
    ).order_by(NPC.loyalty.desc(), NPC.combat_skill.desc()).limit(5).all()

    if not candidates:
        logger.warning(f"⚠️ Нет кандидатов на лидера {faction.id}")
        return

    new_leader = candidates[0]
    new_leader.role = 'leader'
    new_leader.rank = top_rank
    new_leader.is_named = True
    faction.leader_id = new_leader.id

    logger.info(f"👑 Новый лидер {faction.id}: {new_leader.name}")


def wound_npc(npc_id, damage):
    """Ранить NPC."""
    world = get_world_session()
    try:
        npc = world.query(NPC).filter_by(id=npc_id).first()
        if not npc or not npc.is_alive:
            return False

        npc.hp_current = max(0, npc.hp_current - damage)
        if npc.hp_current <= 0:
            world.commit()
            return kill_npc(npc_id, 'Умер от ран')

        world.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка ранения NPC: {e}")
        world.rollback()
        return False
    finally:
        world.close()


def heal_npc(npc_id, amount):
    """Вылечить NPC."""
    world = get_world_session()
    try:
        npc = world.query(NPC).filter_by(id=npc_id).first()
        if not npc or not npc.is_alive:
            return False
        npc.hp_current = min(npc.hp_max, npc.hp_current + amount)
        world.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка лечения NPC: {e}")
        world.rollback()
        return False
    finally:
        world.close()


# ==================== ПРОДВИЖЕНИЕ ====================

def promote_npc(npc_id):
    """Повысить NPC в ранге."""
    world = get_world_session()
    try:
        npc = world.query(NPC).filter_by(id=npc_id).first()
        if not npc or not npc.is_alive or not npc.faction_id:
            return False

        ranks = list(FACTION_RANKS.get(npc.faction_id, {}).keys())
        if npc.rank not in ranks:
            return False

        idx = ranks.index(npc.rank)
        if idx <= 0:
            return False  # уже на верху

        npc.rank = ranks[idx - 1]
        npc.loyalty = min(100, npc.loyalty + 10)
        world.commit()
        logger.info(f"⬆️ {npc.name} повышен до {npc.rank}")
        return True
    except Exception as e:
        logger.error(f"Ошибка повышения NPC: {e}")
        world.rollback()
        return False
    finally:
        world.close()


def demote_npc(npc_id):
    """Понизить NPC."""
    world = get_world_session()
    try:
        npc = world.query(NPC).filter_by(id=npc_id).first()
        if not npc or not npc.is_alive or not npc.faction_id:
            return False

        ranks = list(FACTION_RANKS.get(npc.faction_id, {}).keys())
        if npc.rank not in ranks:
            return False

        idx = ranks.index(npc.rank)
        if idx >= len(ranks) - 1:
            return False

        npc.rank = ranks[idx + 1]
        npc.loyalty = max(0, npc.loyalty - 15)
        world.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка понижения NPC: {e}")
        world.rollback()
        return False
    finally:
        world.close()


# ==================== ОТНОШЕНИЯ С ИГРОКОМ ====================

def get_player_attitude(player_id, npc_id):
    """Отношение NPC к игроку."""
    players = get_players_session()
    try:
        rel = players.query(PlayerRelation).filter_by(
            player_id=player_id, npc_id=npc_id
        ).first()
        if rel:
            return rel.attitude
        world = get_world_session()
        try:
            npc = world.query(NPC).filter_by(id=npc_id).first()
            return npc.player_relationship if npc else 0
        finally:
            world.close()
    finally:
        players.close()


def change_player_attitude(player_id, npc_id, delta):
    """Изменить отношение NPC к игроку."""
    players = get_players_session()
    try:
        rel = players.query(PlayerRelation).filter_by(
            player_id=player_id, npc_id=npc_id
        ).first()
        if not rel:
            rel = PlayerRelation(player_id=player_id, npc_id=npc_id, attitude=0)
            players.add(rel)
        rel.attitude = clamp(rel.attitude + delta, -100, 100)
        rel.met_at = datetime.now()
        players.commit()
        return rel.attitude
    except Exception as e:
        logger.error(f"Ошибка изменения отношения: {e}")
        players.rollback()
        return 0
    finally:
        players.close()


# ==================== ПАМЯТЬ ИГРОКА ====================

def get_met_npcs(player_id, limit=50):
    """NPC, которых игрок встречал."""
    players = get_players_session()
    try:
        rels = players.query(PlayerRelation).filter_by(
            player_id=player_id
        ).order_by(PlayerRelation.met_at.desc()).limit(limit).all()

        result = []
        world = get_world_session()
        try:
            for rel in rels:
                npc = world.query(NPC).filter_by(id=rel.npc_id).first()
                if not npc:
                    continue
                faction_name = None
                if npc.faction_id:
                    faction = world.query(Faction).filter_by(
                        id=npc.faction_id
                    ).first()
                    if faction:
                        faction_name = faction.name

                result.append({
                    'npc_id': npc.id,
                    'npc_name': npc.name,
                    'callsign': npc.callsign,
                    'faction_name': faction_name,
                    'is_alive': npc.is_alive,
                    'attitude': rel.attitude,
                    'met_at': rel.met_at,
                })
        finally:
            world.close()

        return result
    finally:
        players.close()


# ==================== СТАТИСТИКА ====================

def get_faction_npc_summary(faction_id):
    """Сводка NPC фракции."""
    world = get_world_session()
    try:
        faction = world.query(Faction).filter_by(id=faction_id).first()
        if not faction:
            return None

        total = world.query(NPC).filter_by(faction_id=faction_id).count()
        alive = world.query(NPC).filter_by(
            faction_id=faction_id, is_alive=True
        ).count()

        # По рангам
        ranks = {}
        for rank_key in FACTION_RANKS.get(faction_id, {}).keys():
            ranks[rank_key] = world.query(NPC).filter_by(
                faction_id=faction_id, rank=rank_key, is_alive=True
            ).count()

        return {
            'faction_id': faction_id,
            'faction_name': faction.name,
            'total': total,
            'alive': alive,
            'dead': total - alive,
            'by_rank': ranks,
            'leader': faction.leader_id,
            'advisor': faction.advisor_id,
        }
    finally:
        world.close()


def count_all_npcs():
    """Сколько NPC в мире."""
    world = get_world_session()
    try:
        total = world.query(NPC).count()
        alive = world.query(NPC).filter_by(is_alive=True).count()
        return {'total': total, 'alive': alive, 'dead': total - alive}
    finally:
        world.close()