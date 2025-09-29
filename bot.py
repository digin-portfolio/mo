# bot.py
import os
import json
import difflib
import requests
from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Environment variables (set on Render)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
REQUEST_GROUP_ID = int(os.environ.get("REQUEST_GROUP_ID", "0"))
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "0"))
TMDB_KEY = os.environ.get("TMDB_KEY")  # optional for posters

bot = TeleBot(BOT_TOKEN)

# Load or create movies.json
try:
    with open("movies.json", "r", encoding="utf-8") as f:
        movies = json.load(f)
except:
    movies = {}

# --- Helper functions ---
def get_movie_info_from_tmdb(query):
    if not TMDB_KEY:
        return None
    url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_KEY}&query={requests.utils.requote_uri(query)}"
    resp = requests.get(url, timeout=10).json()
    if resp.get("results"):
        movie = resp["results"][0]
        title = movie.get("title") or query
        year = (movie.get("release_date") or "")[:4]
        poster_path = movie.get("poster_path")
        poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None
        if year:
            title = f"{title} ({year})"
        return title, poster_url
    return None

def get_download_keyboard(movie_key):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("⬇️ Download", callback_data=f"download::{movie_key}"))
    return kb

# --- Handle new uploads in private channel ---
@bot.channel_post_handler(content_types=['document'])
def handle_new_movie(message):
    if message.chat.id != CHANNEL_ID:
        return
    file_id = message.document.file_id
    movie_name = message.document.file_name.rsplit(".", 1)[0]
    movies[movie_name] = file_id
    with open("movies.json", "w", encoding="utf-8") as f:
        json.dump(movies, f, ensure_ascii=False, indent=2)
    print(f"Added: {movie_name} -> {file_id}")

# --- Handle requests in group ---
@bot.message_handler(func=lambda m: m.chat.id == REQUEST_GROUP_ID and isinstance(m.text, str))
def handle_request_message(message):
    text = message.text.strip()
    if not text.lower().startswith("request:"):
        return
    query = text[len("request:"):].strip()
    if not query:
        bot.reply_to(message, "Please write: `Request: Movie Name`", parse_mode='Markdown')
        return

    matches = [k for k in movies.keys() if query.lower() in k.lower()]
    if not matches:
        matches = difflib.get_close_matches(query, movies.keys(), n=3, cutoff=0.4)
    if not matches:
        bot.reply_to(message, "❌ Movie not found.")
        return

    for mk in matches[:3]:
        tmdb = get_movie_info_from_tmdb(mk)
        caption = mk
        photo = None
        if tmdb:
            caption, photo = tmdb
        try:
            if photo:
                bot.send_photo(chat_id=message.chat.id, photo=photo, caption=caption, reply_markup=get_download_keyboard(mk))
            else:
                bot.send_message(chat_id=message.chat.id, text=caption, reply_markup=get_download_keyboard(mk))
        except:
            bot.send_message(chat_id=message.chat.id, text=caption + "\n(Poster unavailable)", reply_markup=get_download_keyboard(mk))

# --- Handle Download button ---
@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("download::"))
def handle_download_callback(call):
    movie_key = call.data.split("::", 1)[1]
    file_id = movies.get(movie_key)
    if not file_id:
        bot.answer_callback_query(call.id, "❌ File not found.")
        return
    user_id = call.from_user.id
    try:
        bot.send_message(user_id, f"Sending: {movie_key}\nIf you don't get it, open a chat with the bot and press Start: t.me/{bot.get_me().username}")
        bot.send_document(user_id, file_id)
        bot.answer_callback_query(call.id, "✅ Sent to your DM!")
    except:
        bot.answer_callback_query(call.id, "❌ Can't send. Start a chat with the bot first: t.me/{}".format(bot.get_me().username))

# --- Start bot ---
if __name__ == "__main__":
    print("Bot is starting...")
    bot.polling(none_stop=True, interval=0, timeout=20)
