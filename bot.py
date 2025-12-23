import os
import json
import logging
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

# --- কনফিগারেশন ---
ADMIN_ID = 6388412065  # আপনার আইডি দিন
BOT_TOKEN = "8417045385:AAGO3QSwZtSGksCqy1Nq5vOEb_nzn7hmPxM"
CHANNEL_USERNAME = "@SMSGenNet" # বটকে অ্যাডমিন দিন
GROUP_LINK = "https://t.me/BD71BOTT"
DB_FILE = 'database.json'

# অ্যাডমিন স্টেট ট্র্যাকিং (মেমোরিতে থাকবে)
admin_states = {}

# --- ডাটাবেস ---
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    return {"users": {}, "countries": {}, "banned": []}

def save_db(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# --- Render Web Server ---
app = Flask('')
@app.route('/')
def home(): return "Bot Running"
def run_web(): app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- হেল্পার ---
async def is_subscribed(bot, user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except: return False

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("🌍 Available Country", callback_data='list_countries')],
        [InlineKeyboardButton("📊 My Info", callback_data='my_info'), InlineKeyboardButton("🔐OTP(Group)", url=GROUP_LINK)]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- ইউজার হ্যান্ডলারস ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    db = load_db()
    
    if user_id in db['banned']: return
    if user_id not in db['users']:
        db['users'][user_id] = {"current": "None", "changes": 0}
        save_db(db)

    if not await is_subscribed(context.bot, int(user_id)):
        keyboard = [[InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME.replace('@','')}")],
                    [InlineKeyboardButton("✅ I have Joined", callback_data="check_join")]]
        return await update.message.reply_text("বটটি ব্যবহার করতে আমাদের চ্যানেলে জয়েন করুন।", reply_markup=InlineKeyboardMarkup(keyboard))

    await update.message.reply_text("👋 স্বাগতম! একটি অপশন বেছে নিন।", reply_markup=get_main_menu())

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    db = load_db()
    await query.answer()

    if query.data == "check_join":
        if await is_subscribed(context.bot, int(user_id)):
            await query.message.edit_text("ধন্যবাদ! এখন ব্যবহার করুন।", reply_markup=get_main_menu())
        else: await query.answer("আপনি এখনো জয়েন করেননি!", show_alert=True)

    elif query.data == "list_countries":
        if not db['countries']:
            return await query.edit_message_text("কোনো দেশ বা নম্বর নেই।", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='back')]]))
        keyboard = []
        for c in db['countries'].keys():
            count = len(db['countries'][c])
            keyboard.append([InlineKeyboardButton(f"{c} ({count})", callback_data=f"sel_{c}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='back')])
        await query.edit_message_text("একটি দেশ সিলেক্ট করুন:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("sel_"):
        country = query.data.split("_")[1]
        if not db['countries'].get(country):
            return await query.answer("নম্বর শেষ!", show_alert=True)
        num = db['countries'][country].pop(0)
        db['users'][user_id]['current'] = f"{country}: {num}"
        db['users'][user_id]['changes'] += 1
        save_db(db)
        await query.edit_message_text(f"✅ নম্বর: `{num}`\n🌍 দেশ: {country}", parse_mode='Markdown', 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("♻️ Change Number", callback_data='list_countries')], [InlineKeyboardButton("🔙 Back", callback_data='back')]]))

    elif query.data == "my_info":
        u = db['users'].get(user_id)
        await query.edit_message_text(f"👤 ইনফো\n📞 নম্বর: `{u['current']}`\n🔄 চেঞ্জ: {u['changes']}", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='back')]]))

    elif query.data == "back":
        await query.message.edit_text("👋 স্বাগতম! একটি অপশন বেছে নিন।", reply_markup=get_main_menu())

    # --- এডমিন বাটন হ্যান্ডলিং ---
    elif query.data == "admin_add_country":
        if int(user_id) != ADMIN_ID: return
        admin_states[user_id] = {'step': 'WAITING_COUNTRY_NAME'}
        await query.message.reply_text("📝 Give Me Country name:")

# --- টেক্সট এবং ফাইল হ্যান্ডলার (অ্যাডমিন প্রসেস) ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if int(user_id) != ADMIN_ID: return
    
    state = admin_states.get(user_id)
    if not state: return

    # স্টেপ ১: দেশের নাম নেওয়া
    if state['step'] == 'WAITING_COUNTRY_NAME':
        country_name = update.message.text.strip()
        admin_states[user_id] = {'step': 'WAITING_FILE', 'country': country_name}
        await update.message.reply_text(f"✅ Country: {country_name}\n📂 Now Give me {country_name} number.txt File:")

    # স্টেপ ২: ফাইল নেওয়া
    elif state['step'] == 'WAITING_FILE':
        if not update.message.document:
            return await update.message.reply_text("❌ দয়া করে একটি .txt ফাইল পাঠান।")
        
        country = state['country']
        file = await update.message.document.get_file()
        file_path = "temp.txt"
        await file.download_to_drive(file_path)

        with open(file_path, 'r') as f:
            new_nums = [l.strip() for l in f if l.strip()]
        
        db = load_db()
        if country not in db['countries']: db['countries'][country] = []
        db['countries'][country].extend(new_nums)
        db['countries'][country] = list(set(db['countries'][country])) # ডুপ্লিকেট ফিল্টার
        save_db(db)
        
        os.remove(file_path)
        del admin_states[user_id] # স্টেট ক্লিয়ার
        await update.message.reply_text(f"✅ সফল! {country} দেশে {len(new_nums)} টি নম্বর যোগ হয়েছে।")

# --- এডমিন কমান্ডস ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    db = load_db()
    keyboard = [[InlineKeyboardButton("➕ Add Country & Numbers", callback_data="admin_add_country")]]
    await update.message.reply_text(f"🛠 এডমিন প্যানেল\nইউজার: {len(db['users'])}\nদেশ: {len(db['countries'])}", reply_markup=InlineKeyboardMarkup(keyboard))

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args: return
    uid = context.args[0]
    db = load_db()
    if uid not in db['banned']: db['banned'].append(uid)
    save_db(db)
    await update.message.reply_text(f"🚫 User {uid} banned.")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or not context.args: return
    msg = " ".join(context.args)
    db = load_db()
    for uid in db['users'].keys():
        try: await context.bot.send_message(chat_id=uid, text=f"📢 Notice:\n\n{msg}")
        except: pass
    await update.message.reply_text("✅ Broadcast Sent.")

# --- মেইন ---
def main():
    threading.Thread(target=run_web, daemon=True).start()
    app_bot = Application.builder().token(BOT_TOKEN).build()

    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("admin", admin_panel))
    app_bot.add_handler(CommandHandler("ban", ban_user))
    app_bot.add_handler(CommandHandler("broadcast", broadcast))
    app_bot.add_handler(CallbackQueryHandler(handle_callback))
    # সব টেক্সট এবং ডকুমেন্ট হ্যান্ডেল করার জন্য
    app_bot.add_handler(MessageHandler(filters.TEXT | filters.Document.ALL, handle_message))

    print("Bot is running...")
    app_bot.run_polling()

if __name__ == '__main__':
    main()
