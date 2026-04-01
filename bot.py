import asyncio
import logging
import sqlite3
import random
import time
import re
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Конфигурация
TOKEN = "7991920232:AAFgSw82BeYdJ0imvYoaNkashAtoMd9gyC0"
START_BALANCE = 2500
BONUS_AMOUNT = 2500
BONUS_COOLDOWN = 5 * 3600
ROBBERY_COOLDOWN = 5 * 60
CHAT_LINK = "https://t.me/AlIynQgYuB84OTY6"
CHANNEL_LINK = "https://t.me/adecvtek"

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Состояния для FSM
class GameStates(StatesGroup):
    cards = State()
    field = State()

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('tonn_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 2500,
            last_bonus INTEGER DEFAULT 0,
            last_robbery INTEGER DEFAULT 0,
            games_played INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            created_at INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS game_states (
            user_id INTEGER PRIMARY KEY,
            game_type TEXT,
            game_data TEXT,
            updated_at INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# Вспомогательные функции
def get_user(user_id: int, username: str = None) -> tuple:
    conn = sqlite3.connect('tonn_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        current_time = int(time.time())
        cursor.execute('''
            INSERT INTO users (user_id, username, balance, last_bonus, last_robbery, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, username, START_BALANCE, 0, 0, current_time))
        conn.commit()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
    
    conn.close()
    return user

def update_balance(user_id: int, amount: int):
    conn = sqlite3.connect('tonn_bot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def get_balance(user_id: int) -> int:
    conn = sqlite3.connect('tonn_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else START_BALANCE

def save_game_state(user_id: int, game_type: str, data: dict):
    conn = sqlite3.connect('tonn_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO game_states (user_id, game_type, game_data, updated_at)
        VALUES (?, ?, ?, ?)
    ''', (user_id, game_type, json.dumps(data), int(time.time())))
    conn.commit()
    conn.close()

def get_game_state(user_id: int) -> Tuple[Optional[str], Optional[dict]]:
    conn = sqlite3.connect('tonn_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT game_type, game_data FROM game_states WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0], json.loads(result[1])
    return None, None

def clear_game_state(user_id: int):
    conn = sqlite3.connect('tonn_bot.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM game_states WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def generate_cards() -> list:
    buttons = ['💣', '✅', '✅']
    random.shuffle(buttons)
    return buttons

def get_multiplier(level: int) -> float:
    multipliers = {1: 1.33, 2: 1.66, 3: 2.0, 4: 3.0, 5: 5.0}
    return multipliers.get(level, 1.0)

# Команды
@dp.message(Command("start"))
async def start_command(message: Message):
    user = get_user(message.from_user.id, message.from_user.username)
    await message.answer(
        f"🎲 Добро пожаловать в TONN Casino! 🎲\n\n"
        f"💰 Баланс: {user[2]} TONN\n\n"
        f"📌 Команды:\n"
        f"🎴 /карты [ставка] - игра Карты\n"
        f"🎲 /поле [ставка] - игра Поле\n"
        f"🎰 /казино [ставка] - слот\n"
        f"💰 /ограбить - ограбление (5 мин)\n"
        f"💎 /б или /баланс - баланс\n"
        f"🎁 /бонус - бонус 2500 TONN (5 часов)\n"
        f"🏆 /топ - топ игроков\n"
        f"📤 /т [сумма] - перевод (ответом)\n"
        f"🏁 /забрать - забрать выигрыш"
    )

@dp.message(Command("б"))
@dp.message(Command("баланс"))
async def balance_command(message: Message):
    user = get_user(message.from_user.id, message.from_user.username)
    current_time = int(time.time())
    last_bonus = user[3] or 0
    
    if current_time - last_bonus >= BONUS_COOLDOWN:
        bonus_text = f"\n\n🎁 Бонус доступен! Напиши /бонус"
    else:
        remaining = BONUS_COOLDOWN - (current_time - last_bonus)
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        bonus_text = f"\n\n⏰ Бонус через {hours}ч {minutes}мин"
    
    await message.answer(f"💰 Баланс: {user[2]} TONN{bonus_text}")

@dp.message(Command("бонус"))
async def bonus_command(message: Message):
    user = get_user(message.from_user.id, message.from_user.username)
    current_time = int(time.time())
    last_bonus = user[3] or 0
    
    if current_time - last_bonus < BONUS_COOLDOWN:
        remaining = BONUS_COOLDOWN - (current_time - last_bonus)
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        await message.answer(f"⏰ Бонус будет доступен через {hours}ч {minutes}мин")
        return
    
    update_balance(message.from_user.id, BONUS_AMOUNT)
    
    conn = sqlite3.connect('tonn_bot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET last_bonus = ? WHERE user_id = ?', (current_time, message.from_user.id))
    conn.commit()
    conn.close()
    
    await message.answer(f"✅ Получено {BONUS_AMOUNT} TONN!\n💰 Баланс: {get_balance(message.from_user.id)} TONN")

@dp.message(Command("топ"))
async def top_command(message: Message):
    conn = sqlite3.connect('tonn_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, balance FROM users ORDER BY balance DESC LIMIT 10')
    top_users = cursor.fetchall()
    conn.close()
    
    if not top_users:
        await message.answer("🏆 ТОП ИГРОКОВ TONN 🏆\n\nПока нет игроков. Стань первым!")
        return
    
    text = "🏆 ТОП ИГРОКОВ TONN 🏆\n\n"
    for i, user in enumerate(top_users, 1):
        username = user[1] or f"user{user[0]}"
        text += f"{i}. @{username} — {user[2]} TONN\n"
    
    await message.answer(text)

@dp.message(Command("т"))
async def transfer_command(message: Message):
    if not message.reply_to_message:
        await message.answer("❌ Ответьте на сообщение пользователя!\n\nПример: /т 500 (ответом на сообщение)")
        return
    
    try:
        amount = int(message.text.split()[1])
    except (IndexError, ValueError):
        await message.answer("❌ Укажите сумму!\n\nПример: /т 500")
        return
    
    if amount <= 0:
        await message.answer("🚫 НУ БЛЯДЬ БОЛЬШЕ СТАВЬ 🚫")
        return
    
    sender_id = message.from_user.id
    receiver_id = message.reply_to_message.from_user.id
    receiver_name = message.reply_to_message.from_user.username or f"user{receiver_id}"
    
    if sender_id == receiver_id:
        await message.answer("🚫 ТЫ ДАЛБАЕБ? 🚫")
        return
    
    sender_balance = get_balance(sender_id)
    
    if sender_balance < amount:
        await message.answer(f"❌ Недостаточно средств!\n💰 Баланс: {sender_balance} TONN\n📤 Нужно: {amount} TONN")
        return
    
    update_balance(sender_id, -amount)
    update_balance(receiver_id, amount)
    
    await message.answer(
        f"✅ Перевод выполнен!\n\n"
        f"📤 Отправитель: @{message.from_user.username}\n"
        f"📥 Получатель: @{receiver_name}\n"
        f"💵 Сумма: {amount} TONN\n\n"
        f"💰 Ваш баланс: {get_balance(sender_id)} TONN"
    )

@dp.message(Command("карты"))
async def cards_command(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Укажите ставку!\n\nПример: /карты 200")
        return
    
    try:
        bet = int(parts[1])
    except ValueError:
        await message.answer("❌ Ставка должна быть числом!\n\nПример: /карты 200")
        return
    
    if bet <= 0:
        await message.answer("🚫 НУ БЛЯДЬ БОЛЬШЕ СТАВЬ 🚫")
        return
    
    balance = get_balance(message.from_user.id)
    
    if bet > balance:
        await message.answer(f"❌ Недостаточно средств!\n💰 Баланс: {balance} TONN\n🎲 Ставка: {bet} TONN")
        return
    
    update_balance(message.from_user.id, -bet)
    
    buttons = generate_cards()
    
    save_game_state(message.from_user.id, "cards", {
        'bet': bet,
        'level': 1,
        'buttons': buttons,
        'win': 0
    })
    
    text = f"🎴 Карты {bet}\n\nTONN\n@{message.from_user.username}, вы начали игру карты!\n\n"
    text += f"Уровень 1 | Множитель x1.33\n💰 Ставка: {bet} TONN\n\n"
    text += f"1️⃣ {buttons[0]}  2️⃣ {buttons[1]}  3️⃣ {buttons[2]}\n\n"
    text += f"Напиши цифру 1, 2 или 3 чтобы выбрать кнопку"
    
    await message.answer(text)

@dp.message(Command("поле"))
async def field_command(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Укажите ставку!\n\nПример: /поле 100")
        return
    
    try:
        bet = int(parts[1])
    except ValueError:
        await message.answer("❌ Ставка должна быть числом!\n\nПример: /поле 100")
        return
    
    if bet <= 0:
        await message.answer("🚫 НУ БЛЯДЬ БОЛЬШЕ СТАВЬ 🚫")
        return
    
    balance = get_balance(message.from_user.id)
    
    if bet > balance:
        await message.answer(f"❌ Недостаточно средств!\n💰 Баланс: {balance} TONN\n🎲 Ставка: {bet} TONN")
        return
    
    update_balance(message.from_user.id, -bet)
    
    # Генерируем поле 5x5 с 5 минами
    field = [['?' for _ in range(5)] for _ in range(5)]
    mines = []
    positions = list(range(25))
    random.shuffle(positions)
    
    for i in range(5):
        pos = positions[i]
        row = pos // 5
        col = pos % 5
        mines.append((row, col))
    
    save_game_state(message.from_user.id, "field", {
        'bet': bet,
        'field': field,
        'mines': mines,
        'win': 0,
        'opened': []
    })
    
    # Показываем поле
    field_text = "🎲 ПОЛЕ 5x5 (5 мин)\n\n"
    field_text += "    1  2  3  4  5\n"
    for row in range(5):
        field_text += f"{row+1}  "
        for col in range(5):
            field_text += f"{field[row][col]}  "
        field_text += "\n"
    
    field_text += f"\n💰 Ставка: {bet} TONN | За клетку +20 TONN\n"
    field_text += f"Напиши координаты клетки (например: 1 3) чтобы открыть\n"
    field_text += f"Или /забрать чтобы забрать выигрыш"
    
    await message.answer(field_text)

@dp.message(Command("казино"))
async def casino_command(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Укажите ставку!\n\nПример: /казино 200")
        return
    
    try:
        bet = int(parts[1])
    except ValueError:
        await message.answer("❌ Ставка должна быть числом!\n\nПример: /казино 200")
        return
    
    if bet <= 0:
        await message.answer("🚫 НУ БЛЯДЬ БОЛЬШЕ СТАВЬ 🚫")
        return
    
    balance = get_balance(message.from_user.id)
    
    if bet > balance:
        await message.answer(f"❌ Недостаточно средств!\n💰 Баланс: {balance} TONN\n🎰 Ставка: {bet} TONN")
        return
    
    update_balance(message.from_user.id, -bet)
    
    msg = await message.answer(
        f"🎰 КРУЧУ КАЗИНО 🎰\n\n"
        f"💵 Ставка: {bet} TONN\n\n"
        f"Крутим... крутим... крутим..."
    )
    
    await asyncio.sleep(3)
    
    result = random.random()
    
    if result < 0.7:
        win = 0
        text = f"🎰 КРУЧУ КАЗИНО 🎰\n\n❌ ВЫ ПРОИГРАЛИ ❌\n\n💵 Ставка: {bet} TONN"
    elif result < 0.9:
        multiplier = random.choice([2, 3, 5])
        win = int(bet * multiplier)
        update_balance(message.from_user.id, win)
        text = f"🎰 КРУЧУ КАЗИНО 🎰\n\n🎉 ВЫ ВЫИГРАЛИ! 🎉\n\n💵 Выиграно: {win} TONN\n📌 Поставлено: {bet} TONN\n✨ Множитель: x{multiplier}"
    else:
        win = int(bet * 10)
        update_balance(message.from_user.id, win)
        text = f"🎰 КРУЧУ КАЗИНО 🎰\n\n🔥 ДЖЕКПОТ! 🔥\n🎉 ВЫ ВЫИГРАЛИ ДЖЕКПОТ! 🎉\n\n💵 Выиграно: {win} TONN\n📌 Поставлено: {bet} TONN\n✨ Множитель: x10"
    
    await msg.edit_text(text)

@dp.message(Command("ограбить"))
@dp.message(Command("ограбить_казну"))
async def robbery_command(message: Message):
    user = get_user(message.from_user.id, message.from_user.username)
    current_time = int(time.time())
    last_robbery = user[4] or 0
    
    if current_time - last_robbery < ROBBERY_COOLDOWN:
        remaining = ROBBERY_COOLDOWN - (current_time - last_robbery)
        minutes = remaining // 60
        seconds = remaining % 60
        await message.answer(f"⏰ Подождите {minutes} мин {seconds} сек до следующего ограбления!")
        return
    
    conn = sqlite3.connect('tonn_bot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET last_robbery = ? WHERE user_id = ?', (current_time, message.from_user.id))
    conn.commit()
    conn.close()
    
    fail_scenarios = [
        "вас заметили когда заходили в сейф",
        "вас заметили когда перерезали провода",
        "вас заметили когда отключали сигнализацию",
        "вас заметили когда выходили из казны",
        "сработала скрытая камера",
        "охранник услышал шум",
        "собака вас учуяла",
        "вы наступили на лазерную ловушку",
        "дверь захлопнулась и вы застряли"
    ]
    
    success = random.choice([True, False])
    
    if success:
        win = random.randint(100, 10000)
        update_balance(message.from_user.id, win)
        text = f"🏃‍♀️ ВЫ УКРАЛИ АЛМАЗ 🏃‍♀️\n\n👮‍♂️ Полиция вас не смогла догнать\n\n💵 Получено: {win} TONN"
    else:
        scenario = random.choice(fail_scenarios)
        text = f"👮‍♂️ ВАС ПОЙМАЛИ 👮‍♂️\n\nНе смог ограбить :( 0 TONN\n\nКак заметили: {scenario}"
    
    await message.answer(text)

@dp.message(Command("забрать"))
async def collect_command(message: Message):
    state_type, state_data = get_game_state(message.from_user.id)
    
    if state_type == "cards":
        win = state_data.get('win', 0)
        if win > 0:
            update_balance(message.from_user.id, win)
        clear_game_state(message.from_user.id)
        await message.answer(f"💰 Вы забрали выигрыш: {win} TONN")
    
    elif state_type == "field":
        win = state_data.get('win', 0)
        if win > 0:
            update_balance(message.from_user.id, win)
        clear_game_state(message.from_user.id)
        await message.answer(f"💰 Вы забрали выигрыш: {win} TONN")
    
    else:
        await message.answer("❌ Нет активной игры!")

# Обработка выбора в игре Карты
@dp.message(lambda message: message.reply_to_message and message.text in ['1', '2', '3'])
async def cards_choice(message: Message):
    state_type, state_data = get_game_state(message.from_user.id)
    if state_type != "cards":
        return
    
    try:
        choice = int(message.text) - 1
        buttons = state_data['buttons']
        bet = state_data['bet']
        level = state_data['level']
        
        if buttons[choice] == '💣':
            clear_game_state(message.from_user.id)
            await message.answer(
                f"💣 ВЫ ПРОИГРАЛИ! 💣\n\n"
                f"Ставка: {bet} TONN\n"
                f"Выигрыш: 0 TONN\n\n"
                f"@{message.from_user.username}, вы проиграли..."
            )
        else:
            multiplier = get_multiplier(level)
            win = int(bet * multiplier)
            
            if level == 5:
                update_balance(message.from_user.id, win)
                clear_game_state(message.from_user.id)
                await message.answer(
                    f"🎉 ПОБЕДА! 🎉\n\n"
                    f"Ставка: {bet} TONN\n"
                    f"Выигрыш: {win} TONN\n"
                    f"Множитель: x{multiplier}\n\n"
                    f"@{message.from_user.username}, вы прошли все уровни!"
                )
            else:
                new_buttons = generate_cards()
                state_data['level'] = level + 1
                state_data['buttons'] = new_buttons
                state_data['win'] = win
                save_game_state(message.from_user.id, "cards", state_data)
                
                next_multiplier = get_multiplier(level + 1)
                text = f"✅ Уровень {level} пройден!\n\n"
                text += f"Текущий выигрыш: {win} TONN\n"
                text += f"Уровень {level + 1} | Множитель x{next_multiplier}\n\n"
                text += f"1️⃣ {new_buttons[0]}  2️⃣ {new_buttons[1]}  3️⃣ {new_buttons[2]}\n\n"
                text += f"Напиши цифру 1, 2 или 3"
                
                await message.answer(text)
                
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

# Обработка выбора в игре Поле
@dp.message(lambda message: re.match(r'^\d+\s+\d+$', message.text) and message.reply_to_message)
async def field_choice(message: Message):
    state_type, state_data = get_game_state(message.from_user.id)
    if state_type != "field":
        return
    
    try:
        coords = message.text.split()
        row = int(coords[0]) - 1
        col = int(coords[1]) - 1
        
        if row < 0 or row > 4 or col < 0 or col > 4:
            await message.answer("❌ Координаты от 1 до 5! Пример: 1 3")
            return
        
        bet = state_data['bet']
        mines = state_data['mines']
        win = state_data['win']
        opened = state_data.get('opened', [])
        
        if (row, col) in opened:
            await message.answer("❌ Эта клетка уже открыта!")
            return
        
        if (row, col) in mines:
            clear_game_state(message.from_user.id)
            
            # Показываем все мины
            field_text = "💣 ВЫ ПРОИГРАЛИ! 💣\n\n"
            field_text += f"Ставка: {bet} TONN\n"
            field_text += f"Выигрыш: 0 TONN\n\n"
            field_text += "Поле с минами:\n"
            field_text += "    1  2  3  4  5\n"
            for r in range(5):
                field_text += f"{r+1}  "
                for c in range(5):
                    if (r, c) in mines:
                        field_text += "💣 "
                    else:
                        field_text += "✅ "
                field_text += "\n"
            
            await message.answer(field_text)
        else:
            opened.append((row, col))
            win += 20
            state_data['win'] = win
            state_data['opened'] = opened
            save_game_state(message.from_user.id, "field", state_data)
            
            # Показываем обновленное поле
            field_text = f"✅ +20 TONN!\n\n"
            field_text += f"Текущий выигрыш: {win} TONN\n"
            field_text += f"Ставка: {bet} TONN\n"
            field_text += f"Открыто клеток: {len(opened)}/20\n\n"
            field_text += "    1  2  3  4  5\n"
            for r in range(5):
                field_text += f"{r+1}  "
                for c in range(5):
                    if (r, c) in opened:
                        if (r, c) in mines:
                            field_text += "💣 "
                        else:
                            field_text += "✅ "
                    else:
                        field_text += "? "
                field_text += "\n"
            
            field_text += "\nНапиши координаты клетки (например: 1 3) чтобы продолжить"
            field_text += f"\nИли /забрать чтобы забрать {win} TONN"
            
            await message.answer(field_text)
            
    except Exception as e:
        await message.answer(f"❌ Ошибка! Пример: 1 3")

# Запуск бота
async def main():
    logger.info("Бот TONN запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
