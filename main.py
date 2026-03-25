import os, requests, time, io
import telebot
from telebot import types
from flask import Flask
from threading import Thread

# --- Flask Server Setup ---
app = Flask(__name__)
@app.route('/')
def home(): return "NexFlix Private Gen is Active!"

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

# --- TMDB API Logic (Fixed for Multi-Search) ---
def get_tmdb_data(q):
    # 'multi' এন্ডপয়েন্ট মুভি এবং টিভি সিরিজ দুটোই খুঁজবে
    search_url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={q}"
    try:
        res = requests.get(search_url).json()
        if not res.get('results'): return None
        
        # 'person' (অ্যাক্টর) স্কিপ করে প্রথম মুভি বা টিভি সিরিজ বের করা
        item = next((x for x in res['results'] if x['media_type'] in ['movie', 'tv']), None)
        if not item: return None
        
        media_type = item['media_type'] # 'movie' নাকি 'tv'
        item_id = item['id']
        
        # ডিটেইলস ফেচ করা (মুভি বা টিভির ওপর ভিত্তি করে)
        detail_url = f"https://api.themoviedb.org/3/{media_type}/{item_id}?api_key={TMDB_API_KEY}&language=en-US"
        details = requests.get(detail_url).json()
        
        # টাইটেল এবং রিলিজ ডেট (মুভি এবং টিভির কি-ওয়ার্ড আলাদা হয়)
        title = details.get('title') if media_type == 'movie' else details.get('name', 'N/A')
        date = details.get('release_date') if media_type == 'movie' else details.get('first_air_date', 'N/A')
        
        # রানটাইম ফিক্স
        if media_type == 'movie':
            runtime = str(details.get('runtime', 'N/A')) + " mins"
        else:
            runtimes = details.get('episode_run_time', [])
            runtime = f"{runtimes[0]} mins/ep" if runtimes else "N/A"
            
        genres = ", ".join([g['name'] for g in details.get('genres', [])])
        studios = details.get('production_companies', [])
        studio = studios[0]['name'] if studios else 'N/A'
        
        poster_path = details.get('poster_path')
        poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None
        
        return {
            "type": media_type.upper(), # MOVIE or TV
            "title": title,
            "date": date,
            "runtime": runtime,
            "rating": round(details.get('vote_average', 0.0), 1),
            "votes": details.get('vote_count', '0'),
            "genres": genres,
            "studio": studio,
            "overview": details.get('overview', 'No description available.'),
            "poster": poster_url,
            # টিভি সিরিজের জন্য স্পেশাল ডাটা
            "seasons": details.get('number_of_seasons', 'N/A') if media_type == 'tv' else None,
            "episodes": details.get('number_of_episodes', 'N/A') if media_type == 'tv' else None
        }
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

# --- Telegram Handlers ---
@bot.message_handler(commands=['start'])
def start(m):
    if m.from_user.id != ADMIN_ID:
        return bot.reply_to(m, "❌ *অ্যাক্সেস ডিনাইড!*\nএই বটটি ব্যক্তিগত ব্যবহারের জন্য।", parse_mode="Markdown")
    bot.reply_to(m, "🎬 *Welcome Admin!*\nমুভি বা সিরিজের নাম লিখে মেসেজ দিন, আমি ডিটেইলস দিচ্ছি।", parse_mode="Markdown")

@bot.message_handler(func=lambda m: True)
def generate_post(m):
    if m.from_user.id != ADMIN_ID: return

    query = m.text.strip()
    if len(query) < 2: return
    
    status_msg = bot.reply_to(m, "⏳ *তথ্য ও ইমেজ সংগ্রহ করা হচ্ছে...*")
    data = get_tmdb_data(query)
    
    if not data:
        return bot.edit_message_text("😔 কন্টেন্টটি TMDB-তে পাওয়া যায়নি!", m.chat.id, status_msg.message_id)

    overview = data['overview'][:450] + "..." if len(data['overview']) > 450 else data['overview']
    
    # আইকন এবং ক্যাপশন সেটআপ (ক্যাটাগরি অনুযায়ী)
    icon = "🎬" if data['type'] == "MOVIE" else "📺"
    
    caption = f"{icon} *{data['title'].upper()}* [{data['type']}]\n\n"
    caption += f"📅 *First Air/Release:* {data['date']}\n"
    
    if data['type'] == 'TV':
        caption += f"🎞️ *Seasons:* {data['seasons']}\n"
        caption += f"🔢 *Episodes:* {data['episodes']}\n"
        
    caption += f"⏳ *Duration:* {data['runtime']}\n"
    caption += f"⭐ *Rating:* {data['rating']} ({data['votes']} votes)\n"
    caption += f"🎭 *Genres:* {data['genres']}\n"
    caption += f"🏢 *Studio:* {data['studio']}\n"
    caption += f"🌐 *Languages:* English / Hindi\n\n"
    caption += f"📝 *Overview:*\n{overview}"
    
    try:
        bot.delete_message(m.chat.id, status_msg.message_id)
        if data['poster']:
            photo_res = requests.get(data['poster'])
            if photo_res.status_code == 200:
                bot.send_photo(m.chat.id, io.BytesIO(photo_res.content), caption=caption, parse_mode="Markdown")
            else: 
                bot.send_message(m.chat.id, caption, parse_mode="Markdown")
        else: 
            bot.send_message(m.chat.id, caption, parse_mode="Markdown")
    except:
        bot.send_message(m.chat.id, caption + "\n\n⚠️ _ইমেজ লোড করা যায়নি!_", parse_mode="Markdown")

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
        
