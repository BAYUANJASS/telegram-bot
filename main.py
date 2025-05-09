from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
from datetime import datetime
import asyncio

TOKEN = '7928886857:AAHxlgToMCO78SRCjasdNroboOTyd7xVyYc'  # Ganti dengan token bot Anda

user_timers = {}
user_activities = {}
user_izin_counts = {}
daily_limit = {'kamar_mandi': 15, 'merokok': 2, 'makan': 5, 'bab': 4}  # Default batas izin
admin_ids = [7452519221]  # Ganti dengan ID admin grup

# Fungsi untuk menangani pesan teks
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    message_id = update.message.message_id

    if 'izin ambil makan' in text:
        await handle_izin(update, context, user_id, chat_id, message_id, 'makan', 20)
    elif 'izin kamar mandi bab' in text:
        await handle_izin(update, context, user_id, chat_id, message_id, 'bab', None)
    elif 'izin kamar mandi' in text:
        await handle_izin(update, context, user_id, chat_id, message_id, 'kamar_mandi', 5)
    elif 'izin merokok' in text:
        await handle_izin(update, context, user_id, chat_id, message_id, 'merokok', 10)

# Fungsi untuk menangani izin
async def handle_izin(update, context, user_id, chat_id, message_id, izin_type, duration):
    # Cek apakah izin sudah melebihi batas
    if user_izin_counts.get(user_id, {}).get(izin_type, 0) >= daily_limit.get(izin_type, 0):
        await safe_send_message(context, chat_id, f"⚠️ Kamu sudah mencapai batas izin untuk {izin_type} hari ini.", message_id)
        return

    if user_id in user_timers:
        await safe_send_message(context, chat_id, "⏳ Kamu masih punya izin aktif.\nGunakan /done untuk menyelesaikannya.", message_id)
        return

    reason = f"Izin {izin_type}"
    info = f"🕒 {reason} dimulai."
    if duration:
        info += f"\n⏳ Waktu: {duration} menit."

    await safe_send_message(context, chat_id, info, message_id)

    task = asyncio.create_task(timer_task(duration, chat_id, user_id, context, reason, message_id)) if duration else asyncio.create_task(wait_indefinitely(user_id))

    user_timers[user_id] = {
        'task': task,
        'start_time': datetime.now(),
        'reason': reason,
        'message_id': message_id,
        'duration': duration
    }

    # Cek apakah user_id sudah ada dalam user_activities
    if user_id not in user_activities:
        user_activities[user_id] = {}

    # Menambahkan aktivitas yang terjadi
    user_activities[user_id][izin_type] = user_activities[user_id].get(izin_type, 0) + 1

    if user_id not in user_izin_counts:
        user_izin_counts[user_id] = {izin_type: 1}
    else:
        user_izin_counts[user_id][izin_type] = user_izin_counts[user_id].get(izin_type, 0) + 1

# Fungsi untuk menangani selesai izin
async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    message_id = update.message.message_id

    if user_id in user_timers:
        start_time = user_timers[user_id]['start_time']
        reason = user_timers[user_id]['reason']
        duration_limit = user_timers[user_id].get('duration')
        elapsed = datetime.now() - start_time
        minutes = elapsed.seconds // 60
        seconds = elapsed.seconds % 60

        text = f"✅ {reason} selesai.\n⏱️ Durasi: {minutes} menit {seconds} detik."
        if duration_limit and elapsed.total_seconds() > duration_limit * 60:
            text += "\n⚠️ Estimasi waktu telah terlewati."

        user_timers[user_id]['task'].cancel()
        del user_timers[user_id]
    else:
        text = "⚠️ Tidak ada izin aktif.\nKetik `/izin` atau 'izin ambil makan' untuk mulai."

    await safe_send_message(context, chat_id, text, message_id)

# Command /rekap
async def rekap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    report = "📊 Ringkasan Harian:\n"

    # Periksa setiap pengguna di user_activities
    if not user_activities:
        await safe_send_message(context, update.message.chat.id, "⚠️ Belum ada aktivitas yang tercatat.", update.message.message_id)
        return

    for user_id, activities in user_activities.items():
        try:
            user = await context.bot.get_chat(user_id)  # Mengambil data user berdasarkan ID
            username = user.username if user.username else f"@{user_id}"  # Username atau fallback ke user_id
        except Exception as e:
            username = f"@{user_id}"  # Jika terjadi error (misalnya bot tidak bisa mengambil data), fallback ke ID pengguna

        # Menambahkan data aktivitas setiap user
        activity_report = "\n".join([f"{activity}: {count} kali" for activity, count in activities.items()])

        # Menambahkan laporan aktivitas ke report
        report += f"🏷️ {username}:\n{activity_report}\n"

    await safe_send_message(context, update.message.chat.id, report, update.message.message_id)

async def siapa_izin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    active_users = []
    for user_id, timer in user_timers.items():
        try:
            user = await context.bot.get_chat(user_id)  # Mengambil data user berdasarkan ID
            username = user.username if user.username else f"@{user_id}"  # Username atau fallback ke user_id
            active_users.append(username)
        except Exception as e:
            active_users.append(f"@{user_id}")  # Jika terjadi error (misalnya bot tidak bisa mengambil data), fallback ke ID pengguna)

    if active_users:
        user_list = "\n".join(active_users)
        text = f"✅ Orang yang masih izin:\n{user_list}"
    else:
        text = "⚠️ Tidak ada yang sedang izin saat ini."

    # Mendapatkan message_id dari pesan yang diterima
    message_id = update.message.message_id

    await safe_send_message(context, update.message.chat.id, text, message_id)


# Command /reset_data
async def reset_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in admin_ids:
        return await safe_send_message(context, update.message.chat.id, "⚠️ Hanya admin yang bisa menggunakan perintah ini.", update.message.message_id)

    user_timers.clear()
    user_activities.clear()
    user_izin_counts.clear()
    await safe_send_message(context, update.message.chat.id, "✅ Semua data telah direset.")

# Command /set_batas
async def set_batas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in admin_ids:
        return await safe_send_message(context, update.message.chat.id, "⚠️ Hanya admin yang bisa menggunakan perintah ini.", update.message.message_id)

    if context.args:
        izin_type = context.args[0]
        try:
            limit = int(context.args[1])
            daily_limit[izin_type] = limit
            await safe_send_message(context, update.message.chat.id, f"✅ Batas izin {izin_type} diubah menjadi {limit} per hari.")
        except (ValueError, IndexError):
            await safe_send_message(context, update.message.chat.id, "⚠️ Format perintah salah. Gunakan: /set_batas <izin_type> <limit>")
    else:
        await safe_send_message(context, update.message.chat.id, "⚠️ Mohon masukkan tipe izin dan batasnya.")

# Fungsi untuk memulai timer
async def timer_task(duration, chat_id, user_id, context, reason, message_id):
    try:
        await asyncio.sleep(duration * 60)
        await safe_send_message(context, chat_id, f"⏰ {reason} selesai otomatis setelah {duration} menit.", message_id)
    except asyncio.CancelledError:
        return
    finally:
        if user_id in user_timers:
            del user_timers[user_id]

# Jika izin tanpa waktu (misalnya BAB)
async def wait_indefinitely(user_id):
    try:
        while True:
            await asyncio.sleep(60)
    except asyncio.CancelledError:
        return

# Safe send message with error handling
async def safe_send_message(context, chat_id, text, message_id):
    try:
        await context.bot.send_message(chat_id=chat_id, text=text, reply_to_message_id=message_id)
    except Exception as e:
        print(f"Error sending message: {e}")

# === Jalankan Bot ===
if __name__ == "__main__":
    app = ApplicationBuilder().token('7928886857:AAHxlgToMCO78SRCjasdNroboOTyd7xVyYc').build()

    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(CommandHandler("rekap", rekap))
    app.add_handler(CommandHandler("siapa_izin", siapa_izin))
    app.add_handler(CommandHandler("reset_data", reset_data))
    app.add_handler(CommandHandler("set_batas", set_batas))

    print("Bot aktif... Menunggu pesan...")
    app.run_polling()
