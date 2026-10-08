# dialog_system.py - Rad Earth
# Версия: 1.0.0
# Система диалогов. Загружает реплики из JsonFolder/npcs/named/*.json,
# управляет выбором игрока, считает эффекты (репутация, предметы, деньги).

import os
import json
import random
from datetime import datetime

from config import (
    logger, JSON_NPCS_NAMED, JSON_NPCS_TEMPLATES,
    REP_MIN, REP_MAX, clamp,
)
from database import (
    get_world_session, get_players_session,
    NPC, Faction, Player, PlayerLog, PlayerRelation,
)


# ==================== ЗАГРУЗКА ДИАЛОГОВ ====================

_DIALOG_CACHE = {}


def load_dialog(npc_id):
    """Загрузить диалоговый файл для NPC."""
    if npc_id in _DIALOG_CACHE:
        return _DIALOG_CACHE[npc_id]

    path = os.path.join(JSON_NPCS_NAMED, f"{npc_id}.json")
    if not os.path.exists(path):
        logger.warning(f"Диалог не найден: {npc_id}")
        return None

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        _DIALOG_CACHE[npc_id] = data
        return data
    except Exception as e:
        logger.error(f"Ошибка загрузки диалога {npc_id}: {e}")
        return None


def get_generic_dialog(faction_id, role='soldier'):
    """Загрузить generic-диалог для рядового NPC."""
    path = os.path.join(JSON_NPCS_TEMPLATES, f"{faction_id}_{role}.json")
    if not os.path.exists(path):
        path = os.path.join(JSON_NPCS_TEMPLATES, "generic_soldier.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки шаблона диалога: {e}")
        return None


# ==================== СТАРТ ДИАЛОГА ====================

def start_dialog(player_id, npc_id):
    """Начать диалог с NPC. Возвращает структуру диалога или None."""
    world = get_world_session()
    players = get_players_session()
    try:
        npc = world.query(NPC).filter_by(id=npc_id).first()
        if not npc:
            logger.warning(f"NPC не найден: {npc_id}")
            return None
        if not npc.is_alive:
            return {'error': 'NPC мёртв'}

        player = players.query(Player).filter_by(id=player_id).first()
        if not player:
            return {'error': 'Игрок не найден'}

        # Репутация с фракцией NPC
        rep_map = json.loads(player.faction_rep or '{}')
        faction_rep = rep_map.get(npc.faction_id, 0) if npc.faction_id else 0

        # Отношение конкретно к этому NPC
        relation = players.query(PlayerRelation).filter_by(
            player_id=player_id, npc_id=npc_id
        ).first()
        npc_attitude = relation.attitude if relation else npc.player_relationship

        # Загружаем диалог
        if npc.is_named and npc.dialog_file:
            dialog_data = load_dialog(npc.dialog_file)
        elif npc.is_named:
            dialog_data = load_dialog(npc.id)
        else:
            dialog_data = get_generic_dialog(npc.faction_id, npc.role or 'soldier')

        if not dialog_data:
            return {'error': 'Нет данных для диалога'}

        greeting = _pick_greeting(dialog_data, faction_rep, npc_attitude)

        return {
            'npc_id': npc.id,
            'npc_name': npc.name,
            'npc_callsign': npc.callsign,
            'faction_id': npc.faction_id,
            'rank': npc.rank,
            'greeting': greeting,
            'choices': dialog_data.get('choices', []),
            'faction_rep': faction_rep,
            'npc_attitude': npc_attitude,
        }
    finally:
        world.close()
        players.close()


def _pick_greeting(dialog_data, faction_rep, npc_attitude):
    """Выбрать приветствие в зависимости от отношения."""
    greetings = dialog_data.get('greetings', {})
    if isinstance(greetings, str):
        return greetings

    if npc_attitude <= -50 or faction_rep <= -50:
        key = 'hostile'
    elif npc_attitude <= -20 or faction_rep <= -20:
        key = 'unfriendly'
    elif npc_attitude >= 50 or faction_rep >= 50:
        key = 'ally'
    elif npc_attitude >= 20 or faction_rep >= 20:
        key = 'friendly'
    else:
        key = 'neutral'

    options = greetings.get(key) or greetings.get('neutral') or []
    if isinstance(options, list) and options:
        return random.choice(options)
    return "..."


# ==================== ОБРАБОТКА ВЫБОРА ====================

def process_choice(player_id, npc_id, choice_index):
    """Обработать выбор игрока в диалоге."""
    world = get_world_session()
    players = get_players_session()
    try:
        npc = world.query(NPC).filter_by(id=npc_id).first()
        if not npc:
            return {'error': 'NPC не найден'}

        player = players.query(Player).filter_by(id=player_id).first()
        if not player:
            return {'error': 'Игрок не найден'}

        # Загружаем диалог
        if npc.is_named:
            dialog_data = load_dialog(npc.dialog_file or npc.id)
        else:
            dialog_data = get_generic_dialog(npc.faction_id, npc.role or 'soldier')

        if not dialog_data:
            return {'error': 'Нет данных диалога'}

        choices = dialog_data.get('choices', [])
        if choice_index < 0 or choice_index >= len(choices):
            return {'error': 'Неверный выбор'}

        choice = choices[choice_index]
        reply = choice.get('reply', '')
        effects = choice.get('effects', {})

        result = {
            'reply': reply,
            'effects': {},
        }

        # Репутация с фракцией
        if 'rep' in effects and npc.faction_id:
            delta = effects['rep']
            _change_faction_rep(player, npc.faction_id, delta)
            result['effects']['rep'] = delta

        # Репутация с NPC лично
        if 'npc_attitude' in effects:
            delta = effects['npc_attitude']
            _change_npc_attitude(players, player_id, npc_id, delta)
            result['effects']['npc_attitude'] = delta

        # Деньги
        if 'rc' in effects:
            player.radcoins = max(0, player.radcoins + effects['rc'])
            result['effects']['rc'] = effects['rc']

        if 'rf' in effects:
            player.radfragments = max(0, player.radfragments + effects['rf'])
            result['effects']['rf'] = effects['rf']

        # Предмет
        if 'item' in effects:
            item_id = effects['item']
            count = effects.get('item_count', 1)
            _give_item(player, item_id, count)
            result['effects']['item'] = item_id
            result['effects']['item_count'] = count

        # Действия
        action = choice.get('action')
        if action:
            result['action'] = action
            _handle_action(action, player, npc, world, players)

        # Лог
        log = PlayerLog(
            player_id=player_id,
            action='dialog',
            item=f"{npc.name}:{choice_index}",
            details=json.dumps(result['effects']),
        )
        players.add(log)

        players.commit()
        world.commit()
        return result

    except Exception as e:
        logger.error(f"Ошибка обработки диалога: {e}")
        players.rollback()
        world.rollback()
        return {'error': str(e)}
    finally:
        world.close()
        players.close()


# ==================== ЭФФЕКТЫ ====================

def _change_faction_rep(player, faction_id, delta):
    """Изменить репутацию с фракцией."""
    reps = json.loads(player.faction_rep or '{}')
    current = reps.get(faction_id, 0)
    reps[faction_id] = clamp(current + delta, REP_MIN, REP_MAX)
    player.faction_rep = json.dumps(reps)


def _change_npc_attitude(players_session, player_id, npc_id, delta):
    """Изменить личное отношение NPC."""
    rel = players_session.query(PlayerRelation).filter_by(
        player_id=player_id, npc_id=npc_id
    ).first()
    if not rel:
        rel = PlayerRelation(player_id=player_id, npc_id=npc_id, attitude=0)
        players_session.add(rel)
    rel.attitude = clamp(rel.attitude + delta, REP_MIN, REP_MAX)
    rel.met_at = datetime.now()


def _give_item(player, item_id, count):
    """Выдать предмет в инвентарь игрока."""
    inv = json.loads(player.inventory or '[]')
    for entry in inv:
        if entry.get('item') == item_id:
            entry['count'] = entry.get('count', 0) + count
            break
    else:
        inv.append({'item': item_id, 'count': count})
    player.inventory = json.dumps(inv)


def _remove_item(player, item_id, count=1):
    """Убрать предмет из инвентаря."""
    inv = json.loads(player.inventory or '[]')
    for entry in inv:
        if entry.get('item') == item_id:
            entry['count'] = entry.get('count', 0) - count
            if entry['count'] <= 0:
                inv.remove(entry)
            break
    player.inventory = json.dumps(inv)


# ==================== ДЕЙСТВИЯ ====================

def _handle_action(action, player, npc, world, players):
    """Обработать специальное действие из диалога."""
    if action == 'attack':
        npc.is_alive = False
        npc.death_date = datetime.now()
        npc.death_reason = f"Убит игроком {player.username}"
        player.npcs_killed = (player.npcs_killed or 0) + 1
        if npc.faction_id:
            _change_faction_rep(player, npc.faction_id, -15)

    elif action == 'help':
        player.npcs_helped = (player.npcs_helped or 0) + 1
        if npc.faction_id:
            _change_faction_rep(player, npc.faction_id, 5)

    elif action == 'trade':
        pass  # Открыть торговлю — обрабатывается в UI

    elif action == 'join_faction' and npc.faction_id:
        player.faction_id = npc.faction_id
        player.faction_rank = 'rookie' if npc.faction_id == 'volya' else 'private'
        _change_faction_rep(player, npc.faction_id, 20)

    elif action == 'leave_faction' and player.faction_id:
        _change_faction_rep(player, player.faction_id, -10)
        player.faction_id = None
        player.faction_rank = None

    elif action == 'recruit':
        _change_faction_rep(player, npc.faction_id, 10)

    elif action == 'give_quest':
        pass  # Обрабатывается в квестах

    elif action == 'end':
        pass


# ==================== ГЕНЕРАЦИЯ ДИАЛОГА ДЛЯ РЯДОВОГО ====================

def generate_generic_choices(npc):
    """Сгенерировать базовые варианты ответа для рядового NPC."""
    choices = [
        {'text': '👋 Поздороваться', 'reply': '— Приветствую.', 'effects': {'rep': 1}},
        {'text': '❓ Спросить о делах', 'reply': '— Дела как обычно. Война.', 'effects': {'rep': 0}},
        {'text': '🚶 Уйти', 'reply': '— Ходи с миром.', 'effects': {}},
    ]
    if npc.is_trader:
        choices.insert(1, {'text': '💰 Торговать', 'reply': '— Показывай деньги.',
                           'effects': {}, 'action': 'trade'})
    return choices