import os
import json
import asyncio
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)

# ফাইলে টাস্ক সেভ
TASKS_FILE = "tasks.json"

# কথোপকথনের ধাপ
WAITING_TASK, WAITING_INTERVAL = range(2)

def load_tasks():
    if os.path.exists(TASKS_FILE):
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_tasks(tasks):
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)

def get_user_tasks(user_id: str):
    tasks = load_tasks()
    return tasks.get(user_id, [])

def save_user_tasks(user_id: str, user_tasks: list):
    tasks = load_tasks()
    tasks[user_id] = user_tasks
    save_tasks(tasks)

# /start কমান্ড
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("➕ নতুন টাস্ক যোগ করো")],
        [KeyboardButton("📋 আমার টাস্কগুলো দেখাও")],
        [KeyboardButton("🗑️ সব টাস্ক মুছো")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "🤖 *রিমাইন্ডার বট-এ স্বাগতম!*\n\n"
        "আমি নির্দিষ্ট সময় পর পর আপনাকে টাস্কের কথা মনে করিয়ে দেব।\n"
        "কাজ শেষ হলে শুধু *'ডান'* লিখুন — সেই টাস্ক আর আসবে না! ✅\n\n"
        "নিচের বোতাম থেকে শুরু করুন 👇",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

# নতুন টাস্ক যোগ করার শুরু
async def add_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 *নতুন টাস্ক যোগ করুন*\n\n"
        "টাস্কটি লিখুন (যেমন: 'রাত ১০টায় ঘুমাতে যাও' বা 'প্রজেক্ট রিপোর্ট লেখো'):",
        parse_mode="Markdown"
    )
    return WAITING_TASK

# টাস্ক নাম পেলে
async def received_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task_text = update.message.text.strip()
    context.user_data["new_task"] = task_text

    keyboard = [
        [KeyboardButton("⏰ ৩০ মিনিট"), KeyboardButton("⏰ ১ ঘণ্টা")],
        [KeyboardButton("⏰ ২ ঘণ্টা"), KeyboardButton("⏰ ৬ ঘণ্টা")],
        [KeyboardButton("⏰ ১২ ঘণ্টা"), KeyboardButton("⏰ ২৪ ঘণ্টা")],
        [KeyboardButton("❌ বাতিল")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        f"✅ টাস্ক: *{task_text}*\n\n"
        "⏱️ কত সময় পর পর রিমাইন্ড করবো?",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    return WAITING_INTERVAL

# ইন্টারভাল পেলে টাস্ক সেভ করো
async def received_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if text == "❌ বাতিল":
        await show_main_menu(update, context)
        return ConversationHandler.END

    interval_map = {
        "⏰ ৩০ মিনিট": 30,
        "⏰ ১ ঘণ্টা": 60,
        "⏰ ২ ঘণ্টা": 120,
        "⏰ ৬ ঘণ্টা": 360,
        "⏰ ১২ ঘণ্টা": 720,
        "⏰ ২৪ ঘণ্টা": 1440,
    }

    # কাস্টম মিনিট চেক
    if text in interval_map:
        interval_minutes = interval_map[text]
    else:
        try:
            interval_minutes = int(text)
            if interval_minutes < 1:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ সঠিক সময় দিন (মিনিটে সংখ্যা অথবা বোতাম চাপুন)")
            return WAITING_INTERVAL

    user_id = str(update.effective_user.id)
    task_name = context.user_data.get("new_task", "")

    new_task = {
        "id": int(datetime.now().timestamp()),
        "task": task_name,
        "interval_minutes": interval_minutes,
        "last_reminded": None,
        "done": False
    }

    user_tasks = get_user_tasks(user_id)
    user_tasks.append(new_task)
    save_user_tasks(user_id, user_tasks)

    interval_text = f"{interval_minutes} মিনিট"
    if interval_minutes >= 60:
        hours = interval_minutes // 60
        mins = interval_minutes % 60
        interval_text = f"{hours} ঘণ্টা" + (f" {mins} মিনিট" if mins else "")

    await update.message.reply_text(
        f"🎉 *টাস্ক সেভ হয়েছে!*\n\n"
        f"📌 টাস্ক: {task_name}\n"
        f"⏱️ রিমাইন্ড: প্রতি {interval_text} পর পর\n\n"
        f"কাজ শেষ হলে শুধু *'ডান'* লিখুন!",
        parse_mode="Markdown"
    )
    await show_main_menu(update, context)
    return ConversationHandler.END

# টাস্ক লিস্ট দেখাও
async def show_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_tasks = [t for t in get_user_tasks(user_id) if not t.get("done")]

    if not user_tasks:
        await update.message.reply_text(
            "📭 কোনো সক্রিয় টাস্ক নেই!\n\n'➕ নতুন টাস্ক যোগ করো' বোতাম চাপুন।"
        )
        return

    msg = "📋 *আপনার সক্রিয় টাস্কগুলো:*\n\n"
    for i, task in enumerate(user_tasks, 1):
        interval = task["interval_minutes"]
        if interval >= 60:
            hours = interval // 60
            mins = interval % 60
            interval_text = f"{hours}ঘণ্টা" + (f" {mins}মি" if mins else "")
        else:
            interval_text = f"{interval}মিনিট"
        msg += f"{i}. 📌 {task['task']}\n   ⏱️ প্রতি {interval_text} পর পর\n\n"

    msg += "✅ কাজ শেষ হলে *'ডান'* লিখুন"
    await update.message.reply_text(msg, parse_mode="Markdown")

# "ডান" মেসেজ হ্যান্ডেল
async def handle_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_tasks = get_user_tasks(user_id)
    active_tasks = [t for t in user_tasks if not t.get("done")]

    if not active_tasks:
        await update.message.reply_text("📭 কোনো সক্রিয় টাস্ক নেই!")
        return

    if len(active_tasks) == 1:
        # একটাই টাস্ক থাকলে সরাসরি শেষ করো
        task = active_tasks[0]
        for t in user_tasks:
            if t["id"] == task["id"]:
                t["done"] = True
        save_user_tasks(user_id, user_tasks)
        await update.message.reply_text(
            f"✅ দারুণ! *'{task['task']}'* সম্পন্ন হয়েছে!\n\n"
            "এই টাস্ক নিয়ে আর রিমাইন্ড করব না। 🎉",
            parse_mode="Markdown"
        )
    else:
        # একাধিক টাস্ক থাকলে কোনটা শেষ জিজ্ঞেস করো
        msg = "কোন টাস্কটি সম্পন্ন হয়েছে?\n\n"
        for i, task in enumerate(active_tasks, 1):
            msg += f"{i}. {task['task']}\n"
        msg += "\nনম্বর লিখুন (যেমন: 1)"
        context.user_data["pending_done"] = active_tasks
        await update.message.reply_text(msg)

# নম্বর দিয়ে নির্দিষ্ট টাস্ক শেষ করা
async def handle_done_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "pending_done" not in context.user_data:
        return

    try:
        num = int(update.message.text.strip())
        active_tasks = context.user_data["pending_done"]
        if 1 <= num <= len(active_tasks):
            task = active_tasks[num - 1]
            user_id = str(update.effective_user.id)
            user_tasks = get_user_tasks(user_id)
            for t in user_tasks:
                if t["id"] == task["id"]:
                    t["done"] = True
            save_user_tasks(user_id, user_tasks)
            del context.user_data["pending_done"]
            await update.message.reply_text(
                f"✅ *'{task['task']}'* সম্পন্ন! 🎉\n\nএই টাস্ক নিয়ে আর রিমাইন্ড করব না।",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("❌ সঠিক নম্বর দিন!")
    except ValueError:
        pass

# সব টাস্ক মুছো
async def clear_all_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    save_user_tasks(user_id, [])
    await update.message.reply_text("🗑️ সব টাস্ক মুছে ফেলা হয়েছে!")

# মেইন মেনু দেখাও
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("➕ নতুন টাস্ক যোগ করো")],
        [KeyboardButton("📋 আমার টাস্কগুলো দেখাও")],
        [KeyboardButton("🗑️ সব টাস্ক মুছো")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("মেইন মেনু 👇", reply_markup=reply_markup)

# বাতিল
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_main_menu(update, context)
    return ConversationHandler.END

# ব্যাকগ্রাউন্ড রিমাইন্ডার জব
async def send_reminders(context: ContextTypes.DEFAULT_TYPE):
    all_tasks = load_tasks()
    now = datetime.now()

    for user_id, user_tasks in all_tasks.items():
        changed = False
        for task in user_tasks:
            if task.get("done"):
                continue

            interval_minutes = task.get("interval_minutes", 60)
            last_reminded = task.get("last_reminded")

            should_remind = False
            if last_reminded is None:
                should_remind = True
            else:
                last_time = datetime.fromisoformat(last_reminded)
                elapsed = (now - last_time).total_seconds() / 60
                if elapsed >= interval_minutes:
                    should_remind = True

            if should_remind:
                try:
                    await context.bot.send_message(
                        chat_id=int(user_id),
                        text=f"⏰ *রিমাইন্ডার!*\n\n📌 {task['task']}\n\nকাজটি হয়ে গেলে *'ডান'* লিখুন ✅",
                        parse_mode="Markdown"
                    )
                    task["last_reminded"] = now.isoformat()
                    changed = True
                except Exception as e:
                    print(f"রিমাইন্ড পাঠাতে ব্যর্থ {user_id}: {e}")

        if changed:
            all_tasks[user_id] = user_tasks

    save_tasks(all_tasks)

# জেনেরিক মেসেজ হ্যান্ডেলার
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()

    if text in ["ডান", "done", "হয়ে গেছে", "শেষ", "✅"]:
        await handle_done(update, context)
    elif "pending_done" in context.user_data:
        await handle_done_number(update, context)
    elif update.message.text == "📋 আমার টাস্কগুলো দেখাও":
        await show_tasks(update, context)
    elif update.message.text == "🗑️ সব টাস্ক মুছো":
        await clear_all_tasks(update, context)
    else:
        await update.message.reply_text(
            "বুঝতে পারিনি। নিচের বোতাম ব্যবহার করুন অথবা 'ডান' লিখুন কাজ শেষ হলে।"
        )

def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        print("❌ BOT_TOKEN পাওয়া যায়নি!")
        return

    app = Application.builder().token(token).build()

    # ConversationHandler টাস্ক যোগের জন্য
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^➕ নতুন টাস্ক যোগ করো$"), add_task_start),
            CommandHandler("add", add_task_start),
        ],
        states={
            WAITING_TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_task)],
            WAITING_INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_interval)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tasks", show_tasks))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # প্রতি মিনিটে রিমাইন্ডার চেক
    job_queue = app.job_queue
    job_queue.run_repeating(send_reminders, interval=60, first=10)

    print("✅ বট চালু হয়েছে!")
    app.run_polling()

if __name__ == "__main__":
    main()
