import telebot
from telebot import types
import sqlite3
import csv
import base64
import logging
import time
import requests
import tempfile
import os
import imghdr

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')

last_prompt = {}

def is_image_url(url):
    """Упрощенная проверка URL изображения"""
    if not url or not url.startswith("http"):
        return False
    return url.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".jfif"))

def send_photo_safe(chat_id, photo_url, caption=None, **kwargs):
    """Раемни юклаб олиш ва файл сифатида юбориш"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        logging.info(f"Раем юкланмокда: {photo_url}")
        
        # Раемни юклаш
        response = requests.get(photo_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Расширениени аниклаш
        ext = imghdr.what(None, response.content) or "jpg"
        if ext == "jfif":
            ext = "jpg"
        
        # Вактинчалик файлга ёзиш
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{ext}') as f:
            f.write(response.content)
            temp_path = f.name
        
        # Раемни юбориш
        try:
            with open(temp_path, 'rb') as photo_file:
                bot.send_photo(chat_id, photo_file, caption=caption, **kwargs)
            return True
        finally:
            # Файлни тозалаш
            try:
                os.unlink(temp_path)
            except:
                pass
                
    except Exception as e:
        logging.error(f"send_photo_safe хатоси: {str(e)[:100]}")
        return False

TOKEN = "8309105745:AAEoodMIvSiOqPEzkc3fqZhy4AX3nE3hYws"
ADMINS = [6001209350, 7388508151]

bot = telebot.TeleBot(TOKEN)

CASES = [
    {
        "id": 1,
        "name": "Bullpass",
        "price": 4,
        "category": 4,
        "photo": "https://files.catbox.moe/qpmm5f.jpg"
    },
    {
        "id": 2,
        "name": "Jim Ustoz",
        "price": 7,
        "category": 7,
        "photo": "https://files.catbox.moe/bz8az5.jpg"
    },
    {
        "id": 3,
        "name": "Ruhiy shoʻrva",
        "price": 10,
        "category": 10,
        "photo": "https://files.catbox.moe/t3978m.jpg"
    },
    {
        "id": 4,
        "name": "Geysha sirlari",
        "price": 15,
        "category": 15,
        "photo": "https://files.catbox.moe/fvdh78.jpg"
    },
    {
        "id": 5,
        "name": "JOJO",
        "price": 23,
        "category": 23,
        "photo": "https://files.catbox.moe/fnq42d.jpg"
    },
    {
        "id": 6,
        "name": "Torii darvozasi",
        "price": 35,
        "category": 35,
        "photo": "https://files.catbox.moe/t1kwv5.jpg"
    }
]

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
CREATE TABLE IF NOT EXISTS sponsors (
    channel TEXT
)
""", commit=True)

db_query("""
CREATE TABLE IF NOT EXISTS promocodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER,
    code TEXT
)
""", commit=True)

PROMO_FILE = "promocodes.csv"

def write_promos_file():
    """CSV файлни яратиш (факат бек-ап учун)"""
    try:
        rows = db_query("SELECT id, case_id, code FROM promocodes", fetchall=True)
        with open(PROMO_FILE, "w", newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(["id", "case_id", "code"])
            for r in rows:
                w.writerow(r)
    except Exception:
        pass  # CSV факат бек-ап, асосий логика SQLite да

def add_promocode(case_id, code):
    """Промокод қўшиш"""
    db_query(
        "INSERT INTO promocodes (case_id, code) VALUES (?,?)",
        (case_id, code),
        commit=True
    )

def remove_promocode_by_id(pid):
    """Промокодни ID бўйича ўчириш"""
    db_query(
        "DELETE FROM promocodes WHERE id=?",
        (pid,),
        commit=True
    )

db_query("""
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    description TEXT,
    reward INTEGER,
    creator INTEGER,
    assignee INTEGER,
    done INTEGER DEFAULT 0
)
""", commit=True)

try:
    db_query("ALTER TABLE tasks ADD COLUMN require_channel TEXT", commit=True)
except Exception:
    pass
try:
    db_query("ALTER TABLE tasks ADD COLUMN slots INTEGER DEFAULT 1", commit=True)
except Exception:
    pass

db_query("""
CREATE TABLE IF NOT EXISTS task_assignees (
    task_id INTEGER,
    user_id INTEGER,
    completed INTEGER DEFAULT 0,
    PRIMARY KEY (task_id, user_id)
)
""", commit=True)

try:
    rows = db_query("SELECT id, assignee FROM tasks WHERE assignee IS NOT NULL", fetchall=True)
    for tid, assg in rows:
        try:
            if assg:
                db_query("INSERT OR IGNORE INTO task_assignees (task_id, user_id, completed) VALUES (?,?,?)", (tid, assg, 0), commit=True)
        except Exception:
            pass
    db_query("UPDATE tasks SET assignee=NULL WHERE assignee IS NOT NULL", commit=True)
except Exception:
    pass

for a in ADMINS:
    res = db_query("SELECT coins FROM users WHERE user_id=?", (a,), fetchone=True)
    if res:
        db_query("UPDATE users SET coins = ? WHERE user_id=?", (1000, a), commit=True)
    else:
        db_query("INSERT INTO users (user_id, coins) VALUES (?,?)", (a, 1000), commit=True)

admin_state = {}

def is_admin(uid):
    return uid in ADMINS

def check_sub(uid):
    """Барча каналларга обуна бўлганлигини текшириш"""
    if is_admin(uid):
        return True

    chans = db_query("SELECT channel FROM sponsors", fetchall=True)
    if not chans:
        return True

    for (ch,) in chans:
        try:
            target = ch.strip()
            
            if target.startswith("https://t.me/") or target.startswith("t.me/"):
                if target.startswith("https://t.me/"):
                    username = target.replace("https://t.me/", "").lstrip("@")
                else:
                    username = target.replace("t.me/", "").lstrip("@")
                
                if "?" in username:
                    username = username.split("?")[0]
                if "/" in username:
                    username = username.split("/")[0]
                    
                target = f"@{username}"
            
            if not target.startswith("@") and not target.startswith("-100"):
                if target.isdigit():
                    target = f"-100{target}"
                else:
                    target = f"@{target}"
            
            try:
                member = bot.get_chat_member(target, uid)
                
                if member.status in ['left', 'kicked']:
                    logging.info(f"Фойдаланувчи {uid} {target} каналида эмас")
                    return False
                    
            except Exception as e:
                logging.error(f"{target} канали учун аъзоликни текширишда хатолик: {e}")
                continue  # Хатолик бўлса, канални ўтказамиз
                
        except Exception as e:
            logging.error(f"{ch} каналини қайта ишлашда хатолик: {e}")
            continue

    return True

def require_subscription(func):
    """Функцияни бажаришдан олдин обунани текшириш учун декоратор"""
    def wrapper(message):
        uid = message.from_user.id
        if not check_sub(uid):
            prompt_subscription(uid)
            return
        return func(message)
    return wrapper

def require_subscription_callback(func):
    """Callback функциясини бажаришдан олдин обунани текшириш учун декоратор"""
    def wrapper(call):
        uid = call.from_user.id
        if not check_sub(uid):
            bot.answer_callback_query(call.id, "❗ Аввал барча каналларга обуна бўлинг", show_alert=True)
            prompt_subscription(uid)
            return
        return func(call)
    return wrapper

def prompt_subscription(uid, text=None):
    """Фойдаланувчига стандарт обуна таклифини юбориш"""
    now = time.time()
    last = last_prompt.get(uid)
    if last and now - last < 60:
        return
    last_prompt[uid] = now

    kb = types.InlineKeyboardMarkup()
    sponsors = db_query("SELECT channel FROM sponsors", fetchall=True)

    if sponsors:
        for s in sponsors:
            ch = (s[0] or "").strip()
            if not ch:
                continue
            if ch.startswith("http://") or ch.startswith("https://"):
                url = ch
                disp = ch.rstrip('/').split('/')[-1]
                if not disp.startswith("@"):
                    disp = "@" + disp
            elif ch.startswith("t.me/"):
                path = ch.split('/', 1)[1]
                url = f"https://t.me/{path}"
                disp = "@" + path
            elif ch.startswith("@"):
                url = f"https://t.me/{ch[1:]}"
                disp = ch
            else:
                url = f"https://t.me/{ch}"
                disp = "@" + ch

            kb.add(types.InlineKeyboardButton(f"📢 {disp}", url=url))

    kb.add(types.InlineKeyboardButton("✅ Мен обуна болдим", callback_data="check"))

    msg = text or "❗ Аввал обуна бўлинг: илтимос, барча спонсор каналларига обуна бўлинг ва кейин тасдиқланг"
    try:
        bot.send_message(uid, msg, reply_markup=kb)
    except Exception as e:
        logging.exception("Обуна таклифини юборишда хатолик")

def menu(uid):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💰 Танга ишлаш", "🛒 Магазин")
    kb.add("💳 Баланс", "🆘 Қўллаб-қувватлаш")
    kb.add("📝 Вазифалар")
    if is_admin(uid):
        kb.add("👑 Админ панел")
    bot.send_message(uid, "🏠 Асосий меню", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "check")
def recheck(c):
    uid = c.from_user.id
    if check_sub(uid):
        bot.answer_callback_query(c.id, "✅ Раҳмат! Энди ботдан фойдаланишингиз мумкин.")
        try:
            bot.delete_message(c.message.chat.id, c.message.message_id)
        except:
            pass
        menu(uid)
    else:
        bot.answer_callback_query(
            c.id,
            "❌ Сиз ҳали барча каналларга обуна бўлмагансиз!",
            show_alert=True
        )

@bot.message_handler(commands=["start", "menu"])
def cmd_start(m):
    # FSM ни сброс қилиш
    admin_state.pop(m.from_user.id, None)
    
    # Реферал ҳаволани текшириш
    if len(m.text.split()) > 1:
        try:
            ref_id = int(m.text.split()[1])
            if ref_id != m.from_user.id:
                res = db_query("SELECT 1 FROM users WHERE user_id=?", (m.from_user.id,), fetchone=True)
                if not res:
                    db_query("INSERT INTO users (user_id, ref) VALUES (?,?)", (m.from_user.id, ref_id), commit=True)
                    db_query("UPDATE users SET coins = coins + 1 WHERE user_id=?", (ref_id,), commit=True)
        except:
            pass
    
    if not db_query("SELECT 1 FROM users WHERE user_id=?", (m.from_user.id,), fetchone=True):
        db_query("INSERT INTO users (user_id, coins) VALUES (?,?)", (m.from_user.id, 0), commit=True)
    
    if not check_sub(m.from_user.id):
        prompt_subscription(m.from_user.id)
        return
    
    menu(m.from_user.id)

@bot.message_handler(commands=["cancel"])
def cmd_cancel(m):
    if m.from_user.id in admin_state:
        admin_state.pop(m.from_user.id, None)
        bot.send_message(m.chat.id, "✅ Жараён бекор қилинди")
        menu(m.from_user.id)
    else:
        bot.send_message(m.chat.id, "ℹ️ Фаол жараёнлар топилмади")

@bot.message_handler(func=lambda m: getattr(m, 'text', '').strip() == "💰 Танга ишлаш")
@require_subscription
def earn(m):
    link = f"https://t.me/{bot.get_me().username}?start={m.from_user.id}"
    bot.send_message(m.chat.id, f"🔗 Дўстларингиз билан ҳаволани улашинг!\n\n{link}\n\nДўстларингиз билан улашинг ва промо кодларни бирга ютиб олинг🤩")

@bot.message_handler(func=lambda m: getattr(m, 'text', '').strip() == "💳 Баланс")
@require_subscription
def balance(m):
    res = db_query(
        "SELECT coins FROM users WHERE user_id=?",
        (m.from_user.id,),
        fetchone=True
    )
    coins = res[0] if res else 0

    total_coins = db_query("SELECT SUM(coins) FROM users", fetchone=True)[0] or 0
    active_users = db_query("SELECT COUNT(*) FROM users WHERE coins>0", fetchone=True)[0] or 0
    friends = db_query("SELECT COUNT(*) FROM users WHERE ref=?", (m.from_user.id,), fetchone=True)[0] or 0

    caption = (
        f"💰 Баланс: {coins} танга\n"
        f"📦 Жами танга: {total_coins} танга\n"
        f"🟢 Фаол фойдаланувчилар (танга>0): {active_users}\n"
        f"👥 Дўстларингиз сони: {friends}"
    )

    try:
        send_photo_safe(
            m.chat.id,
            "https://i.postimg.cc/fLGHvN5n/photo-5375494812305394909-y-(1).jpg",
            caption=caption
        )
    except Exception as e:
        logging.exception(f"Баланс расмини {m.chat.id} га юборишда хатолик: {e}")
        bot.send_message(m.chat.id, caption + "\n\n📷 Расм юборишда хатолик, ҳавола: https://i.postimg.cc/fLGHvN5n/photo-5375494812305394909-y-(1).jpg")

@bot.message_handler(func=lambda m: getattr(m, 'text', '').strip() == "🆘 Қўллаб-қувватлаш")
@require_subscription
def support(m):
    bot.send_message(m.chat.id, "🆘 Саволлар учун ёзинг: @admin")

@bot.message_handler(func=lambda m: any(word in (m.text or '').lower() for word in ['магазин', 'shop', '🛒']))
@require_subscription
def shop(m):
    uid = m.from_user.id

    kb = types.InlineKeyboardMarkup()
    for p in [4, 7, 10, 15, 23, 35]:
        kb.add(types.InlineKeyboardButton(f"{p} танга", callback_data=f"cat_{p}"))

    try:
        send_photo_safe(
            m.chat.id,
            "https://i.postimg.cc/6QR4vx77/photo-5375494812305394911-y-(1).jpg",
            caption="🎁 Кейс категориялари:",
            reply_markup=kb
        )
    except Exception:
        bot.send_message(
            m.chat.id,
            "🎁 Кейс категориялари:",
            reply_markup=kb
        )

@bot.callback_query_handler(func=lambda c: c.data.startswith("cat_"))
@require_subscription_callback
def show_cases(c):
    uid = c.from_user.id

    price = int(c.data.split("_")[1])
    kb = types.InlineKeyboardMarkup()

    for case in CASES:
        if case["category"] == price:
            kb.add(
                types.InlineKeyboardButton(
                    case["name"],
                    callback_data=f"case_{case['id']}"
                )
            )

    kb.add(types.InlineKeyboardButton("⬅️ Орқага", callback_data="back_cats"))

    try:
        bot.edit_message_text(
            "📦 Кейсни танланг:",
            c.message.chat.id,
            c.message.message_id,
            reply_markup=kb
        )
    except Exception:
        try:
            bot.edit_message_caption(
                "📦 Кейсни танланг:",
                c.message.chat.id,
                c.message.message_id,
                reply_markup=kb
            )
        except Exception:
            bot.send_message(
                c.message.chat.id,
                "📦 Кейсни танланг:",
                reply_markup=kb
            )

@bot.callback_query_handler(func=lambda c: c.data == "back_cats")
@require_subscription_callback
def back_to_cats(c):
    kb = types.InlineKeyboardMarkup()
    for p in [4, 7, 10, 15, 23, 35]:
        kb.add(types.InlineKeyboardButton(f"{p} танга", callback_data=f"cat_{p}"))

    try:
        bot.edit_message_text(
            "🎁 Кейс категориялари:",
            c.message.chat.id,
            c.message.message_id,
            reply_markup=kb
        )
    except Exception:
        try:
            bot.edit_message_caption(
                "🎁 Кейс категориялари:",
                c.message.chat.id,
                c.message.message_id,
                reply_markup=kb
            )
        except Exception:
            try:
                send_photo_safe(c.message.chat.id, "https://i.postimg.cc/6QR4vx77/photo-5375494812305394911-y-(1).jpg", caption="🎁 Кейс категориялари:", reply_markup=kb)
            except Exception as e:
                logging.exception(f"Категория расмини {c.message.chat.id} га юборишда хатолик: {e}")
                bot.send_message(c.message.chat.id, "🎁 Кейс категориялари:\n\n📷 Расм юборишда хатолик, ҳавола: https://i.postimg.cc/6QR4vx77/photo-5375494812305394911-y-(1).jpg", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("case_"))
@require_subscription_callback
def buy_case(c):
    uid = c.from_user.id
    
    cid = int(c.data.split("_")[1])

    case = next((x for x in CASES if x["id"] == cid), None)
    if not case:
        bot.answer_callback_query(c.id, "❌ Кейс топилмади")
        return

    res = db_query(
        "SELECT coins FROM users WHERE user_id=?",
        (uid,),
        fetchone=True
    )
    coins = res[0] if res else 0

    if coins < case["price"]:
        bot.answer_callback_query(c.id, "❌ Етарли танга йўқ")
        return

    promo = db_query(
        "SELECT id, code FROM promocodes WHERE case_id=? LIMIT 1",
        (cid,),
        fetchone=True
    )

    if not promo:
        bot.answer_callback_query(c.id, "❌ Промокодлар тугади")
        return

    # Тангаларни хисобдан ўчириш
    db_query(
        "UPDATE users SET coins = coins - ? WHERE user_id=?",
        (case["price"], uid),
        commit=True
    )

    # Промокодни ўчириш
    remove_promocode_by_id(promo[0])

    photo_url = case.get("photo", "").strip()
    promo_code = promo[1]
    
    # Аввал расм юборишга уринамиз
    try:
        success = send_photo_safe(
            uid,
            photo_url,
            f"🎁 {case['name']}\n🎫 Промокод: `{promo_code}`",
            parse_mode="Markdown"
        )
        if not success:
            raise Exception("send_photo_safe муваффақиятсиз")
    except Exception as e:
        logging.error(f"Расм юборишда хатолик: {e}")
        # Факат матн юборамиз
        bot.send_message(
            uid,
            f"🎁 {case['name']}\n🎫 Промокод: `{promo_code}`",
            parse_mode="Markdown"
        )
    
    bot.answer_callback_query(c.id, "✅ Кейс сотиб олинди!")

@bot.message_handler(func=lambda m: getattr(m, 'text', '').strip() == "👑 Админ панел")
def admin_panel(m):
    if not is_admin(m.from_user.id):
        return

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Промокод қўшиш")
    kb.add("💸 Танга бериш")
    kb.add("➕ Вазифа яратиш")
    kb.add("📢 Спонсор қўшиш")
    kb.add("📊 Статистика")
    kb.add("⬅️ Орқага")
    bot.send_message(m.chat.id, "👑 Админ панел", reply_markup=kb)

@bot.message_handler(func=lambda m: getattr(m, 'text', '').strip() == "⬅️ Орқага")
def back(m):
    menu(m.from_user.id)

@bot.message_handler(func=lambda m: getattr(m, 'text', '').strip() == "➕ Промокод қўшиш")
def add_promo_start(m):
    if not is_admin(m.from_user.id):
        return

    kb = types.InlineKeyboardMarkup()
    for case in CASES:
        kb.add(types.InlineKeyboardButton(
            case["name"],
            callback_data=f"promo_{case['id']}"
        ))

    bot.send_message(m.chat.id, "📦 Кейсни танланг:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("promo_"))
def promo_case(c):
    admin_state[c.from_user.id] = {
        "step": "promo_count",
        "case_id": int(c.data.split("_")[1])
    }
    bot.send_message(c.message.chat.id, "🎫 Нечта промокод қўшмоқчисиз?")

@bot.message_handler(func=lambda m: m.from_user.id in admin_state and admin_state[m.from_user.id]["step"] == "promo_count")
def promo_count(m):
    if not is_admin(m.from_user.id):
        admin_state.pop(m.from_user.id, None)
        return
    try:
        admin_state[m.from_user.id]["left"] = int(m.text)
    except ValueError:
        bot.send_message(m.chat.id, "❌ Илтимос, сон киритинг")
        return
    admin_state[m.from_user.id]["step"] = "promo_add"
    bot.send_message(m.chat.id, "✍️ Промокодларни бирма-бир юборинг")

@bot.message_handler(func=lambda m: m.from_user.id in admin_state and admin_state[m.from_user.id]["step"] == "promo_add")
def promo_add(m):
    if not is_admin(m.from_user.id):
        admin_state.pop(m.from_user.id, None)
        return
    s = admin_state[m.from_user.id]

    add_promocode(s["case_id"], m.text)

    s["left"] -= 1
    if s["left"] == 0:
        del admin_state[m.from_user.id]
        bot.send_message(m.chat.id, "✅ Промокодлар қўшилди")

@bot.message_handler(func=lambda m: getattr(m, 'text', '').strip() == "📢 Спонсор қўшиш")
def add_sponsor(m):
    if not is_admin(m.from_user.id):
        return
    admin_state[m.from_user.id] = {"step": "sponsor"}
    bot.send_message(m.chat.id, "📢 @канал ёки ҳавола юборинг (масалан: @channel_name ёки https://t.me/channel_name)")

def _normalize_channel_input(ch_text):
    ch = (ch_text or "").strip()
    try:
        if ch.startswith("http://") or ch.startswith("https://"):
            ch = ch.rstrip('/').split('/')[-1]
            if "?" in ch:
                ch = ch.split("?")[0]
        if ch.startswith("t.me/"):
            ch = ch.split('/', 1)[1]
            if "?" in ch:
                ch = ch.split("?")[0]
        if not ch.startswith("@"):
            ch = "@" + ch
    except Exception:
        ch = ch_text.strip()
    return ch

@bot.message_handler(func=lambda m: m.from_user.id in admin_state and admin_state[m.from_user.id]["step"] == "sponsor")
def save_sponsor(m):
    if not is_admin(m.from_user.id):
        admin_state.pop(m.from_user.id, None)
        return

    ch_raw = m.text.strip()
    ch = _normalize_channel_input(ch_raw)

    try:
        chat_info = bot.get_chat(ch)
        logging.info(f"Канал маълумоти: {chat_info.title} ({chat_info.id})")
        
        try:
            bot_member = bot.get_chat_member(ch, bot.get_me().id)
            if bot_member.status not in ['administrator', 'creator']:
                bot.send_message(
                    m.chat.id,
                    f"⚠️ Бот {ch} каналида администратор эмас\n\n"
                    f"Обуналарни текшириш учун бот каналда администратор бўлиши керак.\n"
                    f"Ботни {ch} каналига 'Аъзоларни кўриш' ҳуқуқи билан администратор қилиб қўйинг."
                )
                return
        except Exception as e:
            if "chat not found" not in str(e).lower() and "bot is not a member" not in str(e).lower():
                logging.warning(f"{ch} учун бот админ статусини текшириб бўлмади: {e}")
    
    except Exception as e:
        error_msg = str(e).lower()
        if "chat not found" in error_msg:
            bot.send_message(
                m.chat.id,
                f"❌ {ch} канали топилмади ёки шахсий.\n\n"
                f"Шахсий каналлар учун:\n"
                f"1. Ботни каналга администратор қилиб қўйинг\n"
                f"2. Ботга 'Аъзоларни кўриш' ҳуқуқини беринг\n"
                f"3. Шундан сўнг канални қайта қўшиб кўринг"
            )
        elif "bot is not a member" in error_msg:
            bot.send_message(
                m.chat.id,
                f"❌ Бот {ch} каналига қўшилмаган\n\n"
                f"Илтимос:\n"
                f"1. Ботни @{bot.get_me().username} каналига қўшинг\n"
                f"2. Ботни администратор қилинг\n"
                f"3. 'Аъзоларни кўриш' ҳуқуқини беринг\n"
                f"4. Қайта уриниб кўринг"
            )
        else:
            bot.send_message(
                m.chat.id, 
                f"⚠️ {ch} каналини текширишда хатолик: {e}\n"
                f"Илтимос, канал мавжудлигига ва бот унга кириш ҳуқуқига эга эканлигига ишонч ҳосил қилинг."
            )
        return

    existing = db_query("SELECT 1 FROM sponsors WHERE channel=?", (ch,), fetchone=True)
    if existing:
        del admin_state[m.from_user.id]
        bot.send_message(m.chat.id, "ℹ️ Бу спонсор аллақачон мавжуд")
        return

    admin_state[m.from_user.id] = {
        "step": "sponsor_confirm",
        "pending": ch
    }

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔁 Ўзгартириш", callback_data="sponsor_edit"))
    kb.add(types.InlineKeyboardButton("✅ Тайёр", callback_data="sponsor_confirm"))
    kb.add(types.InlineKeyboardButton("❌ Бекор қилиш", callback_data="sponsor_cancel"))

    try:
        bot.send_message(m.chat.id, f"📢 Топилди: {ch}\nИлтимос тасдиқланг ёки ўзгартиринг:", reply_markup=kb)
    except Exception as e:
        logging.exception("Спонсор тасдиқлаш тугмаларини юборишда хатолик: %s", e)
        bot.send_message(m.chat.id, f"📢 Топилди: {ch}\nИлтимос тасдиқланг ёки ўзгартиринг:\n(Inline тугмалар юборилмади — илтимос, /sponsors билан текширинг ёки қайта юборинг)")

@bot.message_handler(func=lambda m: getattr(m, 'text', '').strip() == "➕ Вазифа яратиш")
def create_task_start(m):
    if not is_admin(m.from_user.id):
        return
    admin_state[m.from_user.id] = {"step": "task_title"}
    bot.send_message(m.chat.id, "✍️ Вазифа сарлавҳасини киритинг")

@bot.message_handler(func=lambda m: m.from_user.id in admin_state and admin_state[m.from_user.id]["step"] == "task_title")
def create_task_title(m):
    if not is_admin(m.from_user.id):
        admin_state.pop(m.from_user.id, None)
        return
    admin_state[m.from_user.id] = {"step": "task_desc", "title": m.text}
    bot.send_message(m.chat.id, "✍️ Вазифа матнини киритинг")

@bot.message_handler(func=lambda m: m.from_user.id in admin_state and admin_state[m.from_user.id]["step"] == "task_desc")
def create_task_desc(m):
    if not is_admin(m.from_user.id):
        admin_state.pop(m.from_user.id, None)
        return
    s = admin_state[m.from_user.id]
    s["desc"] = m.text
    s["step"] = "task_reward"
    bot.send_message(m.chat.id, "✍️ Неча танга берасиз? (сон)")

@bot.message_handler(func=lambda m: m.from_user.id in admin_state and admin_state[m.from_user.id]["step"] == "task_slots")
def create_task_slots(m):
    if not is_admin(m.from_user.id):
        admin_state.pop(m.from_user.id, None)
        return
    s = admin_state[m.from_user.id]
    try:
        slots = int(m.text)
        if slots < 1:
            raise ValueError
    except Exception:
        bot.send_message(m.chat.id, "❌ Илтимос, 1 ёки ундан катта бутун сон киритинг")
        return
    s["slots"] = slots
    s["step"] = "task_require"
    bot.send_message(m.chat.id, "🔗 Агар вазифа учун каналга обуна бўлиш талаб қилинса, канални (@канал ёки t.me/ҳавола) юборинг; агар талаб йўқ бўлса 'йўқ' ёзинг")

@bot.message_handler(func=lambda m: m.from_user.id in admin_state and admin_state[m.from_user.id]["step"] == "task_reward")
def create_task_reward(m):
    if not is_admin(m.from_user.id):
        admin_state.pop(m.from_user.id, None)
        return
    s = admin_state[m.from_user.id]
    try:
        reward = int(m.text)
    except Exception:
        bot.send_message(m.chat.id, "❌ Бутун сон киритинг")
        return

    s["reward"] = reward
    s["step"] = "task_slots"
    bot.send_message(m.chat.id, "🔢 Нечта иштирокчи рухсат этилади? (бутун сон, стандарт 1)")

@bot.message_handler(func=lambda m: m.from_user.id in admin_state and admin_state[m.from_user.id]["step"] == "task_require")
def create_task_require(m):
    if not is_admin(m.from_user.id):
        admin_state.pop(m.from_user.id, None)
        return
    s = admin_state[m.from_user.id]
    channel = m.text.strip()
    if channel.lower() == "йўқ" or channel == "":
        channel = None

    db_query(
        "INSERT INTO tasks (title, description, reward, creator, require_channel, slots) VALUES (?,?,?,?,?,?)",
        (s["title"], s["desc"], s["reward"], m.from_user.id, channel, s.get("slots", 1)),
        commit=True
    )

    tid = db_query("SELECT last_insert_rowid()", fetchone=True)[0]
    bot.send_message(m.chat.id, f"✅ Вазифа яратилди (id: {tid})")
    del admin_state[m.from_user.id]

def _encode_channel(ch):
    return base64.urlsafe_b64encode(ch.encode()).decode()

def _decode_channel(enc):
    try:
        return base64.urlsafe_b64decode(enc.encode()).decode()
    except Exception:
        return enc

@bot.message_handler(commands=["sponsors"])
def cmd_sponsors(m):
    sponsors = db_query("SELECT channel FROM sponsors", fetchall=True)
    if not sponsors:
        bot.send_message(m.chat.id, "ℹ️ Ҳозирча спонсор каналлари рўйхати бўш")
        return

    kb = types.InlineKeyboardMarkup()
    isadm = is_admin(m.from_user.id)
    for s in sponsors:
        ch = s[0]
        if not ch:
            continue
        
        url = ch
        if ch.startswith("@"):
            url = f"https://t.me/{ch[1:]}"
        elif not ch.startswith("http"):
            url = f"https://t.me/{ch.lstrip('@')}"
        
        kb_row = []
        kb_row.append(types.InlineKeyboardButton(f"📢 {ch}", url=url))
        if isadm:
            enc = _encode_channel(ch)
            kb_row.append(types.InlineKeyboardButton("🗑 Ўчириш", callback_data=f"remove_sponsor_{enc}"))
        kb.row(*kb_row)

    bot.send_message(m.chat.id, "📢 Спонсор каналлари:", reply_markup=kb)

@bot.message_handler(func=lambda m: getattr(m, 'text', '').strip() == "📝 Вазифалар")
@require_subscription
def list_tasks(m):
    rows = db_query("SELECT id, title, description, reward, require_channel, slots FROM tasks WHERE done=0", fetchall=True)
    out_count = 0
    for r in rows:
        tid, title, desc, reward, req, slots = r
        current = db_query("SELECT COUNT(*) FROM task_assignees WHERE task_id=?", (tid,), fetchone=True)[0] or 0
        remaining = (slots or 1) - current
        if remaining <= 0:
            continue
        out_count += 1
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Қабул қиламан", callback_data=f"accept_{tid}"))
        text = f"📝 {title}\n{desc}\n💰 Мукофот: {reward} танга\n🔢 Қолган ўринлар: {remaining}"
        if req:
            text += f"\n🔒 Обуна талаб қилинади: {req}"
        bot.send_message(m.chat.id, text, reply_markup=kb)
    if out_count == 0:
        bot.send_message(m.chat.id, "ℹ️ Ҳозирча мавжуд вазифалар йўқ")

@bot.callback_query_handler(func=lambda c: c.data.startswith("accept_"))
@require_subscription_callback
def accept_task(c):
    uid = c.from_user.id
    
    tid = int(c.data.split("_")[1])

    row = db_query("SELECT done, title, reward, creator, require_channel, slots FROM tasks WHERE id=?", (tid,), fetchone=True)
    if not row:
        bot.answer_callback_query(c.id, "❌ Вазифа топилмади")
        return
    done, title, reward, creator, req, slots = row
    if done:
        bot.answer_callback_query(c.id, "❌ Вазифа аллақачон бажарилган")
        return

    already = db_query("SELECT 1 FROM task_assignees WHERE task_id=? AND user_id=?", (tid, uid), fetchone=True)
    if already:
        bot.answer_callback_query(c.id, "❌ Сиз аллақачон бу вазифани қабул қилгансиз")
        return

    current = db_query("SELECT COUNT(*) FROM task_assignees WHERE task_id=?", (tid,), fetchone=True)[0] or 0
    if current >= (slots or 1):
        bot.answer_callback_query(c.id, "❌ Бошқа иштирокчилар аллақачон тўлдирилган")
        return

    db_query("INSERT INTO task_assignees (task_id, user_id, completed) VALUES (?,?,?)", (tid, uid, 0), commit=True)
    bot.answer_callback_query(c.id, "✅ Вазифани қабул қилдингиз")
    bot.send_message(uid, f"✅ Сиз '{title}' вазифасини қабул қилдингиз. Мукофот: {reward} танга")

    try:
        bot.send_message(creator, f"👤 Фойдаланувчи {c.from_user.id} вазифани қабул қилди (id: {tid})")
    except Exception:
        pass

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅ Мен бажардим", callback_data=f"checksub_{tid}"))
    if req:
        bot.send_message(uid, f"🔔 Ушбу вазифа учун {req} каналига обуна бўлиш талаб қилинади. Обуна бўлгач, қуйидаги тугмани босинг.", reply_markup=kb)
    else:
        bot.send_message(uid, "✅ Вазифани бажарганингизни тасдиқлаш учун қуйидаги тугмани босинг:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("remove_sponsor_"))
def remove_sponsor(c):
    if not is_admin(c.from_user.id):
        bot.answer_callback_query(c.id, "❌ Рухсат йўқ")
        return
    enc = c.data.split("remove_sponsor_")[1]
    ch = _decode_channel(enc)
    db_query("DELETE FROM sponsors WHERE channel=?", (ch,), commit=True)
    bot.answer_callback_query(c.id, f"✅ Спонсор {ch} ўчирилди")
    try:
        bot.delete_message(c.message.chat.id, c.message.message_id)
    except Exception:
        pass

@bot.callback_query_handler(func=lambda c: c.data == "sponsor_edit")
def sponsor_edit(c):
    if not is_admin(c.from_user.id):
        bot.answer_callback_query(c.id, "❌ Рухсат йўқ")
        return
    admin_state[c.from_user.id] = {"step": "sponsor"}
    bot.answer_callback_query(c.id, "✍️ Илтимос янги @канал ёки t.me/ҳавола юборинг")
    try:
        bot.delete_message(c.message.chat.id, c.message.message_id)
    except Exception:
        pass

@bot.callback_query_handler(func=lambda c: c.data == "sponsor_cancel")
def sponsor_cancel(c):
    if not is_admin(c.from_user.id):
        bot.answer_callback_query(c.id, "❌ Рухсат йўқ")
        return
    admin_state.pop(c.from_user.id, None)
    bot.answer_callback_query(c.id, "❌ Спонсор қўшиш бекор қилинди")
    try:
        bot.delete_message(c.message.chat.id, c.message.message_id)
    except Exception:
        pass

@bot.callback_query_handler(func=lambda c: c.data == "sponsor_confirm")
def sponsor_confirm(c):
    if not is_admin(c.from_user.id):
        bot.answer_callback_query(c.id, "❌ Рухсат йўқ")
        return
    s = admin_state.get(c.from_user.id)
    if not s or s.get("step") != "sponsor_confirm":
        bot.answer_callback_query(c.id, "❌ Тасдиқлаш учун спонсор йўқ")
        return
    ch = s.get("pending")
    if not ch:
        bot.answer_callback_query(c.id, "❌ Номаълум канал")
        return

    existing = db_query("SELECT 1 FROM sponsors WHERE channel=?", (ch,), fetchone=True)
    if existing:
        admin_state.pop(c.from_user.id, None)
        bot.answer_callback_query(c.id, "ℹ️ Бу спонсор аллақачон мавжуд")
        try:
            bot.delete_message(c.message.chat.id, c.message.message_id)
        except Exception:
            pass
        return

    db_query("INSERT INTO sponsors (channel) VALUES (?)", (ch,), commit=True)
    admin_state.pop(c.from_user.id, None)
    bot.answer_callback_query(c.id, f"✅ Спонсор қўшилди: {ch}")
    try:
        bot.delete_message(c.message.chat.id, c.message.message_id)
    except Exception:
        pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("checksub_"))
def check_subscription(c):
    uid = c.from_user.id
    tid = int(c.data.split("_")[1])

    row = db_query("SELECT done, title, reward, creator, require_channel, slots FROM tasks WHERE id=?", (tid,), fetchone=True)
    if not row:
        bot.answer_callback_query(c.id, "❌ Вазифа топилмади")
        return
    done, title, reward, creator, req, slots = row
    assigned = db_query("SELECT completed FROM task_assignees WHERE task_id=? AND user_id= ?", (tid, uid), fetchone=True)
    if not assigned:
        bot.answer_callback_query(c.id, "❌ Сиз ушбу вазифани қабул қилмагансиз")
        return
    if done:
        bot.answer_callback_query(c.id, "ℹ️ Вазифа аллақачон бажарилган")
        return
    if assigned[0] == 1:
        bot.answer_callback_query(c.id, "ℹ️ Сиз ушбу вазифани аллақачон бажардингиз")
        return

    def normalize_channel(text):
        t = text.strip()
        if t.startswith("https://") or t.startswith("http://"):
            try:
                return t.rstrip('/').split('/')[-1]
            except Exception:
                return t
        if t.startswith("t.me/"):
            return t.split('/',1)[1]
        return t  

    if not req:
        db_query("UPDATE task_assignees SET completed=1 WHERE task_id=? AND user_id=?", (tid, uid), commit=True)
        db_query("UPDATE users SET coins = coins + ? WHERE user_id=?", (reward, uid), commit=True)
        bot.answer_callback_query(c.id, "✅ Вазифа бажарилди, мукофот топширилди")
        bot.send_message(uid, f"✅ Сиз '{title}' вазифасини бажардингиз. Мукофот: {reward} танга")
        try:
            bot.send_message(creator, f"✅ Фойдаланувчи {uid} вазифани бажарди (id: {tid})")
        except Exception:
            pass
        completed_count = db_query("SELECT COUNT(*) FROM task_assignees WHERE task_id=? AND completed=1", (tid,), fetchone=True)[0] or 0
        if completed_count >= (slots or 1):
            db_query("UPDATE tasks SET done=1 WHERE id=?", (tid,), commit=True)
        return

    chan = normalize_channel(req)
    if not chan.startswith("@") and not chan.startswith("-"):
        target = '@' + chan
    else:
        target = chan

    try:
        member = bot.get_chat_member(target, uid)
        if member.status not in ["left", "kicked"]:
            db_query("UPDATE task_assignees SET completed=1 WHERE task_id=? AND user_id=?", (tid, uid), commit=True)
            db_query("UPDATE users SET coins = coins + ? WHERE user_id=?", (reward, uid), commit=True)
            bot.answer_callback_query(c.id, "✅ Обуна текширилди ва вазифа бажарилди")
            bot.send_message(uid, f"✅ Сиз '{title}' вазифасини бажардингиз ва {reward} танга олдингиз")
            try:
                bot.send_message(creator, f"✅ Фойдаланувчи {uid} вазифани бажарди (id: {tid})")
            except Exception:
                pass
            completed_count = db_query("SELECT COUNT(*) FROM task_assignees WHERE task_id=? AND completed=1", (tid,), fetchone=True)[0] or 0
            if completed_count >= (slots or 1):
                db_query("UPDATE tasks SET done=1 WHERE id=?", (tid,), commit=True)
        else:
            bot.answer_callback_query(c.id, "❌ Сиз каналга обуна бўлмагансиз")
    except Exception:
        bot.answer_callback_query(c.id, "❌ Канални текширишда хатолик. Илтимос, админ билан боғланинг")

@bot.message_handler(commands=["check_url"])
def cmd_check_url(m):
    args = m.text.split(maxsplit=1)
    if len(args) < 2:
        bot.send_message(m.chat.id, "ℹ️ Илтимос, URL киритинг: /check_url https://example.com/image.jpg")
        return
    url = args[1].strip()
    bot.send_message(m.chat.id, f"🔍 Текширилмокда: {url}")
    ok = is_image_url(url)
    if ok:
        bot.send_message(m.chat.id, f"✅ Бу URL тасвирга ўхшайди: {url}")
    else:
        try:
            r = requests.head(url, allow_redirects=True, timeout=5)
            ct = r.headers.get('content-type', '(none)')
            status = r.status_code
            bot.send_message(m.chat.id, f"❌ Бу URL тасвир эмас ёки ишламаёпти. status={status}, content-type={ct}")
        except Exception as e:
            bot.send_message(m.chat.id, f"❌ Текширишда хатолик: {e}")

@bot.message_handler(commands=["check_case_images"])
def cmd_check_case_images(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ Рухсат йўқ")
        return
    bot.send_message(m.chat.id, "🔍 Ҳаммасини текширяпман, кутинг...")
    broken = []
    ok = []
    for case in CASES:
        url = case.get('photo', '')
        if is_image_url(url):
            ok.append((case['id'], case['name']))
        else:
            broken.append((case['id'], case['name'], url))
    txt = f"✅ Яхши: {len(ok)}\n❌ Муаммоли: {len(broken)}\n"
    if broken:
        txt += "\nМуаммоли URL\n"
        for b in broken:
            txt += f"- id {b[0]} {b[1]}: {b[2]}\n"
    bot.send_message(m.chat.id, txt)

@bot.message_handler(func=lambda m: getattr(m, 'text', '').strip() == "💸 Танга бериш")
def give_coins_start(m):
    if not is_admin(m.from_user.id):
        return
    admin_state[m.from_user.id] = {"step": "give_username"}
    bot.send_message(m.chat.id, "✍️ Қабул қилувчининг @username ёки user_id сини юборинг")

@bot.message_handler(func=lambda m: m.from_user.id in admin_state and admin_state[m.from_user.id]["step"] == "give_username")
def give_coins_username(m):
    if not is_admin(m.from_user.id):
        admin_state.pop(m.from_user.id, None)
        return
    text = m.text.strip()
    try:
        if text.isdigit():
            target_id = int(text)
        else:
            if not text.startswith("@"):
                text = "@" + text
            target = bot.get_chat(text)
            target_id = target.id
    except Exception:
        bot.send_message(m.chat.id, "❌ Фойдаланувчи топилмади. Тўғри @username киритилганига ёки фойдаланувчи ботни ишга туширганига ишонч ҳосил қилинг.")
        return

    admin_state[m.from_user.id] = {"step": "give_amount", "target": target_id}
    bot.send_message(m.chat.id, "✍️ Неча танга берилсин? (сон)")

@bot.message_handler(func=lambda m: m.from_user.id in admin_state and admin_state[m.from_user.id]["step"] == "give_amount")
def give_coins_amount(m):
    if not is_admin(m.from_user.id):
        admin_state.pop(m.from_user.id, None)
        return
    s = admin_state[m.from_user.id]
    try:
        amount = int(m.text)
    except Exception:
        bot.send_message(m.chat.id, "❌ Бутун сон киритинг")
        return

    if amount <= 0:
        bot.send_message(m.chat.id, "❌ Сумма мусбат бўлиши керак")
        return

    target = s["target"]

    if not db_query("SELECT 1 FROM users WHERE user_id=?", (target,), fetchone=True):
        db_query("INSERT INTO users (user_id, coins) VALUES (?,?)", (target, amount), commit=True)
    else:
        db_query("UPDATE users SET coins = coins + ? WHERE user_id=?", (amount, target), commit=True)

    bot.send_message(m.chat.id, f"✅ Фойдаланувчи {target} га {amount} танга берилди")
    try:
        bot.send_message(target, f"💸 Админ сизга {amount} танга берди")
    except Exception:
        pass

    del admin_state[m.from_user.id]

@bot.message_handler(func=lambda m: getattr(m, 'text', '').strip() == "📊 Статистика")
def stats(m):
    users = db_query("SELECT COUNT(*) FROM users", fetchone=True)[0]
    promos = db_query("SELECT COUNT(*) FROM promocodes", fetchone=True)[0]

    bot.send_message(
        m.chat.id,
        f"📊 Статистика:\n\n"
        f"👤 Фойдаланувчилар: {users}\n"
        f"🎫 Промокодлар: {promos}"
    )

@bot.message_handler(commands=["promos"])
def admin_promos(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ Рухсат йўқ")
        return

    rows = db_query("SELECT case_id, COUNT(*) FROM promocodes GROUP BY case_id", fetchall=True)
    if not rows:
        bot.send_message(m.chat.id, "ℹ️ Ҳозирча промокодлар мавжуд эмас")
        return

    text_lines = []
    for case_id, cnt in rows:
        sample = db_query("SELECT code FROM promocodes WHERE case_id=? LIMIT 5", (case_id,), fetchall=True)
        sample_codes = ", ".join([s[0] for s in sample]) if sample else "(none)"
        text_lines.append(f"Кейс {case_id}: {cnt} та — намұна: {sample_codes}")

    bot.send_message(m.chat.id, "📦 Промокодлар:\n" + "\n".join(text_lines))

# Ботни каналга қўшиш учун буюруқ
@bot.message_handler(commands=["addbot"])
def cmd_addbot(m):
    if not is_admin(m.from_user.id):
        return
    
    bot_username = bot.get_me().username
    bot_link = f"https://t.me/{bot_username}"
    
    message = (
        f"🤖 Ботни каналга қўшиш бўйича кўрсатма:\n\n"
        f"1. Канал созламаларига киринг\n"
        f"2. 'Администраторлар' ни танланг\n"
        f"3. 'Администратор қўшиш' ни босинг\n"
        f"4. @{bot_username} ни киритинг ёки ҳаволага ўтинг: {bot_link}\n"
        f"5. Ботга қуйидаги ҳуқуқларни беринг:\n"
        f"   • ✅ Аъзоларни кўриш\n"
        f"   • ❌ Қолган ҳуқуқларни ўчириб қўйинг\n"
        f"6. 'Сақлаш' ни босинг\n\n"
        f"⚠️ Муҳим: обуналарни текшириш учун бот администратор бўлиши керак!"
    )
    
    bot.send_message(m.chat.id, message)

bot.infinity_polling(threaded=False, skip_pending=True)