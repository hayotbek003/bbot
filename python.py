import telebot
from telebot import types
import sqlite3
import csv
import base64
import logging
import time
import os
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')

last_prompt = {}

# Rasmlar uchun papka
PHOTOS_FOLDER = "case_photos"
os.makedirs(PHOTOS_FOLDER, exist_ok=True)

TOKEN = "8534666186:AAEGAbCnBiGV5CDmByKsyEL3frWoFLZ_n4I"
ADMINS = [5911280005, 7388508151]

bot = telebot.TeleBot(TOKEN)

CASES = [
    {
        "id": 1,
        "name": "Bullpass",
        "price": 4,
        "category": 4,
        "photo": "bullpass.jpg"
    },
    {
        "id": 2,
        "name": "Jim Ustoz",
        "price": 7,
        "category": 7,
        "photo": "jim_ustoz.jpg"
    },
    {
        "id": 3,
        "name": "Ruhiy shoʻrva",
        "price": 10,
        "category": 10,
        "photo": "ruhiy_shorva.jpg"
    },
    {
        "id": 4,
        "name": "Geysha sirlari",
        "price": 15,
        "category": 15,
        "photo": "geysha.jpg"
    },
    {
        "id": 5,
        "name": "JOJO",
        "price": 23,
        "category": 23,
        "photo": "jojo.jpg"
    },
    {
        "id": 6,
        "name": "Torii darvozasi",
        "price": 35,
        "category": 35,
        "photo": "torii.jpg"
    }
]

def get_photo_path(photo_filename):
    """Rasm faylining toʻliq yoʻlini olish"""
    return os.path.join(PHOTOS_FOLDER, photo_filename)

def send_photo_from_file(chat_id, photo_filename, caption=None, **kwargs):
    """Fayldan rasm yuborish"""
    photo_path = get_photo_path(photo_filename)

    if not os.path.exists(photo_path):
        logging.error(f"Rasm topilmadi: {photo_path}")
        if caption:
            bot.send_message(chat_id, caption, **kwargs)
        return False

    try:
        with open(photo_path, 'rb') as photo:
            bot.send_photo(chat_id, photo, caption=caption, **kwargs)
        return True
    except Exception as e:
        logging.error(f"Rasm {photo_filename} ni yuborishda xatolik: {e}")
        if caption:
            bot.send_message(chat_id, caption, **kwargs)
        return False

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
    """CSV faylini yaratish (faqat zaxira uchun)"""
    try:
        rows = db_query("SELECT id, case_id, code FROM promocodes", fetchall=True)
        with open(PROMO_FILE, "w", newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(["id", "case_id", "code"])
            for r in rows:
                w.writerow(r)
    except Exception:
        pass

def add_promocode(case_id, code):
    """Promokod qo'shish"""
    db_query(
        "INSERT INTO promocodes (case_id, code) VALUES (?,?)",
        (case_id, code),
        commit=True
    )

def remove_promocode_by_id(pid):
    """Promokodni ID bo'yicha o'chirish"""
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
    """Barcha kanallarga obuna bo'lganligini tekshirish"""
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
                    logging.info(f"Foydalanuvchi {uid} {target} kanalida emas")
                    return False

            except Exception as e:
                logging.error(f"{target} kanali uchun a'zolikni tekshirishda xatolik: {e}")
                continue

        except Exception as e:
            logging.error(f"{ch} kanalini qayta ishlashda xatolik: {e}")
            continue

    return True

def require_subscription(func):
    """Funksiyani bajarishdan oldin obunani tekshirish uchun dekorator"""
    def wrapper(message):
        uid = message.from_user.id
        if not check_sub(uid):
            prompt_subscription(uid)
            return
        return func(message)
    return wrapper

def require_subscription_callback(func):
    """Callback funksiyasini bajarishdan oldin obunani tekshirish uchun dekorator"""
    def wrapper(call):
        uid = call.from_user.id
        if not check_sub(uid):
            bot.answer_callback_query(call.id, "❗ Avval barcha kanallarga obuna bo'ling", show_alert=True)
            prompt_subscription(uid)
            return
        return func(call)
    return wrapper

def prompt_subscription(uid, text=None):
    """Foydalanuvchiga standart obuna taklifini yuborish"""
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

    kb.add(types.InlineKeyboardButton("✅ Men obuna bo'ldim", callback_data="check"))

    msg = text or "❗ Avval obuna bo'ling: iltimos, barcha sponsor kanallariga obuna bo'ling va keyin tasdiqlang"
    try:
        bot.send_message(uid, msg, reply_markup=kb)
    except Exception as e:
        logging.exception("Obuna taklifini yuborishda xatolik")

def menu(uid):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💰 Tanga ishlash", "🛒 Do'kon")
    kb.add("💳 Balans")
    kb.add("📝 Vazifalar")
    kb.add("⭐ Sapyor", "💥 Crash")
    if is_admin(uid):
        kb.add("👑 Admin panel")
    bot.send_message(uid, "🏠 Asosiy menyu", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "check")
def recheck(c):
    uid = c.from_user.id
    if check_sub(uid):
        bot.answer_callback_query(c.id, "✅ Rahmat! Endi botdan foydalanishingiz mumkin.")
        try:
            bot.delete_message(c.message.chat.id, c.message.message_id)
        except:
            pass
        menu(uid)
    else:
        bot.answer_callback_query(
            c.id,
            "❌ Siz hali barcha kanallarga obuna bo'lmagansiz!",
            show_alert=True
        )

@bot.message_handler(commands=["start", "menu"])
def cmd_start(m):
    admin_state.pop(m.from_user.id, None)

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
        bot.send_message(m.chat.id, "✅ Jarayon bekor qilindi")
        menu(m.from_user.id)
    else:
        bot.send_message(m.chat.id, "ℹ️ Faol jarayonlar topilmadi")

@bot.message_handler(func=lambda m: getattr(m, 'text', '').strip() == "💰 Tanga ishlash")
@require_subscription
def earn(m):
    link = f"https://t.me/{bot.get_me().username}?start={m.from_user.id}"
    bot.send_message(m.chat.id, f"🔗 Do'stlaringiz bilan havolani ulashing!\n\n{link}\n\nDo'stlaringiz bilan ulashing va promo kodlarni birga yutib oling🤩")

@bot.message_handler(func=lambda m: getattr(m, 'text', '').strip() == "💳 Balans")
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
        f"💰 Balans: {coins} tanga\n"
        f"📦 Jami tanga: {total_coins} tanga\n"
        f"🟢 Faol foydalanuvchilar (tanga>0): {active_users}\n"
        f"👥 Do'stlaringiz soni: {friends}"
    )

    send_photo_from_file(
        m.chat.id,
        "balance.jpg",
        caption=caption
    )

@bot.message_handler(func=lambda m: getattr(m, 'text', '').strip() == "🆘 Qo'llab-quvvatlash")
@require_subscription
def support(m):
    bot.send_message(m.chat.id, "🆘 Savollar uchun yozing: @Camonim")

@bot.message_handler(func=lambda m: any(word in (m.text or '').lower() for word in ['do\'kon', 'shop', '🛒']))
@require_subscription
def shop(m):
    uid = m.from_user.id

    kb = types.InlineKeyboardMarkup()
    for p in [4, 7, 10, 15, 23, 35]:
        kb.add(types.InlineKeyboardButton(f"{p} tanga", callback_data=f"cat_{p}"))

    send_photo_from_file(
        m.chat.id,
        "shop_categories.jpg",
        caption="🎁 Keys kategoriyalari:",
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

    kb.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_cats"))

    try:
        bot.edit_message_text(
            "📦 Keysni tanlang:",
            c.message.chat.id,
            c.message.message_id,
            reply_markup=kb
        )
    except Exception:
        try:
            bot.edit_message_caption(
                "📦 Keysni tanlang:",
                c.message.chat.id,
                c.message.message_id,
                reply_markup=kb
            )
        except Exception:
            bot.send_message(
                c.message.chat.id,
                "📦 Keysni tanlang:",
                reply_markup=kb
            )

@bot.callback_query_handler(func=lambda c: c.data == "back_cats")
@require_subscription_callback
def back_to_cats(c):
    kb = types.InlineKeyboardMarkup()
    for p in [4, 7, 10, 15, 23, 35]:
        kb.add(types.InlineKeyboardButton(f"{p} tanga", callback_data=f"cat_{p}"))

    try:
        bot.edit_message_text(
            "🎁 Keys kategoriyalari:",
            c.message.chat.id,
            c.message.message_id,
            reply_markup=kb
        )
    except Exception:
        try:
            bot.edit_message_caption(
                "🎁 Keys kategoriyalari:",
                c.message.chat.id,
                c.message.message_id,
                reply_markup=kb
            )
        except Exception:
            send_photo_from_file(
                c.message.chat.id,
                "shop_categories.jpg",
                caption="🎁 Keys kategoriyalari:",
                reply_markup=kb
            )

@bot.callback_query_handler(func=lambda c: c.data.startswith("case_"))
@require_subscription_callback
def buy_case(c):
    uid = c.from_user.id

    cid = int(c.data.split("_")[1])

    case = next((x for x in CASES if x["id"] == cid), None)
    if not case:
        bot.answer_callback_query(c.id, "❌ Keys topilmadi")
        return

    res = db_query(
        "SELECT coins FROM users WHERE user_id=?",
        (uid,),
        fetchone=True
    )
    coins = res[0] if res else 0

    if coins < case["price"]:
        bot.answer_callback_query(c.id, "❌ Yetarli tanga yo'q")
        return

    promo = db_query(
        "SELECT id, code FROM promocodes WHERE case_id=? LIMIT 1",
        (cid,),
        fetchone=True
    )

    if not promo:
        bot.answer_callback_query(c.id, "❌ Promokodlar tugadi")
        return

    db_query(
        "UPDATE users SET coins = coins - ? WHERE user_id=?",
        (case["price"], uid),
        commit=True
    )

    remove_promocode_by_id(promo[0])

    photo_filename = case.get("photo", "")
    promo_code = promo[1]

    send_photo_from_file(
        uid,
        photo_filename,
        f"🎁 {case['name']}\n🎫 Promokod: {promo_code}",
        parse_mode="Markdown"
    )

    bot.answer_callback_query(c.id, "✅ Keys sotib olindi!")

@bot.message_handler(func=lambda m: getattr(m, 'text', '').strip() == "👑 Admin panel")
def admin_panel(m):
    if not is_admin(m.from_user.id):
        return

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Promokod qo'shish")
    kb.add("💸 Tanga berish")
    kb.add("➕ Vazifa yaratish")
    kb.add("📢 Sponsor qo'shish")
    kb.add("📊 Statistika")
    kb.add("🖼 Rasm qo'shish")
    kb.add("⬅️ Orqaga")
    bot.send_message(m.chat.id, "👑 Admin panel", reply_markup=kb)

@bot.message_handler(func=lambda m: getattr(m, 'text', '').strip() == "⬅️ Orqaga")
def back(m):
    menu(m.from_user.id)

@bot.message_handler(func=lambda m: getattr(m, 'text', '').strip() == "➕ Promokod qo'shish")
def add_promo_start(m):
    if not is_admin(m.from_user.id):
        return

    kb = types.InlineKeyboardMarkup()
    for case in CASES:
        kb.add(types.InlineKeyboardButton(
            case["name"],
            callback_data=f"promo_{case['id']}"
        ))

    bot.send_message(m.chat.id, "📦 Keysni tanlang:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("promo_"))
def promo_case(c):
    admin_state[c.from_user.id] = {
        "step": "promo_count",
        "case_id": int(c.data.split("_")[1])
    }
    bot.send_message(c.message.chat.id, "🎫 Nechta promokod qo'shmoqchisiz?")

@bot.message_handler(func=lambda m: m.from_user.id in admin_state and admin_state[m.from_user.id]["step"] == "promo_count")
def promo_count(m):
    if not is_admin(m.from_user.id):
        admin_state.pop(m.from_user.id, None)
        return
    try:
        admin_state[m.from_user.id]["left"] = int(m.text)
    except ValueError:
        bot.send_message(m.chat.id, "❌ Iltimos, son kiriting")
        return
    admin_state[m.from_user.id]["step"] = "promo_add"
    bot.send_message(m.chat.id, "✍️ Promokodlarni bitta-bitta yuboring")

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
        bot.send_message(m.chat.id, "✅ Promokodlar qo'shildi")

@bot.message_handler(func=lambda m: getattr(m, 'text', '').strip() == "📢 Sponsor qo'shish")
def add_sponsor(m):
    if not is_admin(m.from_user.id):
        return
    admin_state[m.from_user.id] = {"step": "sponsor"}
    bot.send_message(m.chat.id, "📢 @kanal yoki havola yuboring (masalan: @channel_name yoki https://t.me/channel_name)")

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
        logging.info(f"Kanal ma'lumoti: {chat_info.title} ({chat_info.id})")

        try:
            bot_member = bot.get_chat_member(ch, bot.get_me().id)
            if bot_member.status not in ['administrator', 'creator']:
                bot.send_message(
                    m.chat.id,
                    f"⚠️ Bot {ch} kanalida administrator emas\n\n"
                    f"Obunalarni tekshirish uchun bot kanalda administrator bo'lishi kerak.\n"
                    f"Botni {ch} kanaliga 'A'zolarni ko'rish' huquqi bilan administrator qilib qo'ying."
                )
                return
        except Exception as e:
            if "chat not found" not in str(e).lower() and "bot is not a member" not in str(e).lower():
                logging.warning(f"{ch} uchun bot admin statusini tekshirib bo'lmadi: {e}")

    except Exception as e:
        error_msg = str(e).lower()
        if "chat not found" in error_msg:
            bot.send_message(
                m.chat.id,
                f"❌ {ch} kanali topilmadi yoki shaxsiy.\n\n"
                f"Shaxsiy kanallar uchun:\n"
                f"1. Botni kanalga administrator qilib qo'ying\n"
                f"2. Botga 'A'zolarni ko'rish' huquqini bering\n"
                f"3. Shundan so'ng kanalni qayta qo'shib ko'ring"
            )
        elif "bot is not a member" in error_msg:
            bot.send_message(
                m.chat.id,
                f"❌ Bot {ch} kanaliga qo'shilmagan\n\n"
                f"Iltimos:\n"
                f"1. Botni @{bot.get_me().username} kanaliga qo'shing\n"
                f"2. Botni administrator qiling\n"
                f"3. 'A'zolarni ko'rish' huquqini bering\n"
                f"4. Qayta urinib ko'ring"
            )
        else:
            bot.send_message(
                m.chat.id,
                f"⚠️ {ch} kanalini tekshirishda xatolik: {e}\n"
                f"Iltimos, kanal mavjudligiga va bot unga kirish huquqiga ega ekanligiga ishonch hosil qiling."
            )
        return

    existing = db_query("SELECT 1 FROM sponsors WHERE channel=?", (ch,), fetchone=True)
    if existing:
        del admin_state[m.from_user.id]
        bot.send_message(m.chat.id, "ℹ️ Bu sponsor allaqachon mavjud")
        return

    admin_state[m.from_user.id] = {
        "step": "sponsor_confirm",
        "pending": ch
    }

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔁 O'zgartirish", callback_data="sponsor_edit"))
    kb.add(types.InlineKeyboardButton("✅ Tayyor", callback_data="sponsor_confirm"))
    kb.add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data="sponsor_cancel"))

    try:
        bot.send_message(m.chat.id, f"📢 Topildi: {ch}\nIltimos tasdiqlang yoki o'zgartiring:", reply_markup=kb)
    except Exception as e:
        logging.exception("Sponsor tasdiqlash tugmalarini yuborishda xatolik: %s", e)
        bot.send_message(m.chat.id, f"📢 Topildi: {ch}\nIltimos tasdiqlang yoki o'zgartiring:\n(Inline tugmalar yuborilmadi — iltimos, /sponsors bilan tekshiring yoki qayta yuboring)")

@bot.message_handler(func=lambda m: getattr(m, 'text', '').strip() == "➕ Vazifa yaratish")
def create_task_start(m):
    if not is_admin(m.from_user.id):
        return
    admin_state[m.from_user.id] = {"step": "task_title"}
    bot.send_message(m.chat.id, "✍️ Vazifa sarlavhasini kiriting")

@bot.message_handler(func=lambda m: m.from_user.id in admin_state and admin_state[m.from_user.id]["step"] == "task_title")
def create_task_title(m):
    if not is_admin(m.from_user.id):
        admin_state.pop(m.from_user.id, None)
        return
    admin_state[m.from_user.id] = {"step": "task_desc", "title": m.text}
    bot.send_message(m.chat.id, "✍️ Vazifa matnini kiriting")

@bot.message_handler(func=lambda m: m.from_user.id in admin_state and admin_state[m.from_user.id]["step"] == "task_desc")
def create_task_desc(m):
    if not is_admin(m.from_user.id):
        admin_state.pop(m.from_user.id, None)
        return
    s = admin_state[m.from_user.id]
    s["desc"] = m.text
    s["step"] = "task_reward"
    bot.send_message(m.chat.id, "✍️ Necha tanga berasiz? (son)")

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
        bot.send_message(m.chat.id, "❌ Iltimos, 1 yoki undan katta butun son kiriting")
        return
    s["slots"] = slots
    s["step"] = "task_require"
    bot.send_message(m.chat.id, "🔗 Agar vazifa uchun kanalga obuna bo'lish talab qilinsa, kanalni (@kanal yoki t.me/havola) yuboring; agar talab yo'q bo'lsa 'yo'q' yozing")

@bot.message_handler(func=lambda m: m.from_user.id in admin_state and admin_state[m.from_user.id]["step"] == "task_reward")
def create_task_reward(m):
    if not is_admin(m.from_user.id):
        admin_state.pop(m.from_user.id, None)
        return
    s = admin_state[m.from_user.id]
    try:
        reward = int(m.text)
    except Exception:
        bot.send_message(m.chat.id, "❌ Butun son kiriting")
        return

    s["reward"] = reward
    s["step"] = "task_slots"
    bot.send_message(m.chat.id, "🔢 Nechta ishtirokchi ruxsat etiladi? (butun son, standart 1)")

@bot.message_handler(func=lambda m: m.from_user.id in admin_state and admin_state[m.from_user.id]["step"] == "task_require")
def create_task_require(m):
    if not is_admin(m.from_user.id):
        admin_state.pop(m.from_user.id, None)
        return
    s = admin_state[m.from_user.id]
    channel = m.text.strip()
    if channel.lower() == "yo'q" or channel == "":
        channel = None

    db_query(
        "INSERT INTO tasks (title, description, reward, creator, require_channel, slots) VALUES (?,?,?,?,?,?)",
        (s["title"], s["desc"], s["reward"], m.from_user.id, channel, s.get("slots", 1)),
        commit=True
    )

    tid = db_query("SELECT last_insert_rowid()", fetchone=True)[0]
    bot.send_message(m.chat.id, f"✅ Vazifa yaratildi (id: {tid})")
    del admin_state[m.from_user.id]

@bot.message_handler(func=lambda m: getattr(m, 'text', '').strip() == "🖼 Rasm qo'shish")
def add_photo_menu(m):
    if not is_admin(m.from_user.id):
        return

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Keys rasm qo'shish")
    kb.add("➕ Balans rasm qo'shish")
    kb.add("➕ Do'kon rasm qo'shish")
    kb.add("⬅️ Orqaga")

    bot.send_message(m.chat.id, "🖼 Rasm qo'shish menyusi:", reply_markup=kb)

@bot.message_handler(func=lambda m: getattr(m, 'text', '').strip() == "➕ Keys rasm qo'shish")
def add_case_photo_start(m):
    if not is_admin(m.from_user.id):
        return

    kb = types.InlineKeyboardMarkup()
    for case in CASES:
        kb.add(types.InlineKeyboardButton(
            case["name"],
            callback_data=f"addphoto_{case['id']}"
        ))

    bot.send_message(m.chat.id, "📦 Keysni tanlang:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("addphoto_"))
def add_case_photo(c):
    admin_state[c.from_user.id] = {
        "step": "add_photo",
        "case_id": int(c.data.split("_")[1])
    }

    case = next((x for x in CASES if x["id"] == int(c.data.split("_")[1])), None)
    if case:
        bot.send_message(c.message.chat.id,
            f"📸 Keys: {case['name']}\n"
            f"Fayl nomi: {case['photo']}\n\n"
            f"Iltimos, rasmini yuboring (yoki hujjat sifatida).")
    else:
        bot.send_message(c.message.chat.id, "Rasmini yuboring:")

@bot.message_handler(content_types=['photo', 'document'])
def handle_photo(m):
    if m.from_user.id not in admin_state or admin_state[m.from_user.id].get("step") != "add_photo":
        return

    s = admin_state[m.from_user.id]
    case_id = s.get("case_id")

    if not case_id:
        if s.get("photo_type") == "balance":
            filename = "balance.jpg"
        elif s.get("photo_type") == "shop":
            filename = "shop_categories.jpg"
        else:
            return
    else:
        case = next((x for x in CASES if x["id"] == case_id), None)
        if not case:
            return
        filename = case["photo"]

    try:
        if m.photo:
            file_info = bot.get_file(m.photo[-1].file_id)
        elif m.document:
            file_info = bot.get_file(m.document.file_id)
        else:
            bot.send_message(m.chat.id, "❌ Iltimos, rasm yoki hujjat yuboring.")
            return

        downloaded_file = bot.download_file(file_info.file_path)

        file_path = os.path.join(PHOTOS_FOLDER, filename)
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        bot.send_message(m.chat.id, f"✅ Rasm saqlandi: {filename}")

        del admin_state[m.from_user.id]

    except Exception as e:
        logging.error(f"Rasm saqlashda xatolik: {e}")
        bot.send_message(m.chat.id, f"❌ Xatolik: {e}")

@bot.message_handler(func=lambda m: getattr(m, 'text', '').strip() == "➕ Balans rasm qo'shish")
def add_balance_photo(m):
    if not is_admin(m.from_user.id):
        return

    admin_state[m.from_user.id] = {
        "step": "add_photo",
        "photo_type": "balance"
    }

    bot.send_message(m.chat.id, "💰 Balans uchun rasmini yuboring (yoki hujjat sifatida).\nFayl nomi: balance.jpg")

@bot.message_handler(func=lambda m: getattr(m, 'text', '').strip() == "➕ Do'kon rasm qo'shish")
def add_shop_photo(m):
    if not is_admin(m.from_user.id):
        return

    admin_state[m.from_user.id] = {
        "step": "add_photo",
        "photo_type": "shop"
    }

    bot.send_message(m.chat.id, "🛒 Do'kon kategoriyalari uchun rasmini yuboring (yoki hujjat sifatida).\nFayl nomi: shop_categories.jpg")

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
        bot.send_message(m.chat.id, "ℹ️ Hozircha sponsor kanallari ro'yxati bo'sh")
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
            kb_row.append(types.InlineKeyboardButton("🗑 O'chirish", callback_data=f"remove_sponsor_{enc}"))
        kb.row(*kb_row)

    bot.send_message(m.chat.id, "📢 Sponsor kanallari:", reply_markup=kb)

@bot.message_handler(func=lambda m: getattr(m, 'text', '').strip() == "📝 Vazifalar")
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
        kb.add(types.InlineKeyboardButton("Qabul qilaman", callback_data=f"accept_{tid}"))
        text = f"📝 {title}\n{desc}\n💰 Mukofot: {reward} tanga\n🔢 Qolgan o'rinlar: {remaining}"
        if req:
            text += f"\n🔒 Obuna talab qilinadi: {req}"
        bot.send_message(m.chat.id, text, reply_markup=kb)
    if out_count == 0:
        bot.send_message(m.chat.id, "ℹ️ Hozircha mavjud vazifalar yo'q")

@bot.callback_query_handler(func=lambda c: c.data.startswith("accept_"))
@require_subscription_callback
def accept_task(c):
    uid = c.from_user.id

    tid = int(c.data.split("_")[1])

    row = db_query("SELECT done, title, reward, creator, require_channel, slots FROM tasks WHERE id=?", (tid,), fetchone=True)
    if not row:
        bot.answer_callback_query(c.id, "❌ Vazifa topilmadi")
        return
    done, title, reward, creator, req, slots = row
    if done:
        bot.answer_callback_query(c.id, "❌ Vazifa allaqachon bajarilgan")
        return

    already = db_query("SELECT 1 FROM task_assignees WHERE task_id=? AND user_id=?", (tid, uid), fetchone=True)
    if already:
        bot.answer_callback_query(c.id, "❌ Siz allaqachon bu vazifani qabul qilgansiz")
        return

    current = db_query("SELECT COUNT(*) FROM task_assignees WHERE task_id=?", (tid,), fetchone=True)[0] or 0
    if current >= (slots or 1):
        bot.answer_callback_query(c.id, "❌ Boshqa ishtirokchilar allaqachon to'ldirilgan")
        return

    db_query("INSERT INTO task_assignees (task_id, user_id, completed) VALUES (?,?,?)", (tid, uid, 0), commit=True)
    bot.answer_callback_query(c.id, "✅ Vazifani qabul qildingiz")
    bot.send_message(uid, f"✅ Siz '{title}' vazifasini qabul qildingiz. Mukofot: {reward} tanga")

    try:
        bot.send_message(creator, f"👤 Foydalanuvchi {c.from_user.id} vazifani qabul qildi (id: {tid})")
    except Exception:
        pass

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅ Men bajardim", callback_data=f"checksub_{tid}"))
    if req:
        bot.send_message(uid, f"🔔 Ushbu vazifa uchun {req} kanaliga obuna bo'lish talab qilinadi. Obuna bo'lgach, quyidagi tugmani bosing.", reply_markup=kb)
    else:
        bot.send_message(uid, "✅ Vazifani bajarganingizni tasdiqlash uchun quyidagi tugmani bosing:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("remove_sponsor_"))
def remove_sponsor(c):
    if not is_admin(c.from_user.id):
        bot.answer_callback_query(c.id, "❌ Ruxsat yo'q")
        return
    enc = c.data.split("remove_sponsor_")[1]
    ch = _decode_channel(enc)
    db_query("DELETE FROM sponsors WHERE channel=?", (ch,), commit=True)
    bot.answer_callback_query(c.id, f"✅ Sponsor {ch} o'chirildi")
    try:
        bot.delete_message(c.message.chat.id, c.message.message_id)
    except Exception:
        pass

@bot.callback_query_handler(func=lambda c: c.data == "sponsor_edit")
def sponsor_edit(c):
    if not is_admin(c.from_user.id):
        bot.answer_callback_query(c.id, "❌ Ruxsat yo'q")
        return
    admin_state[c.from_user.id] = {"step": "sponsor"}
    bot.answer_callback_query(c.id, "✍️ Iltimos yangi @kanal yoki t.me/havola yuboring")
    try:
        bot.delete_message(c.message.chat.id, c.message.message_id)
    except Exception:
        pass

@bot.callback_query_handler(func=lambda c: c.data == "sponsor_cancel")
def sponsor_cancel(c):
    if not is_admin(c.from_user.id):
        bot.answer_callback_query(c.id, "❌ Ruxsat yo'q")
        return
    admin_state.pop(c.from_user.id, None)
    bot.answer_callback_query(c.id, "❌ Sponsor qo'shish bekor qilindi")
    try:
        bot.delete_message(c.message.chat.id, c.message.message_id)
    except Exception:
        pass

@bot.callback_query_handler(func=lambda c: c.data == "sponsor_confirm")
def sponsor_confirm(c):
    if not is_admin(c.from_user.id):
        bot.answer_callback_query(c.id, "❌ Ruxsat yo'q")
        return
    s = admin_state.get(c.from_user.id)
    if not s or s.get("step") != "sponsor_confirm":
        bot.answer_callback_query(c.id, "❌ Tasdiqlash uchun sponsor yo'q")
        return
    ch = s.get("pending")
    if not ch:
        bot.answer_callback_query(c.id, "❌ Noma'lum kanal")
        return

    existing = db_query("SELECT 1 FROM sponsors WHERE channel=?", (ch,), fetchone=True)
    if existing:
        admin_state.pop(c.from_user.id, None)
        bot.answer_callback_query(c.id, "ℹ️ Bu sponsor allaqachon mavjud")
        try:
            bot.delete_message(c.message.chat.id, c.message.message_id)
        except Exception:
            pass
        return

    db_query("INSERT INTO sponsors (channel) VALUES (?)", (ch,), commit=True)
    admin_state.pop(c.from_user.id, None)
    bot.answer_callback_query(c.id, f"✅ Sponsor qo'shildi: {ch}")
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
        bot.answer_callback_query(c.id, "❌ Vazifa topilmadi")
        return
    done, title, reward, creator, req, slots = row
    assigned = db_query("SELECT completed FROM task_assignees WHERE task_id=? AND user_id= ?", (tid, uid), fetchone=True)
    if not assigned:
        bot.answer_callback_query(c.id, "❌ Siz ushbu vazifani qabul qilmagansiz")
        return
    if done:
        bot.answer_callback_query(c.id, "ℹ️ Vazifa allaqachon bajarilgan")
        return
    if assigned[0] == 1:
        bot.answer_callback_query(c.id, "ℹ️ Siz ushbu vazifani allaqachon bajardingiz")
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
        bot.answer_callback_query(c.id, "✅ Vazifa bajarildi, mukofot topshirildi")
        bot.send_message(uid, f"✅ Siz '{title}' vazifasini bajardingiz. Mukofot: {reward} tanga")
        try:
            bot.send_message(creator, f"✅ Foydalanuvchi {uid} vazifani bajardi (id: {tid})")
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
            bot.answer_callback_query(c.id, "✅ Obuna tekshirildi va vazifa bajarildi")
            bot.send_message(uid, f"✅ Siz '{title}' vazifasini bajardingiz va {reward} tanga oldingiz")
            try:
                bot.send_message(creator, f"✅ Foydalanuvchi {uid} vazifani bajardi (id: {tid})")
            except Exception:
                pass
            completed_count = db_query("SELECT COUNT(*) FROM task_assignees WHERE task_id=? AND completed=1", (tid,), fetchone=True)[0] or 0
            if completed_count >= (slots or 1):
                db_query("UPDATE tasks SET done=1 WHERE id=?", (tid,), commit=True)
        else:
            bot.answer_callback_query(c.id, "❌ Siz kanalga obuna bo'lmagansiz")
    except Exception:
        bot.answer_callback_query(c.id, "❌ Kanalni tekshirishda xatolik. Iltimos, admin bilan bog'laning")

@bot.message_handler(commands=["check_photos"])
def cmd_check_photos(m):
    if not is_admin(m.from_user.id):
        return

    missing_files = []
    existing_files = []

    main_files = ["balance.jpg", "shop_categories.jpg"]
    for filename in main_files:
        path = get_photo_path(filename)
        if os.path.exists(path):
            existing_files.append(f"✅ {filename}")
        else:
            missing_files.append(f"❌ {filename}")

    for case in CASES:
        path = get_photo_path(case["photo"])
        if os.path.exists(path):
            existing_files.append(f"✅ Keys {case['id']}: {case['photo']}")
        else:
            missing_files.append(f"❌ Keys {case['id']}: {case['photo']}")

    response = "📁 Fayllar ro'yxati:\n\n"

    if existing_files:
        response += "✅ Mavjud fayllar:\n" + "\n".join(existing_files) + "\n\n"

    if missing_files:
        response += "❌ Mavjud bo'lmagan fayllar:\n" + "\n".join(missing_files) + "\n\n"
        response += "🖼 Rasm qo'shish uchun Admin panelda '🖼 Rasm qo'shish' tugmasini bosing."
    else:
        response += "✅ Barcha fayllar mavjud!"

    bot.send_message(m.chat.id, response)

@bot.message_handler(func=lambda m: getattr(m, 'text', '').strip() == "💸 Tanga berish")
def give_coins_start(m):
    if not is_admin(m.from_user.id):
        return
    admin_state[m.from_user.id] = {"step": "give_username"}
    bot.send_message(m.chat.id, "✍️ Qabul qiluvchining @username yoki user_id sini yuboring")

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
        bot.send_message(m.chat.id, "❌ Foydalanuvchi topilmadi. To'g'ri @username kiritilganiga yoki foydalanuvchi botni ishga tushirganiga ishonch hosil qiling.")
        return

    admin_state[m.from_user.id] = {"step": "give_amount", "target": target_id}
    bot.send_message(m.chat.id, "✍️ Necha tanga berilsin? (son)")

@bot.message_handler(func=lambda m: m.from_user.id in admin_state and admin_state[m.from_user.id]["step"] == "give_amount")
def give_coins_amount(m):
    if not is_admin(m.from_user.id):
        admin_state.pop(m.from_user.id, None)
        return
    s = admin_state[m.from_user.id]
    try:
        amount = int(m.text)
    except Exception:
        bot.send_message(m.chat.id, "❌ Butun son kiriting")
        return

    if amount <= 0:
        bot.send_message(m.chat.id, "❌ Summa musbat bo'lishi kerak")
        return

    target = s["target"]

    if not db_query("SELECT 1 FROM users WHERE user_id=?", (target,), fetchone=True):
        db_query("INSERT INTO users (user_id, coins) VALUES (?,?)", (target, amount), commit=True)
    else:
        db_query("UPDATE users SET coins = coins + ? WHERE user_id=?", (amount, target), commit=True)

    bot.send_message(m.chat.id, f"✅ Foydalanuvchi {target} ga {amount} tanga berildi")
    try:
        bot.send_message(target, f"💸 Admin sizga {amount} tanga berdi")
    except Exception:
        pass

    del admin_state[m.from_user.id]

@bot.message_handler(func=lambda m: getattr(m, 'text', '').strip() == "📊 Statistika")
def stats(m):
    users = db_query("SELECT COUNT(*) FROM users", fetchone=True)[0]
    promos = db_query("SELECT COUNT(*) FROM promocodes", fetchone=True)[0]

    bot.send_message(
        m.chat.id,
        f"📊 Statistika:\n\n"
        f"👤 Foydalanuvchilar: {users}\n"
        f"🎫 Promokodlar: {promos}"
    )

@bot.message_handler(commands=["promos"])
def admin_promos(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "❌ Ruxsat yo'q")
        return

    rows = db_query("SELECT case_id, COUNT(*) FROM promocodes GROUP BY case_id", fetchall=True)
    if not rows:
        bot.send_message(m.chat.id, "ℹ️ Hozircha promokodlar mavjud emas")
        return

    text_lines = []
    for case_id, cnt in rows:
        sample = db_query("SELECT code FROM promocodes WHERE case_id=? LIMIT 5", (case_id,), fetchall=True)
        sample_codes = ", ".join([s[0] for s in sample]) if sample else "(none)"
        text_lines.append(f"Keys {case_id}: {cnt} ta — namuna: {sample_codes}")

    bot.send_message(m.chat.id, "📦 Promokodlar:\n" + "\n".join(text_lines))

# ⭐ Sapyor - 26 katak o'yini
@bot.message_handler(func=lambda m: m.text == "⭐ Sapyor")
@require_subscription
def prediction_menu(m):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("⭐ 3 yulduz (3 tanga)", callback_data="stars3"))
    bot.send_message(m.chat.id, "Rejimni tanlang:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "stars3")
@require_subscription_callback
def show_stars_prediction(c):
    uid = c.from_user.id

    res = db_query("SELECT coins FROM users WHERE user_id=?", (uid,), fetchone=True)
    coins = res[0] if res else 0

    if coins < 3:
        bot.answer_callback_query(c.id, "❌ 3 tanga kerak", show_alert=True)
        return

    db_query("UPDATE users SET coins = coins - 3 WHERE user_id=?", (uid,), commit=True)

    cells = list(range(1, 27))
    star_cells = random.sample(cells, 3)

    kb = types.InlineKeyboardMarkup(row_width=5)

    buttons = []
    for i in cells:
        if i in star_cells:
            text = "⭐"
        else:
            text = "⬜"
        buttons.append(types.InlineKeyboardButton(text, callback_data="none"))

    kb.add(*buttons)

    bot.send_message(uid, "⭐ Mana 3 ta xavfsiz katak:", reply_markup=kb)

# 💥 Crash prognozi
@bot.message_handler(func=lambda m: m.text == "💥 Crash")
@require_subscription
def crash_prediction(m):
    uid = m.from_user.id

    res = db_query("SELECT coins FROM users WHERE user_id=?", (uid,), fetchone=True)
    coins = res[0] if res else 0

    if coins < 2:
        bot.send_message(uid, "❌ Kamida 2 tanga kerak")
        return

    db_query("UPDATE users SET coins = coins - 2 WHERE user_id=?", (uid,), commit=True)

    crash_value = round(random.uniform(1.05, 2.55), 2)

    bot.send_message(
        uid,
        f"💥 CRASH PROGNOZI\n\n"
        f"🚀 Bugungi o'sish:\n\n"
        f"🔥 {crash_value}x"
    )

# Botni ishga tushirish
bot.infinity_polling(skip_pending=True)