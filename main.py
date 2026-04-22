import os, requests, time, io
import telebot
from telebot import types
from flask import Flask
from threading import Thread

# --- Flask Server Setup ---
app = Flask(__name__)
@app.route('/')
def home(): return "NexFlix Pro Bot is Active!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    Thread(target=run).start()

# --- Config ---
API_TOKEN = os.getenv('API_TOKEN')
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
ADMIN_ID = 7414830213 # আপনার আইডি

bot = telebot.TeleBot(API_TOKEN)

# ল্যাঙ্গুয়েজ কোডকে পূর্ণ নামে রূপান্তর করার ডিকশনারি
LANG_MAP = {'en': 'English', 'hi': 'Hindi', 'ko': 'Korean', 'ja': 'Japanese', 'ta': 'Tamil', 'te': 'Telugu', 'bn': 'Bengali', 'es': 'Spanish', 'fr': 'French'}

# --- TMDB Multi-Search logic ---
def search_tmdb(query, page=1):
    url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={query}&language=en-US&page={page}"
    try:
        res = requests.get(url).json()
        results = []
        if not res.get('results'): return [], 0
        
        for item in res['results']:
            if item.get('media_type') in ['movie', 'tv']:
                title = item.get('title') or item.get('name')
                date = item.get('release_date') or item.get('first_air_date') or "N/A"
                year = date.split("-")[0] if date != "N/A" else "N/A"
                results.append({
                    "id": item['id'],
                    "title": title,
                    "year": year,
                    "type": item['media_type']
                })
        return results, res.get('total_pages', 1)
    except Exception as e:
        print(f"Search Error: {e}")
        return [], 0

def get_detailed_data(item_id, media_type):
    url = f"https://api.themoviedb.org/3/{media_type}/{item_id}?api_key={TMDB_API_KEY}&language=en-US"
    try:
        details = requests.get(url).json()
        title = details.get('title') if media_type == 'movie' else details.get('name', 'N/A')
        date = details.get('release_date') if media_type == 'movie' else details.get('first_air_date', 'N/A')
        
        # ল্যাঙ্গুয়েজ ডিটেকশন
        lang_code = details.get('original_language', 'N/A')
        language = LANG_MAP.get(lang_code, lang_code.upper())

        if media_type == 'movie':
            runtime = f"{details.get('runtime', 'N/A')} mins"
        else:
            runtimes = details.get('episode_run_time', [])
            runtime = f"{runtimes[0]} mins/ep" if runtimes else "N/A"
            
        genres = ", ".join([g['name'] for g in details.get('genres', [])])
        studios = details.get('production_companies', [])
        studio = studios[0]['name'] if studios else 'N/A'
        
        poster_path = details.get('poster_path')
        poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None
        
        return {
            "type": media_type.upper(),
            "title": title,
            "date": date,
            "runtime": runtime,
            "language": language,
            "rating": round(details.get('vote_average', 0.0), 1),
            "votes": details.get('vote_count', '0'),
            "genres": genres,
            "studio": studio,
            "overview": details.get('overview', 'No description available.'),
            "poster": poster_url,
            "seasons": details.get('number_of_seasons', 'N/A') if media_type == 'tv' else None,
            "episodes": details.get('number_of_episodes', 'N/A') if media_type == 'tv' else None
        }
    except Exception as e:
        print(f"Detail Fetch Error: {e}")
        return None

# --- Telegram Handlers ---
@bot.message_handler(commands=['start'])
def start(m):
    if m.from_user.id != ADMIN_ID: return
    bot.reply_to(m, "🎬 *Search System Active!*\nমুভি বা সিরিজের নাম লিখুন।", parse_mode="Markdown")

@bot.message_handler(func=lambda m: True)
def handle_search(m):
    if m.from_user.id != ADMIN_ID: return
    send_search_results(m.chat.id, m.text.strip(), 1)

def send_search_results(chat_id, query, page, message_id=None):
    results, total_pages = search_tmdb(query, page)
    if not results:
        if message_id: bot.edit_message_text("😔 কোনো রেজাল্ট পাওয়া যায়নি!", chat_id, message_id)
        else: bot.send_message(chat_id, "😔 কোনো রেজাল্ট পাওয়া যায়নি!")
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for item in results:
        icon = "🔴" if item['type'] == 'movie' else "🔵"
        btn_text = f"{icon} {item['title']} ({item['year']})"
        callback_data = f"info|{item['type']}|{item['id']}|{query}|{page}"
        markup.add(types.InlineKeyboardButton(text=btn_text, callback_data=callback_data))
    
    # Pagination Buttons
    nav_btns = []
    if page > 1:
        nav_btns.append(types.InlineKeyboardButton("⬅️ Back", callback_data=f"page|{query}|{page-1}"))
    if page < total_pages:
        nav_btns.append(types.InlineKeyboardButton("Next ➡️", callback_data=f"page|{query}|{page+1}"))
    if nav_btns: markup.row(*nav_btns)

    text = f"🔍 *Results for:* `{query}`\n📄 *Page:* {page}/{total_pages}"
    if message_id:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('page|'))
def callback_pagination(call):
    _, query, page = call.data.split('|')
    send_search_results(call.message.chat.id, query, int(page), call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('info|'))
def callback_info(call):
    _, media_type, item_id, query, page = call.data.split('|')
    bot.answer_callback_query(call.id, "তথ্য সংগ্রহ করা হচ্ছে...")
    
    data = get_detailed_data(item_id, media_type)
    if not data: return

    overview = data['overview'][:450] + "..." if len(data['overview']) > 450 else data['overview']
    icon = "🎬" if data['type'] == "MOVIE" else "📺"
    
    caption = f"{icon} *{data['title'].upper()}* [{data['type']}]\n\n"
    caption += f"📅 *Release:* {data['date']}\n"
    if data['type'] == 'TV':
        caption += f"🎞️ *Seasons:* {data['seasons']} | 🔢 *Episodes:* {data['episodes']}\n"
    caption += f"⏳ *Duration:* {data['runtime']}\n"
    caption += f"🌐 *Language:* {data['language']}\n"
    caption += f"⭐ *Rating:* {data['rating']} ({data['votes']} votes)\n"
    caption += f"🎭 *Genres:* {data['genres']}\n"
    caption += f"🏢 *Studio:* {data['studio']}\n"
    caption += f"📝 *Overview:*\n{overview}"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Back to List", callback_data=f"page|{query}|{page}"))

    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
        if data['poster']:
            photo_res = requests.get(data['poster'])
            bot.send_photo(call.message.chat.id, io.BytesIO(photo_res.content), caption=caption, reply_markup=markup, parse_mode="Markdown")
        else:
            bot.send_message(call.message.chat.id, caption, reply_markup=markup, parse_mode="Markdown")
    except:
        bot.send_message(call.message.chat.id, caption, reply_markup=markup, parse_mode="Markdown")

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
        
