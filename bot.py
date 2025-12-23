import os
import json
import logging
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

# --- কনফিগারেশন ---
ADMIN_ID = 6388412065  # আপনার টেলিগ্রাম আইডি এখানে দিন
TOKEN = "8417045385:AAGO3QSwZtSGksCqy1Nq5vOEb_nzn7hmPxM" # আপনার বট টোকেন দিন
DB_FILE = 'database.json'
NUMBERS_FILE = 'Number.txt'

# --- ডাটাবেস লোড/সেভ ---
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    return {"users": {}, "available_numbers": [], "banned": []}

def save_db(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# --- Render-এর জন্য Web Server ---
app = Flask('')
@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- হেল্পার ফাংশন ---
def is_admin(user_id):
    return user_id == ADMIN_ID

# --- ইউজার হ্যান্ডলারস ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    db = load_db()
    
    if user_id in db['banned']:
        return

    welcome_text = (
        "👋 স্বাগতম!\n\n"
        "এই বটের মাধ্যমে আপনি ইউনিক নম্বর সংগ্রহ করতে পারবেন।\n"
        "প্রতিটি নম্বর একবারই ব্যবহার করা হয়।"
    )
    keyboard = [[InlineKeyboardButton("🎯 Get Number", callback_data='get_num')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    db = load_db()
    
    if user_id in db['banned']:
        await query.answer("আপনি ব্যানড!", show_alert=True)
        return

    await query.answer()
    
    if query.data == 'get_num':
        await process_get_number(query, user_id, db)
    elif query.data == 'change_num':
        await process_change_number(query, user_id, db)
    elif query.data == 'my_info':
        await show_info(query, user_id, db)

async def process_get_number(query, user_id, db):
    user_data = db['users'].get(user_id, {"current": None, "changes": 0})
    
    if user_data['current']:
        await query.edit_message_text(f"আপনার কাছে অলরেডি একটি নম্বর আছে: `{user_data['current']}`", 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("♻️ Change Number", callback_data='change_num')]]), parse_mode='Markdown')
        return

    if not db['available_numbers']:
        await query.edit_message_text("⚠️ দুঃখিত, এই মুহূর্তে কোনো নম্বর নেই। অ্যাডমিনকে জানান।")
        return

    new_num = db['available_numbers'].pop(0)
    user_data['current'] = new_num
    db['users'][user_id] = user_data
    save_db(db)
    
    await query.edit_message_text(f"✅ আপনার নম্বর: `{new_num}`", parse_mode='Markdown',
                                  reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📊 Info", callback_data='my_info')]]))

async def process_change_number(query, user_id, db):
    user_data = db['users'].get(user_id)
    if not db['available_numbers']:
        await query.edit_message_text("নম্বর শেষ! চেঞ্জ করা সম্ভব না।")
        return

    new_num = db['available_numbers'].pop(0)
    user_data['current'] = new_num
    user_data['changes'] += 1
    db['users'][user_id] = user_data
    save_db(db)
    await query.edit_message_text(f"♻️ নম্বর পরিবর্তন করা হয়েছে। নতুন নম্বর: `{new_num}`", parse_mode='Markdown')

async def show_info(query, user_id, db):
    user_data = db['users'].get(user_id, {"current": "None", "changes": 0})
    status = "Active ✅" if user_data['current'] else "Inactive ❌"
    text = (
        f"👤 ইউজার স্ট্যাটাস\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📞 বর্তমান নম্বর: `{user_data['current']}`\n"
        f"🔄 মোট চেঞ্জ: {user_data['changes']} বার\n"
        f"📊 স্ট্যাটাস: {status}"
    )
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='get_num')]]))

# --- অ্যাডমিন হ্যান্ডলারস ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    
    db = load_db()
    total = len(db['available_numbers'])
    used = len(db['users'])
    
    msg = (
        f"🛠 অ্যাডমিন প্যানেল\n\n"
        f"📦 স্টকে আছে: {total}\n"
        f"👥 মোট ইউজার: {used}\n\n"
        "ফাইল আপলোড করতে .txt ফাইল পাঠান।"
    )
    await update.message.reply_text(msg)

async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    
    file = await update.message.document.get_file()
    await file.download_to_drive(NUMBERS_FILE)
    
    with open(NUMBERS_FILE, 'r') as f:
        lines = list(set([line.strip() for line in f if line.strip()]))
    
    db = load_db()
    db['available_numbers'] = lines
    save_db(db)
    
    await update.message.reply_text(f"✅ সফলভাবে {len(lines)} টি নম্বর আপলোড হয়েছে।")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    text = " ".join(context.args)
    if not text: return
    
    db = load_db()
    count = 0
    for uid in db['users'].keys():
        try:
            await context.bot.send_message(chat_id=uid, text=f"📢 নোটিশ:\n\n{text}")
            count += 1
        except: pass
    await update.message.reply_text(f"✅ {count} জন ইউজারকে পাঠানো হয়েছে।")

# --- মেইন ফাংশন ---
def main():
    # Web server thread শুরু
    threading.Thread(target=run_web, daemon=True).start()

    app_bot = Application.builder().token(TOKEN).build()

    # Handlers
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("admin", admin_panel))
    app_bot.add_handler(CommandHandler("broadcast", broadcast))
    app_bot.add_handler(CallbackQueryHandler(handle_callback))
    app_bot.add_handler(MessageHandler(filters.Document.FileExtension("txt"), handle_docs))

    print("Bot is running...")
    app_bot.run_polling()

if __name__ == '__main__':
    main()
