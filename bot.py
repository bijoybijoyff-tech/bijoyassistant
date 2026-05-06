import os
import json
from datetime import datetime
import pytz
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)

TASKS_FILE = "tasks.json"
TIMEZONE = pytz.timezone("Asia/Dhaka")

(WAITING_TASK, WAITING_TYPE, WAITING_INTERVAL, WAITING_DATE, WAITING_TIME) = range(5)

def load_tasks():
    if os.path.exists(TASKS_FILE):
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_tasks(tasks):
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)

def get_user_tasks(user_id):
    return load_tasks().get(user_id, [])

def save_user_tasks(user_id, user_tasks):
    tasks = load_tasks()
    tasks[user_id] = user_tasks
    save_tasks(tasks)

def now_dhaka():
    return datetime.now(TIMEZONE)

async def start(update, context):
    keyboard = [
        [KeyboardButton("➕ নতুন টাস্ক যোগ করো")],
        [KeyboardButton("📋 আমার টাস্কগুলো দেখাও")],
        [KeyboardButton("🗑️ সব টাস্ক মুছো")],
    ]
    await update.message.reply_text(
        "🤖 *রিমাইন্ডার বট-এ স্বাগতম!*\n\n"
        "দুই ধরনের রিমাইন্ডার:\n"
        "🔁 *বারবার* — প্রতি X সময় পর পর\n"
        "📅 *নির্দিষ্ট তারিখে* — একটি দিনে একবার\n\n"
        "কাজ শেষে *'ডান'* লিখুন ✅",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def add_task_start(update, context):
    await update.message.reply_text(
        "📝 টাস্কটি লিখুন:",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("❌ বাতিল")]], resize_keyboard=True)
    )
    return WAITING_TASK

async def received_task(update, context):
    context.user_data["new_task"] = update.message.text.strip()
    keyboard = [
        [KeyboardButton("🔁 বারবার রিমাইন্ড")],
        [KeyboardButton("📅 নির্দিষ্ট তারিখে")],
        [KeyboardButton("❌ বাতিল")],
    ]
    await update.message.reply_text(
        f"✅ টাস্ক: *{context.user_data['new_task']}*\n\nকোন ধরনের রিমাইন্ডার?",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return WAITING_TYPE

async def received_type(update, context):
    text = update.message.text.strip()
    if text == "❌ বাতিল":
        await show_main_menu(update, context)
        return ConversationHandler.END
    if text == "🔁 বারবার রিমাইন্ড":
        context.user_data["reminder_type"] = "interval"
        keyboard = [
            [KeyboardButton("⏰ ৩০ মিনিট"), KeyboardButton("⏰ ১ ঘণ্টা")],
            [KeyboardButton("⏰ ২ ঘণ্টা"), KeyboardButton("⏰ ৬ ঘণ্টা")],
            [KeyboardButton("⏰ ১২ ঘণ্টা"), KeyboardButton("⏰ ২৪ ঘণ্টা")],
            [KeyboardButton("❌ বাতিল")],
        ]
        await update.message.reply_text(
            "⏱️ কত সময় পর পর রিমাইন্ড করবো?\n_(বা নিজে মিনিট লিখুন, যেমন: 45)_",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return WAITING_INTERVAL
    elif text == "📅 নির্দিষ্ট তারিখে":
        context.user_data["reminder_type"] = "date"
        await update.message.reply_text(
            "📅 কোন তারিখে?\n\nফরম্যাট: *DD/MM/YYYY*\nযেমন: `15/06/2026`",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("❌ বাতিল")]], resize_keyboard=True)
        )
        return WAITING_DATE
    else:
        await update.message.reply_text("❌ বোতাম থেকে সিলেক্ট করুন।")
        return WAITING_TYPE

async def received_interval(update, context):
    text = update.message.text.strip()
    if text == "❌ বাতিল":
        await show_main_menu(update, context)
        return ConversationHandler.END
    interval_map = {
        "⏰ ৩০ মিনিট": 30, "⏰ ১ ঘণ্টা": 60,
        "⏰ ২ ঘণ্টা": 120, "⏰ ৬ ঘণ্টা": 360,
        "⏰ ১২ ঘণ্টা": 720, "⏰ ২৪ ঘণ্টা": 1440,
    }
    if text in interval_map:
        interval_minutes = interval_map[text]
    else:
        try:
            interval_minutes = int(text)
            if interval_minutes < 1:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ সঠিক সময় দিন (মিনিটে সংখ্যা লিখুন)")
            return WAITING_INTERVAL

    user_id = str(update.effective_user.id)
    new_task = {
        "id": int(now_dhaka().timestamp()),
        "task": context.user_data.get("new_task", ""),
        "type": "interval",
        "interval_minutes": interval_minutes,
        "last_reminded": None,
        "done": False
    }
    tasks = get_user_tasks(user_id)
    tasks.append(new_task)
    save_user_tasks(user_id, tasks)

    hrs = interval_minutes // 60
    mins = interval_minutes % 60
    t = (f"{hrs} ঘণ্টা " if hrs else "") + (f"{mins} মিনিট" if mins else "")
    await update.message.reply_text(
        f"🎉 *সেভ হয়েছে!*\n\n📌 {new_task['task']}\n🔁 প্রতি {t.strip()} পর পর\n\nকাজ শেষে *'ডান'* লিখুন!",
        parse_mode="Markdown"
    )
    await show_main_menu(update, context)
    return ConversationHandler.END

async def received_date(update, context):
    text = update.message.text.strip()
    if text == "❌ বাতিল":
        await show_main_menu(update, context)
        return ConversationHandler.END
    try:
        parsed = datetime.strptime(text, "%d/%m/%Y")
        if parsed.date() < now_dhaka().date():
            await update.message.reply_text("❌ অতীতের তারিখ দেওয়া যাবে না! আজকের বা ভবিষ্যতের তারিখ দিন:")
            return WAITING_DATE
        context.user_data["reminder_date"] = text
    except ValueError:
        await update.message.reply_text("❌ ফরম্যাট ঠিক নেই! এভাবে লিখুন: `15/06/2026`", parse_mode="Markdown")
        return WAITING_DATE

    await update.message.reply_text(
        f"📅 তারিখ: *{text}*\n\n⏰ কোন সময়ে?\n\n24-ঘণ্টা ফরম্যাট: *HH:MM*\nযেমন: `09:00` বা `21:30`",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("❌ বাতিল")]], resize_keyboard=True)
    )
    return WAITING_TIME

async def received_time(update, context):
    text = update.message.text.strip()
    if text == "❌ বাতিল":
        await show_main_menu(update, context)
        return ConversationHandler.END
    try:
        datetime.strptime(text, "%H:%M")
    except ValueError:
        await update.message.reply_text("❌ ফরম্যাট ঠিক নেই! যেমন: `09:00` বা `21:30`", parse_mode="Markdown")
        return WAITING_TIME

    date_str = context.user_data.get("reminder_date")
    remind_at = f"{date_str} {text}"
    remind_dt = TIMEZONE.localize(datetime.strptime(remind_at, "%d/%m/%Y %H:%M"))
    if remind_dt <= now_dhaka():
        await update.message.reply_text("❌ এই সময় পার হয়ে গেছে! ভবিষ্যতের সময় দিন:")
        return WAITING_TIME

    user_id = str(update.effective_user.id)
    task_name = context.user_data.get("new_task", "")
    new_task = {
        "id": int(now_dhaka().timestamp()),
        "task": task_name,
        "type": "date",
        "remind_at": remind_at,
        "done": False
    }
    tasks = get_user_tasks(user_id)
    tasks.append(new_task)
    save_user_tasks(user_id, tasks)

    month_names = ["","জানুয়ারি","ফেব্রুয়ারি","মার্চ","এপ্রিল","মে","জুন",
                   "জুলাই","আগস্ট","সেপ্টেম্বর","অক্টোবর","নভেম্বর","ডিসেম্বর"]
    d, m, y = date_str.split("/")
    bangla_date = f"{int(d)} {month_names[int(m)]}, {y}"

    await update.message.reply_text(
        f"🎉 *সেভ হয়েছে!*\n\n📌 {task_name}\n📅 {bangla_date}\n⏰ {text}\n\nনির্দিষ্ট সময়ে রিমাইন্ড পাবেন!",
        parse_mode="Markdown"
    )
    await show_main_menu(update, context)
    return ConversationHandler.END

async def show_tasks(update, context):
    user_id = str(update.effective_user.id)
    active = [t for t in get_user_tasks(user_id) if not t.get("done")]
    if not active:
        await update.message.reply_text("📭 কোনো সক্রিয় টাস্ক নেই!")
        return
    month_names = ["","জানু","ফেব্রু","মার্চ","এপ্রিল","মে","জুন",
                   "জুলাই","আগস্ট","সেপ্টে","অক্টো","নভে","ডিসে"]
    msg = "📋 *আপনার সক্রিয় টাস্কগুলো:*\n\n"
    for i, task in enumerate(active, 1):
        if task.get("type") == "date":
            ds, ts = task["remind_at"].split(" ")
            d, m, y = ds.split("/")
            msg += f"{i}. 📌 {task['task']}\n   📅 {int(d)} {month_names[int(m)]} {y}, ⏰ {ts}\n\n"
        else:
            iv = task.get("interval_minutes", 60)
            hrs = iv // 60; mins = iv % 60
            t = (f"{hrs}ঘণ্টা " if hrs else "") + (f"{mins}মি" if mins else "")
            msg += f"{i}. 📌 {task['task']}\n   🔁 প্রতি {t.strip()} পর পর\n\n"
    msg += "✅ কাজ শেষে *'ডান'* লিখুন"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def handle_done(update, context):
    user_id = str(update.effective_user.id)
    all_tasks = get_user_tasks(user_id)
    active = [t for t in all_tasks if not t.get("done")]
    if not active:
        await update.message.reply_text("📭 কোনো সক্রিয় টাস্ক নেই!")
        return
    if len(active) == 1:
        task = active[0]
        for t in all_tasks:
            if t["id"] == task["id"]:
                t["done"] = True
        save_user_tasks(user_id, all_tasks)
        await update.message.reply_text(f"✅ *'{task['task']}'* সম্পন্ন! 🎉", parse_mode="Markdown")
    else:
        msg = "কোন টাস্কটি সম্পন্ন হয়েছে?\n\n"
        for i, task in enumerate(active, 1):
            msg += f"{i}. {task['task']}\n"
        msg += "\nনম্বর লিখুন (যেমন: 1)"
        context.user_data["pending_done"] = active
        await update.message.reply_text(msg)

async def handle_done_number(update, context):
    if "pending_done" not in context.user_data:
        return
    try:
        num = int(update.message.text.strip())
        active = context.user_data["pending_done"]
        if 1 <= num <= len(active):
            task = active[num - 1]
            user_id = str(update.effective_user.id)
            all_tasks = get_user_tasks(user_id)
            for t in all_tasks:
                if t["id"] == task["id"]:
                    t["done"] = True
            save_user_tasks(user_id, all_tasks)
            del context.user_data["pending_done"]
            await update.message.reply_text(f"✅ *'{task['task']}'* সম্পন্ন! 🎉", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ সঠিক নম্বর দিন!")
    except ValueError:
        pass

async def clear_all_tasks(update, context):
    save_user_tasks(str(update.effective_user.id), [])
    await update.message.reply_text("🗑️ সব টাস্ক মুছে ফেলা হয়েছে!")

async def show_main_menu(update, context):
    keyboard = [
        [KeyboardButton("➕ নতুন টাস্ক যোগ করো")],
        [KeyboardButton("📋 আমার টাস্কগুলো দেখাও")],
        [KeyboardButton("🗑️ সব টাস্ক মুছো")],
    ]
    await update.message.reply_text("মেইন মেনু 👇", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def cancel(update, context):
    await show_main_menu(update, context)
    return ConversationHandler.END

async def send_reminders(context):
    all_tasks = load_tasks()
    now = now_dhaka()
    for user_id, user_tasks in all_tasks.items():
        changed = False
        for task in user_tasks:
            if task.get("done"):
                continue
            should_remind = False
            task_type = task.get("type", "interval")

            if task_type == "date":
                try:
                    remind_dt = TIMEZONE.localize(datetime.strptime(task["remind_at"], "%d/%m/%Y %H:%M"))
                    diff = (now - remind_dt).total_seconds()
                    if 0 <= diff < 120:
                        should_remind = True
                except Exception:
                    pass
            else:
                interval_minutes = task.get("interval_minutes", 60)
                last_reminded = task.get("last_reminded")
                if last_reminded is None:
                    should_remind = True
                else:
                    try:
                        last_time = datetime.fromisoformat(last_reminded)
                        if last_time.tzinfo is None:
                            last_time = TIMEZONE.localize(last_time)
                        if (now - last_time).total_seconds() / 60 >= interval_minutes:
                            should_remind = True
                    except Exception:
                        should_remind = True

            if should_remind:
                try:
                    emoji = "📅" if task_type == "date" else "⏰"
                    extra = f"\n🗓️ {task.get('remind_at', '')}" if task_type == "date" else ""
                    await context.bot.send_message(
                        chat_id=int(user_id),
                        text=f"{emoji} *রিমাইন্ডার!*\n\n📌 {task['task']}{extra}\n\nকাজ হলে *'ডান'* লিখুন ✅",
                        parse_mode="Markdown"
                    )
                    if task_type == "date":
                        task["done"] = True
                    else:
                        task["last_reminded"] = now.isoformat()
                    changed = True
                except Exception as e:
                    print(f"রিমাইন্ড ব্যর্থ {user_id}: {e}")
        if changed:
            all_tasks[user_id] = user_tasks
    save_tasks(all_tasks)

async def handle_message(update, context):
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
        await update.message.reply_text("বুঝতে পারিনি। বোতাম ব্যবহার করুন বা কাজ শেষে 'ডান' লিখুন।")

def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        print("❌ BOT_TOKEN পাওয়া যায়নি!")
        return
    app = Application.builder().token(token).build()
    conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^➕ নতুন টাস্ক যোগ করো$"), add_task_start),
            CommandHandler("add", add_task_start),
        ],
        states={
            WAITING_TASK:     [MessageHandler(filters.TEXT & ~filters.COMMAND, received_task)],
            WAITING_TYPE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, received_type)],
            WAITING_INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_interval)],
            WAITING_DATE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, received_date)],
            WAITING_TIME:     [MessageHandler(filters.TEXT & ~filters.COMMAND, received_time)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tasks", show_tasks))
    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.job_queue.run_repeating(send_reminders, interval=60, first=10)
    print("✅ বট চালু হয়েছে!")
    app.run_polling()

if __name__ == "__main__":
    main()
