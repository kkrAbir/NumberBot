import os
import json
import logging
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from telegram.error import BadRequest

# --- কনফিগারেশন (এগুলো পরিবর্তন করুন) ---
ADMIN_ID = 6388412065  # আপনার আইডি
BOT_TOKEN = "8417045385:AAGO3QSwZtSGksCqy1Nq5vOEb_nzn7hmPxM"
CHANNEL_USERNAME = "@SMSGenNet" # উদা: @mychannel (বটকে এখানে অ্যাডমিন দিন)
GROUP_LINK = "https://t.me/BD71BOTT"
DB_FILE = 'database.json'

# --- ডাটাবেস ফাংশন ---
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    return {"users": {}, "countries": {}, "banned": []}

def save_db(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# --- Render-এর জন্য Web Server ---
app = Flask('')
@app.route('/')
def home(): return "Bot is Alive!"

def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- হেল্পার ফাংশন ---
async def is_subscribed(bot, user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

# --- ইউজার হ্যান্ডলারস ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db = load_db()

    if str(user_id) in db['banned']:
        return await update.message.reply_text("🚫 আপনি এই বট থেকে ব্যানড।")

    # ডাটাবেসে ইউজার সেভ
    if str(user_id) not in db['users']:
        db['users'][str(user_id)] = {"current": None, "changes": 0}
        save_db(db)

    # Force Join Check
    if not await is_subscribed(context.bot, user_id):
        keyboard = [
            [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME.replace('@','')}")],
            [InlineKeyboardButton("✅ I have Joined", callback_data="check_join")]
        ]
        return await update.message.reply_text(f"বটটি ব্যবহার করতে আমাদের চ্যানেলে জয়েন করুন।", reply_markup=InlineKeyboardMarkup(keyboard))

    # মেইন মেনু
    keyboard = [
        [InlineKeyboardButton("🎯 Get Number", callback_data='get_num')],
        [InlineKeyboardButton("🌍 Available Country", callback_data='list_countries')],
        [InlineKeyboardButton("📊 My Info", callback_data='my_info'), InlineKeyboardButton("👥 Oip (Group)", url=GROUP_LINK)]
    ]
    await update.message.reply_text("স্বাগতম! নিচের বাটন থেকে অপশন সিলেক্ট করুন।", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    db = load_db()

    if user_id in db['banned']: return await query.answer("Banned!", show_alert=True)
    await query.answer()

    if query.data == "check_join":
        if await is_subscribed(context.bot, int(user_id)):
            await query.message.delete()
            await start(update, context)
        else:
            await query.answer("আপনি এখনো জয়েন করেননি!", show_alert=True)

    elif query.data == "list_countries":
        if not db['countries']:
            return await query.edit_message_text("কোনো দেশ বা নম্বর এখনো যুক্ত করা হয়নি।", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='back')]]))
        
        keyboard = []
        for c in db['countries'].keys():
            count = len(db['countries'][c])
            keyboard.append([InlineKeyboardButton(f"{c} ({count} numbers)", callback_data=f"sel_{c}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='back')])
        await query.edit_message_text("একটি দেশ সিলেক্ট করুন:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("sel_"):
        country = query.data.split("_")[1]
        if not db['countries'].get(country):
            return await query.answer("এই দেশে কোনো নম্বর নেই!", show_alert=True)
        
        num = db['countries'][country].pop(0)
        db['users'][user_id]['current'] = f"{country}: {num}"
        save_db(db)
        
        keyboard = [
            [InlineKeyboardButton("♻️ Change Number", callback_data='list_countries')],
            [InlineKeyboardButton("👥 Oip (Group)", url=GROUP_LINK)]
        ]
        await query.edit_message_text(f"✅ আপনার নম্বর: `{num}`\n🌍 দেশ: {country}", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "my_info":
        user_info = db['users'].get(user_id)
        text = f"👤 ইউজার ইনফো\n📞 নম্বর: {user_info['current']}\n🔄 চেঞ্জ: {user_info['changes']} বার"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='back')]]))

    elif query.data == "back":
        await query.message.delete()
        await start(update, context)

# --- অ্যাডমিন হ্যান্ডলারস ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    db = load_db()
    msg = (
        f"🛠 অ্যাডমিন প্যানেল\n\n"
        f"👥 মোট ইউজার: {len(db['users'])}\n"
        f"🚫 ব্যানড ইউজার: {len(db['banned'])}\n\n"
        f"কমান্ডস:\n"
        f"/addcountry [নাম] - দেশ যোগ করতে\n"
        f"/addnum [দেশ] [নম্বর] - নম্বর যোগ করতে\n"
        f"/ban [user_id] - ব্যান করতে\n"
        f"/unban [user_id] - আনব্যান করতে\n"
        f"/broadcast [মেসেজ] - সবাইকে মেসেজ দিতে"
    )
    await update.message.reply_text(msg)

async def add_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    name = " ".join(context.args)
    if not name: return await update.message.reply_text("দেশের নাম দিন। উদা: /addcountry USA")
    db = load_db()
    if name not in db['countries']:
        db['countries'][name] = []
        save_db(db)
        await update.message.reply_text(f"✅ {name} যুক্ত হয়েছে।")

async def add_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if len(context.args) < 2: return await update.message.reply_text("উদা: /addnum USA +123456")
    country, num = context.args[0], context.args[1]
    db = load_db()
    if country in db['countries']:
        db['countries'][country].append(num)
        save_db(db)
        await update.message.reply_text(f"✅ {country}-তে নম্বর যোগ হয়েছে।")
    else:
        await update.message.reply_text("দেশটি আগে যোগ করুন।")

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    uid = context.args[0]
    db = load_db()
    if uid not in db['banned']:
        db['banned'].append(uid)
        save_db(db)
        await update.message.reply_text("ইউজার ব্যানড।")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    text = " ".join(context.args)
    db = load_db()
    for uid in db['users'].keys():
        try: await context.bot.send_message(chat_id=uid, text=f"📢 নোটিফিকেশন:\n\n{text}")
        except: pass
    await update.message.reply_text("মেসেজ পাঠানো হয়েছে।")

# --- মেইন ---
def main():
    threading.Thread(target=run_web, daemon=True).start()
    app_bot = Application.builder().token(BOT_TOKEN).build()

    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("admin", admin_panel))
    app_bot.add_handler(CommandHandler("addcountry", add_country))
    app_bot.add_handler(CommandHandler("addnum", add_number))
    app_bot.add_handler(CommandHandler("ban", ban_user))
    app_bot.add_handler(CommandHandler("broadcast", broadcast))
    app_bot.add_handler(CallbackQueryHandler(handle_callback))

    print("Bot is running...")
    app_bot.run_polling()

if __name__ == '__main__':
    main()
