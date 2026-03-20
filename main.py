import telebot, os, requests, time
from telebot import types
from flask import Flask
from threading import Thread

# --- Render Environment Variables (এগুলো হাইড থাকবে) ---
API_TOKEN = os.getenv('API_TOKEN')
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

bot = telebot.TeleBot(API_TOKEN)

# --- Flask Server (Render Keep Alive) ---
app = Flask('')
@app.route('/')
def home(): return "Post Generator is Secure & Active!"

def run():
    # Render সাধারণত ৮0৮0 বা ১0000 পোর্ট ব্যবহার করে
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    Thread(target=run).start()

# --- TMDB Logic ---
def get_tmdb_data(q):
    search_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={q}"
    try:
        res = requests.get(search_url).json()
        if not res['results']: return None
        
        movie_id = res['results'][0]['id']
        detail_url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}"
        movie = requests.get(detail_url).json()
        
        genres = ", ".join([g['name'] for g in movie.get('genres', [])])
        poster = f"https://image.tmdb.org/t/p/w500{movie.get('poster_path')}" if movie.get('poster_path') else None
        
        return {
            "title": movie.get('title'),
            "date": movie.get('release_date'),
            "runtime": movie.get('runtime', 'N/A'),
            "rating": movie.get('vote_average', '0.0'),
            "votes": movie.get('vote_count', '0'),
            "genres": genres,
            "overview": movie.get('overview'),
            "poster": poster
        }
    except:
        return None

# --- Handlers ---
@bot.message_handler(commands=['start'])
def start(m):
    bot.reply_to(m, "🎬 *NexFlix Post Generator*\nমুভির নাম লিখে মেসেজ দিন।", parse_mode="Markdown")

@bot.message_handler(func=lambda m: True)
def generate(m):
    q = m.text.strip()
    if len(q) < 2: return
    
    status = bot.reply_to(m, "⏳ *তথ্য সংগ্রহ করা হচ্ছে...*")
    movie = get_tmdb_data(q)
    
    if not movie:
        return bot.edit_message_text("😔 মুভিটি পাওয়া যায়নি!", m.chat.id, status.message_id)

    caption = (
        f"🎬 *{movie['title']}*\n"
        f"📅 *Release:* {movie['date']}\n"
        f"⏳ *Duration:* {movie['runtime']} mins\n"
        f"⭐ *Rating:* {movie['rating']} ({movie['votes']} votes)\n"
        f"🎭 *Genres:* {movie['genres']}\n"
        f"🏢 *Studio:* Jio Studios\n"
        f"🌐 *Languages:* Hindi\n\n"
        f"📝 *Overview:*\n{movie['overview'][:500]}..." 
    )
    
    bot.delete_message(m.chat.id, status.message_id)
    
    if movie['poster']:
        bot.send_photo(m.chat.id, movie['poster'], caption=caption, parse_mode="Markdown")
    else:
        bot.send_message(m.chat.id, caption, parse_mode="Markdown")

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
    
