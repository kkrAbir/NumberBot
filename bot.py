import os
import json
import logging
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

# --- কনফিগারেশন ---
ADMIN_ID = 6388412065  # আপনার টেলিগ্রাম আইডি দিন
BOT_TOKEN = "8417045385:AAGO3QSwZtSGksCqy1Nq5vOEb_nzn7hmPxM" # আপনার বট টোকেন দিন
CHANNEL_USERNAME = "@SMSGenNet" # আপনার চ্যানেলের ইউজারনেম (বটকে অ্যাডমিন দিন)
GROUP_LINK = "https://t.me/BD71BOTT" # Oip বাটনের লিংক
DB_FILE = 'database.json'

# --- ডাটাবেস ---
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    return {"users": {}, "countries": {}, "banned": [], "admin_state": {}}

def save_db(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# --- Render-এর জন্য Web Server ---
app = Flask('')
@app.route('/')
def home(): return "Running..."

def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- হেল্পার ফাংশন ---
async def is_subscribed(bot, user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("🌍 Available Country", callback_data='list_countries')],
        [InlineKeyboardButton("📊 My Info", callback_data='my_info'), InlineKeyboardButton("🔐 OTP (Group)", url=GROUP_LINK)]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- হ্যান্ডলারস ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    db = load_db()
    
    if user_id in db['banned']:
        return await update.message.reply_text("🚫 আপনি ব্যানড!")

    if user_id not in db['users']:
        db['users'][user_id] = {"current": "None", "changes": 0}
        save_db(db)

    if not await is_subscribed(context.bot, int(user_id)):
        keyboard = [[InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME.replace('@','')}")],
                    [InlineKeyboardButton("✅ I have Joined", callback_data="check_join")]]
        return await update.message.reply_text("বটটি ব্যবহার করতে আমাদের চ্যানেলে জয়েন করুন।", reply_markup=InlineKeyboardMarkup(keyboard))

    await update.message.reply_text("👋 স্বাগতম! নিচের বাটন থেকে অপশন সিলেক্ট করুন।", reply_markup=get_main_menu())

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    db = load_db()
    
    await query.answer()

    if query.data == "check_join":
        if await is_subscribed(context.bot, int(user_id)):
            await query.message.edit_text("ধন্যবাদ! এখন আপনি বটটি ব্যবহার করতে পারেন।", reply_markup=get_main_menu())
        else:
            await query.answer("আপনি এখনো জয়েন করেননি!", show_alert=True)

    elif query.data == "list_countries":
        if not db['countries']:
            return await query.edit_message_text("কোনো দেশ বা নম্বর এখনো নেই।", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='back')]]))
        
        keyboard = []
        for c in db['countries'].keys():
            count = len(db['countries'][c])
            keyboard.append([InlineKeyboardButton(f"{c} ({count} numbers)", callback_data=f"sel_{c}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='back')])
        await query.edit_message_text("একটি দেশ সিলেক্ট করুন:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("sel_"):
        country = query.data.split("_")[1]
        if not db['countries'].get(country):
            return await query.answer("এই দেশে কোনো নম্বর খালি নেই!", show_alert=True)
        
        num = db['countries'][country].pop(0)
        db['users'][user_id]['current'] = f"{country}: {num}"
        db['users'][user_id]['changes'] += 1
        save_db(db)
        
        keyboard = [[InlineKeyboardButton("♻️ Change Number", callback_data='list_countries')],
                    [InlineKeyboardButton("🔙 Main Menu", callback_data='back')]]
        await query.edit_message_text(f"✅ আপনার নম্বর: `{num}`\n🌍 দেশ: {country}", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "my_info":
        u = db['users'].get(user_id)
        text = f"👤 ইউজার ইনফো\n━━━━━━━━━━━━━━━\n📞 নম্বর: `{u['current']}`\n🔄 মোট চেঞ্জ: {u['changes']} বার"
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='back')]]))

    elif query.data == "back":
        await query.message.edit_text("👋 স্বাগতম! নিচের বাটন থেকে অপশন সিলেক্ট করুন।", reply_markup=get_main_menu())

# --- অ্যাডমিন ফিচার (ফাইল আপলোড ও ম্যানেজমেন্ট) ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    db = load_db()
    msg = (f"🛠 অ্যাডমিন প্যানেল\n\n"
           f"👥 মোট ইউজার: {len(db['users'])}\n"
           f"🌍 দেশ সংখ্যা: {len(db['countries'])}\n\n"
           f"📂 নম্বর ফাইল আপলোড করতে লিখুন: `/add CountryName` এবং সাথে .txt ফাইলটি দিন।\n"
           f"🚫 ব্যান করতে: `/ban user_id` \n"
           f"📢 নোটিশ: `/broadcast মেসেজ`")
    await update.message.reply_text(msg)

async def handle_admin_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    
    caption = update.message.caption
    if not caption or not caption.startswith("/add"):
        return await update.message.reply_text("⚠️ ফাইল আপলোড করার সময় ক্যাপশনে `/add CountryName` লিখুন।")

    country_name = caption.replace("/add", "").strip()
    file = await update.message.document.get_file()
    file_path = "temp_numbers.txt"
    await file.download_to_drive(file_path)

    with open(file_path, 'r') as f:
        new_numbers = [line.strip() for line in f if line.strip()]

    db = load_db()
    if country_name not in db['countries']:
        db['countries'][country_name] = []
    
    db['countries'][country_name].extend(new_numbers)
    # ডুপ্লিকেট রিমুভ
    db['countries'][country_name] = list(set(db['countries'][country_name]))
    save_db(db)
    
    os.remove(file_path)
    await update.message.reply_text(f"✅ সফলভাবে {country_name}-এ {len(new_numbers)} টি নম্বর যোগ হয়েছে।")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    text = " ".join(context.args)
    if not text: return
    db = load_db()
    for uid in db['users'].keys():
        try: await context.bot.send_message(chat_id=uid, text=f"📢 নোটিশ:\n\n{text}")
        except: pass
    await update.message.reply_text("✅ ব্রডকাস্ট সম্পন্ন।")

# --- মেইন ---
def main():
    threading.Thread(target=run_web, daemon=True).start()
    app_bot = Application.builder().token(BOT_TOKEN).build()

    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("admin", admin_panel))
    app_bot.add_handler(CommandHandler("broadcast", broadcast))
    app_bot.add_handler(CallbackQueryHandler(handle_callback))
    # অ্যাডমিন ফাইল হ্যান্ডলার
    app_bot.add_handler(MessageHandler(filters.Document.MimeType("text/plain"), handle_admin_docs))

    print("Bot is running...")
    app_bot.run_polling()

if __name__ == '__main__':
    main()
