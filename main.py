import telebot, os, requests, time
from telebot import types
from flask import Flask
from threading import Thread

# --- Flask Server Setup (Gunicorn-এর ঝামেলা এড়াতে) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "NexFlix Post Generator is Active!"

def run():
    # Render-এর ডাইনামিক পোর্ট হ্যান্ডেল করার জন্য
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    Thread(target=run).start()

# --- Config (Render-এর Environment Variables থেকে নিবে) ---
API_TOKEN = os.getenv('API_TOKEN')
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
ADMIN_ID = os.getenv('ADMIN_ID') # এটি অপশনাল এই বটের জন্য

bot = telebot.TeleBot(API_TOKEN)

# --- TMDB API Logic ---
def get_tmdb_data(q):
    search_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={q}"
    try:
        res = requests.get(search_url).json()
        if not res['results']: return None
        
        movie_id = res['results'][0]['id']
        detail_url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}&language=en-US"
        movie = requests.get(detail_url).json()
        
        genres = ", ".join([g['name'] for g in movie.get('genres', [])])
        poster = f"https://image.tmdb.org/t/p/w500{movie.get('poster_path')}" if movie.get('poster_path') else None
        
        return {
            "title": movie.get('title'),
            "date": movie.get('release_date', 'N/A'),
            "runtime": movie.get('runtime', 'N/A'),
            "rating": movie.get('vote_average', '0.0'),
            "votes": movie.get('vote_count', '0'),
            "genres": genres,
            "studio": movie.get('production_companies', [{'name': 'N/A'}])[0]['name'],
            "overview": movie.get('overview', 'No description available.')
        }
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

# --- Telegram Handlers ---
@bot.message_handler(commands=['start'])
def start(m):
    welcome_text = "🎬 *NexFlix Instant Post Generator*\n\nযেকোনো মুভির নাম লিখে মেসেজ দিন, আমি সাথে সাথে পোস্টারসহ ডিটেইলস পোস্ট তৈরি করে দেব।"
    bot.reply_to(m, welcome_text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: True)
def generate_post(m):
    query = m.text.strip()
    if len(query) < 2: return
    
    status_msg = bot.reply_to(m, "⏳ *অপেক্ষা করুন...* তথ্য সংগ্রহ করা হচ্ছে।", parse_mode="Markdown")
    movie = get_tmdb_data(query)
    
    if not movie:
        return bot.edit_message_text("😔 দুঃখিত! মুভিটি পাওয়া যায়নি।", m.chat.id, status_msg.message_id)

    # আপনার স্ক্রিনশটের স্টাইল অনুযায়ী সাজানো ক্যাপশন
    caption = (
        f"🎬 *{movie['title'].upper()}*\n\n"
        f"📅 *Release:* {movie['date']}\n"
        f"⏳ *Duration:* {movie['runtime']} mins\n"
        f"⭐ *Rating:* {movie['rating']} ({movie['votes']} votes)\n"
        f"🎭 *Genres:* {movie['genres']}\n"
        f"🏢 *Studio:* {movie['studio']}\n"
        f"🌐 *Languages:* English / Hindi\n\n"
        f"📝 *Overview:*\n{movie['overview'][:450]}..."
    )
    
    try:
        bot.delete_message(m.chat.id, status_msg.message_id)
        if movie['poster']:
            bot.send_photo(m.chat.id, movie['poster'], caption=caption, parse_mode="Markdown")
        else:
            bot.send_message(m.chat.id, caption, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(m.chat.id, "⚠️ পোস্ট পাঠাতে সমস্যা হয়েছে!")

if __name__ == "__main__":
    keep_alive()
    print("Bot is starting...")
    bot.infinity_polling()
        
