
import telebot
from telebot import types
import sqlite3
import csv
import base64
import logging
import time
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')

TOKEN = "PASTE_YOUR_NEW_TOKEN_HERE"
ADMINS = [7372947132, 7800773424, 5852874546]

bot = telebot.TeleBot(TOKEN)

db = sqlite3.connect("bot.db", check_same_thread=False)

def db_query(query, params=(), fetchone=False, fetchall=False, commit=False):
    cur = db.cursor()
    cur.execute(query, params)
    if commit:
        db.commit()
    if fetchone:
        return cur.fetchone()
    if fetchall:
        return cur.fetchall()

db_query("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    coins INTEGER DEFAULT 0,
    ref INTEGER
)
""", commit=True)

db_query("""
CREATE TABLE IF NOT EXISTS promocodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER,
    code TEXT
)
""", commit=True)

CASES = [
    {"id": 1, "name": "Bullpass", "price": 4},
    {"id": 2, "name": "Jim Ustoz", "price": 7},
    {"id": 3, "name": "Ruhiy Sho'rva", "price": 10},
    {"id": 4, "name": "Geysha Sirlari", "price": 15},
    {"id": 5, "name": "JOJO", "price": 23},
    {"id": 6, "name": "Torii Darvozasi", "price": 35},
]

def is_admin(uid):
    return uid in ADMINS

def menu(uid):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💰 Монеты", "🛒 Магазин")
    kb.add("💳 Баланс", "🆘 Поддержка")
    if is_admin(uid):
        kb.add("👑 Админ панель")
    bot.send_message(uid, "🏠 Главное меню", reply_markup=kb)

@bot.message_handler(commands=["start"])
def start(m):
    if not db_query("SELECT 1 FROM users WHERE user_id=?", (m.from_user.id,), fetchone=True):
        db_query("INSERT INTO users (user_id, coins) VALUES (?,?)", (m.from_user.id, 0), commit=True)
    menu(m.from_user.id)

@bot.message_handler(func=lambda m: m.text == "💳 Баланс")
def balance(m):
    coins = db_query("SELECT coins FROM users WHERE user_id=?", (m.from_user.id,), fetchone=True)
    coins = coins[0] if coins else 0
    bot.send_message(m.chat.id, f"💰 Ваш баланс: {coins} монет")

@bot.message_handler(func=lambda m: m.text == "💰 Монеты")
def invite(m):
    link = f"https://t.me/{bot.get_me().username}?start={m.from_user.id}"
    bot.send_message(m.chat.id, f"Приглашайте друзей:\n{link}")

@bot.message_handler(func=lambda m: m.text == "🛒 Магазин")
def shop(m):
    kb = types.InlineKeyboardMarkup()
    for case in CASES:
        kb.add(types.InlineKeyboardButton(
            f"{case['name']} - {case['price']} монет",
            callback_data=f"case_{case['id']}"
        ))
    bot.send_message(m.chat.id, "🎁 Выберите кейс:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("case_"))
def buy_case(c):
    cid = int(c.data.split("_")[1])
    case = next((x for x in CASES if x["id"] == cid), None)
    if not case:
        bot.answer_callback_query(c.id, "Кейс не найден")
        return

    coins = db_query("SELECT coins FROM users WHERE user_id=?", (c.from_user.id,), fetchone=True)
    coins = coins[0] if coins else 0

    if coins < case["price"]:
        bot.answer_callback_query(c.id, "Недостаточно монет")
        return

    promo = db_query("SELECT id, code FROM promocodes WHERE case_id=? LIMIT 1", (cid,), fetchone=True)
    if not promo:
        bot.answer_callback_query(c.id, "Промокоды закончились")
        return

    db_query("UPDATE users SET coins = coins - ? WHERE user_id=?", (case["price"], c.from_user.id), commit=True)
    db_query("DELETE FROM promocodes WHERE id=?", (promo[0],), commit=True)

    bot.send_message(c.from_user.id, f"🎁 Ваш промокод:\n{promo[1]}")
    bot.answer_callback_query(c.id, "Кейс успешно куплен!")

@bot.message_handler(func=lambda m: m.text == "🆘 Поддержка")
def support(m):
    bot.send_message(m.chat.id, "По вопросам: @frezzybull")

@bot.message_handler(func=lambda m: m.text == "👑 Админ панель")
def admin_panel(m):
    if not is_admin(m.from_user.id):
        return
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Добавить промокод")
    kb.add("💸 Выдать монеты")
    kb.add("⬅️ Назад")
    bot.send_message(m.chat.id, "👑 Админ панель", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "➕ Добавить промокод")
def add_promo(m):
    if not is_admin(m.from_user.id):
        return
    bot.send_message(m.chat.id, "Введите: case_id код")
    bot.register_next_step_handler(m, save_promo)

def save_promo(m):
    try:
        cid, code = m.text.split()
        db_query("INSERT INTO promocodes (case_id, code) VALUES (?,?)", (int(cid), code), commit=True)
        bot.send_message(m.chat.id, "Промокод добавлен")
    except:
        bot.send_message(m.chat.id, "Ошибка ввода")

@bot.message_handler(func=lambda m: m.text == "💸 Выдать монеты")
def give_coins(m):
    if not is_admin(m.from_user.id):
        return
    bot.send_message(m.chat.id, "Введите: user_id количество")
    bot.register_next_step_handler(m, process_give)

def process_give(m):
    try:
        uid, amount = m.text.split()
        db_query("UPDATE users SET coins = coins + ? WHERE user_id=?", (int(amount), int(uid)), commit=True)
        bot.send_message(m.chat.id, "Монеты выданы")
    except:
        bot.send_message(m.chat.id, "Ошибка ввода")

bot.infinity_polling(skip_pending=True)
