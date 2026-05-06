import os
import json
import calendar
from datetime import datetime, timedelta
import pytz
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)

TASKS_FILE = "tasks.json"
TIMEZONE = pytz.timezone("Asia/Dhaka")

# Conversation states
(WAITING_TASK, WAITING_TYPE, WAITING_INTERVAL) = range(3)

def load_tasks():
    if os.path.exists(TASKS_FILE):
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_tasks(tasks):
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)

def get_user_tasks(user_id):
    return load_tasks().get(str(user_id), [])

def save_user_tasks(user_id, user_tasks):
    tasks = load_tasks()
    tasks[str(user_id)] = user_tasks
    save_tasks(tasks)

def now_dhaka():
    return datetime.now(TIMEZONE)

BANGLA_MONTHS = ["","জানুয়ারি","ফেব্রুয়ারি","মার্চ","এপ্রিল","মে","জুন",
                 "জুলাই","আগস্ট","সেপ্টেম্বর","অক্টোবর","নভেম্বর","ডিসেম্বর"]
BANGLA_DAYS   = ["সো","মঙ","বু","বৃ","শু","শ","র"]

# ── ক্যালেন্ডার কীবোর্ড ─────────────────────────────────────────────────────
def build_calendar(year, month):
    now = now_dhaka()
    today = now.date()
    keyboard = []

    # শিরোনাম সারি
    keyboard.append([
        InlineKeyboardButton("◀", callback_data=f"cal_prev_{year}_{month}"),
        InlineKeyboardButton(f"{BANGLA_MONTHS[month]} {year}", callback_data="cal_ignore"),
        InlineKeyboardButton("▶", callback_data=f"cal_next_{year}_{month}"),
    ])
    # সপ্তাহের দিন
    keyboard.append([InlineKeyboardButton(d, callback_data="cal_ignore") for d in BANGLA_DAYS])

    # তারিখ সারি
    cal = calendar.monthcalendar(year, month)
    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="cal_ignore"))
            else:
                d = datetime(year, month, day).date()
                label = str(day)
                if d < today:
                    row.append(InlineKeyboardButton("·", callback_data="cal_ignore"))
                elif d == today:
                    row.append(InlineKeyboardButton(f"[{day}]", callback_data=f"cal_day_{year}_{month}_{day}"))
                else:
                    row.append(InlineKeyboardButton(label, callback_data=f"cal_day_{year}_{month}_{day}"))
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("❌ বাতিল", callback_data="cal_cancel")])
    return InlineKeyboardMarkup(keyboard)

# ── সময় পিকার কীবোর্ড ────────────────────────────────────────────────────────
def build_time_picker(hour=9, minute=0):
    keyboard = [
        [
            InlineKeyboardButton("▲", callback_data=f"time_hour_up_{hour}_{minute}"),
            InlineKeyboardButton(" ", callback_data="time_ignore"),
            InlineKeyboardButton("▲", callback_data=f"time_min_up_{hour}_{minute}"),
        ],
        [
            InlineKeyboardButton(f"{hour:02d}", callback_data="time_ignore"),
            InlineKeyboardButton(":", callback_data="time_ignore"),
            InlineKeyboardButton(f"{minute:02d}", callback_data="time_ignore"),
        ],
        [
            InlineKeyboardButton("▼", callback_data=f"time_hour_dn_{hour}_{minute}"),
            InlineKeyboardButton(" ", callback_data="time_ignore"),
            InlineKeyboardButton("▼", callback_data=f"time_min_dn_{hour}_{minute}"),
        ],
        [
            InlineKeyboardButton(f"✅ {hour:02d}:{minute:02d} সেট করুন", callback_data=f"time_set_{hour}_{minute}"),
        ],
        [InlineKeyboardButton("❌ বাতিল", callback_data="time_cancel")],
    ]
    return InlineKeyboardMarkup(keyboard)

# ── মেইন মেনু ─────────────────────────────────────────────────────────────────
MAIN_KB = ReplyKeyboardMarkup([
    [KeyboardButton("➕ নতুন টাস্ক যোগ করো")],
    [KeyboardButton("📋 আমার টাস্কগুলো দেখাও")],
    [KeyboardButton("🗑️ সব টাস্ক মুছো")],
], resize_keyboard=True)

async def show_main_menu(update, context):
    await update.message.reply_text("মেইন মেনু 👇", reply_markup=MAIN_KB)

# ── /start ────────────────────────────────────────────────────────────────────
async def start(update, context):
    await update.message.reply_text(
        "🤖 *রিমাইন্ডার বট-এ স্বাগতম!*\n\n"
        "🔁 *বারবার* — প্রতি X সময় পর পর\n"
        "📅 *নির্দিষ্ট তারিখে* — ক্যালেন্ডার থেকে বেছে নিন\n\n"
        "কাজ শেষে *'ডান'* লিখুন ✅",
        parse_mode="Markdown",
        reply_markup=MAIN_KB
    )

# ── টাস্ক যোগ ─────────────────────────────────────────────────────────────────
async def add_task_start(update, context):
    await update.message.reply_text(
        "📝 টাস্কটি লিখুন:",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("❌ বাতিল")]], resize_keyboard=True)
    )
    return WAITING_TASK

async def received_task(update, context):
    if update.message.text == "❌ বাতিল":
        await show_main_menu(update, context)
        return ConversationHandler.END

    context.user_data["new_task"] = update.message.text.strip()
    keyboard = ReplyKeyboardMarkup([
        [KeyboardButton("🔁 বারবার রিমাইন্ড")],
        [KeyboardButton("📅 নির্দিষ্ট তারিখে")],
        [KeyboardButton("❌ বাতিল")],
    ], resize_keyboard=True)
    await update.message.reply_text(
        f"✅ *{context.user_data['new_task']}*\n\nকোন ধরনের রিমাইন্ডার?",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    return WAITING_TYPE

async def received_type(update, context):
    text = update.message.text.strip()
    if text == "❌ বাতিল":
        await show_main_menu(update, context)
        return ConversationHandler.END

    if text == "🔁 বারবার রিমাইন্ড":
        context.user_data["reminder_type"] = "interval"
        kb = ReplyKeyboardMarkup([
            [KeyboardButton("⏰ ৩০ মিনিট"), KeyboardButton("⏰ ১ ঘণ্টা")],
            [KeyboardButton("⏰ ২ ঘণ্টা"),  KeyboardButton("⏰ ৬ ঘণ্টা")],
            [KeyboardButton("⏰ ১২ ঘণ্টা"), KeyboardButton("⏰ ২৪ ঘণ্টা")],
            [KeyboardButton("❌ বাতিল")],
        ], resize_keyboard=True)
        await update.message.reply_text(
            "⏱️ কত সময় পর পর?\n_(বা নিজে মিনিট লিখুন, যেমন: 45)_",
            parse_mode="Markdown", reply_markup=kb
        )
        return WAITING_INTERVAL

    elif text == "📅 নির্দিষ্ট তারিখে":
        context.user_data["reminder_type"] = "date"
        now = now_dhaka()
        await update.message.reply_text(
            "📅 তারিখ বেছে নিন:",
            reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True)  # hide reply kb
        )
        await update.message.reply_text(
            "👇 ক্যালেন্ডার থেকে তারিখ সিলেক্ট করুন:",
            reply_markup=build_calendar(now.year, now.month)
        )
        return ConversationHandler.END  # callback_query হ্যান্ডেলার নেবে

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
        minutes = interval_map[text]
    else:
        try:
            minutes = int(text)
            if minutes < 1: raise ValueError
        except ValueError:
            await update.message.reply_text("❌ সঠিক মিনিট লিখুন")
            return WAITING_INTERVAL

    user_id = str(update.effective_user.id)
    task = {
        "id": int(now_dhaka().timestamp()),
        "task": context.user_data.get("new_task", ""),
        "type": "interval",
        "interval_minutes": minutes,
        "last_reminded": None,
        "done": False
    }
    tasks = get_user_tasks(user_id)
    tasks.append(task)
    save_user_tasks(user_id, tasks)

    h = minutes // 60; m = minutes % 60
    t = (f"{h} ঘণ্টা " if h else "") + (f"{m} মিনিট" if m else "")
    await update.message.reply_text(
        f"🎉 *সেভ হয়েছে!*\n\n📌 {task['task']}\n🔁 প্রতি {t.strip()} পর পর",
        parse_mode="Markdown"
    )
    await show_main_menu(update, context)
    return ConversationHandler.END

# ── ক্যালেন্ডার কলব্যাক ───────────────────────────────────────────────────────
async def calendar_callback(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "cal_ignore":
        return

    if data == "cal_cancel":
        await query.edit_message_text("❌ বাতিল করা হয়েছে।")
        return

    if data.startswith("cal_prev_") or data.startswith("cal_next_"):
        _, _, year, month = data.split("_")
        year, month = int(year), int(month)
        if data.startswith("cal_prev_"):
            month -= 1
            if month < 1: month, year = 12, year - 1
        else:
            month += 1
            if month > 12: month, year = 1, year + 1
        await query.edit_message_reply_markup(reply_markup=build_calendar(year, month))
        return

    if data.startswith("cal_day_"):
        _, _, year, month, day = data.split("_")
        year, month, day = int(year), int(month), int(day)
        context.user_data["sel_date"] = f"{day:02d}/{month:02d}/{year}"
        # তারিখ দেখিয়ে সময় পিকার খোলো
        bangla = f"{day} {BANGLA_MONTHS[month]}, {year}"
        await query.edit_message_text(
            f"📅 তারিখ: *{bangla}*\n\n⏰ এখন সময় বেছে নিন:",
            parse_mode="Markdown",
            reply_markup=build_time_picker(9, 0)
        )

# ── সময় পিকার কলব্যাক ────────────────────────────────────────────────────────
async def time_callback(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data in ("time_ignore",):
        return

    if data == "time_cancel":
        await query.edit_message_text("❌ বাতিল করা হয়েছে।")
        return

    parts = data.split("_")
    action = "_".join(parts[:3])  # time_hour_up / time_hour_dn / time_min_up / time_min_dn / time_set
    hour = int(parts[3])
    minute = int(parts[4])

    if action == "time_hour_up":
        hour = (hour + 1) % 24
    elif action == "time_hour_dn":
        hour = (hour - 1) % 24
    elif action == "time_min_up":
        minute = (minute + 15) % 60
    elif action == "time_min_dn":
        minute = (minute - 15) % 60

    if action == "time_set":
        # সেভ করো
        date_str = context.user_data.get("sel_date", "")
        task_name = context.user_data.get("new_task", "")
        remind_at = f"{date_str} {hour:02d}:{minute:02d}"

        # অতীত চেক
        remind_dt = TIMEZONE.localize(datetime.strptime(remind_at, "%d/%m/%Y %H:%M"))
        if remind_dt <= now_dhaka():
            await query.edit_message_text(
                "❌ এই সময় পার হয়ে গেছে!\nঅনুগ্রহ করে আবার তারিখ সিলেক্ট করুন।",
                reply_markup=build_calendar(now_dhaka().year, now_dhaka().month)
            )
            return

        user_id = str(query.from_user.id)
        task = {
            "id": int(now_dhaka().timestamp()),
            "task": task_name,
            "type": "date",
            "remind_at": remind_at,
            "done": False
        }
        tasks = get_user_tasks(user_id)
        tasks.append(task)
        save_user_tasks(user_id, tasks)

        d, m, y = date_str.split("/")
        bangla_date = f"{int(d)} {BANGLA_MONTHS[int(m)]}, {y}"
        await query.edit_message_text(
            f"🎉 *সেভ হয়েছে!*\n\n"
            f"📌 {task_name}\n"
            f"📅 {bangla_date}\n"
            f"⏰ {hour:02d}:{minute:02d}",
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_reply_markup(reply_markup=build_time_picker(hour, minute))

# ── টাস্ক লিস্ট ───────────────────────────────────────────────────────────────
async def show_tasks(update, context):
    user_id = str(update.effective_user.id)
    active = [t for t in get_user_tasks(user_id) if not t.get("done")]
    if not active:
        await update.message.reply_text("📭 কোনো সক্রিয় টাস্ক নেই!")
        return
    msg = "📋 *আপনার সক্রিয় টাস্কগুলো:*\n\n"
    for i, task in enumerate(active, 1):
        if task.get("type") == "date":
            ds, ts = task["remind_at"].split(" ")
            d, m, y = ds.split("/")
            msg += f"{i}. 📌 {task['task']}\n   📅 {int(d)} {BANGLA_MONTHS[int(m)]} {y}, ⏰ {ts}\n\n"
        else:
            iv = task.get("interval_minutes", 60)
            h = iv // 60; mn = iv % 60
            t = (f"{h}ঘণ্টা " if h else "") + (f"{mn}মি" if mn else "")
            msg += f"{i}. 📌 {task['task']}\n   🔁 প্রতি {t.strip()} পর পর\n\n"
    msg += "✅ কাজ শেষে *'ডান'* লিখুন"
    await update.message.reply_text(msg, parse_mode="Markdown")

# ── ডান হ্যান্ডেল ─────────────────────────────────────────────────────────────
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
            if t["id"] == task["id"]: t["done"] = True
        save_user_tasks(user_id, all_tasks)
        await update.message.reply_text(f"✅ *'{task['task']}'* সম্পন্ন! 🎉", parse_mode="Markdown")
    else:
        msg = "কোন টাস্কটি সম্পন্ন হয়েছে?\n\n"
        for i, t in enumerate(active, 1): msg += f"{i}. {t['task']}\n"
        msg += "\nনম্বর লিখুন (যেমন: 1)"
        context.user_data["pending_done"] = active
        await update.message.reply_text(msg)

async def handle_done_number(update, context):
    if "pending_done" not in context.user_data: return
    try:
        num = int(update.message.text.strip())
        active = context.user_data["pending_done"]
        if 1 <= num <= len(active):
            task = active[num - 1]
            user_id = str(update.effective_user.id)
            all_tasks = get_user_tasks(user_id)
            for t in all_tasks:
                if t["id"] == task["id"]: t["done"] = True
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

async def cancel(update, context):
    await show_main_menu(update, context)
    return ConversationHandler.END

# ── ব্যাকগ্রাউন্ড রিমাইন্ডার ─────────────────────────────────────────────────
async def send_reminders(context):
    all_tasks = load_tasks()
    now = now_dhaka()
    for user_id, user_tasks in all_tasks.items():
        changed = False
        for task in user_tasks:
            if task.get("done"): continue
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
                minutes = task.get("interval_minutes", 60)
                last = task.get("last_reminded")
                if last is None:
                    should_remind = True
                else:
                    try:
                        lt = datetime.fromisoformat(last)
                        if lt.tzinfo is None: lt = TIMEZONE.localize(lt)
                        if (now - lt).total_seconds() / 60 >= minutes:
                            should_remind = True
                    except Exception:
                        should_remind = True

            if should_remind:
                try:
                    emoji = "📅" if task_type == "date" else "⏰"
                    extra = f"\n🗓️ {task.get('remind_at','')}" if task_type == "date" else ""
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

# ── জেনেরিক মেসেজ ─────────────────────────────────────────────────────────────
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

# ── main ───────────────────────────────────────────────────────────────────────
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
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tasks", show_tasks))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(calendar_callback, pattern="^cal_"))
    app.add_handler(CallbackQueryHandler(time_callback, pattern="^time_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.job_queue.run_repeating(send_reminders, interval=60, first=10)
    print("✅ বট চালু হয়েছে!")
    app.run_polling()

if __name__ == "__main__":
    main()
