import telebot, os, requests, time
from telebot import types
from flask import Flask
from threading import Thread

# --- Flask Server Setup ---
app = Flask(__name__)

@app.route('/')
def home():
    return "NexFlix Post Generator is Active!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    Thread(target=run).start()

# --- Config (Render-এর Environment Variables থেকে নিবে) ---
API_TOKEN = os.getenv('API_TOKEN')
TMDB_API_KEY = os.getenv('TMDB_API_KEY')

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
            "title": movie.get('title', 'N/A'),
            "date": movie.get('release_date', 'N/A'),
            "runtime": movie.get('runtime', 'N/A'),
            "rating": movie.get('vote_average', '0.0'),
            "votes": movie.get('vote_count', '0'),
            "genres": genres,
            "studio": movie.get('production_companies', [{'name': 'N/A'}])[0]['name'],
            "overview": movie.get('overview', 'No description available.')
        }
    except Exception as e:
        print(f"TMDB API Error: {e}")
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

    # ক্যাপশন ১০০০ অক্ষরের মধ্যে রাখা হয়েছে যাতে টেলিগ্রাম রিজেক্ট না করে
    overview = movie['overview'][:450] + "..." if len(movie['overview']) > 450 else movie['overview']

    caption = (
        f"🎬 *{movie['title'].upper()}*\n\n"
        f"📅 *Release:* {movie['date']}\n"
        f"⏳ *Duration:* {movie['runtime']} mins\n"
        f"⭐ *Rating:* {movie['rating']} ({movie['votes']} votes)\n"
        f"🎭 *Genres:* {movie['genres']}\n"
        f"🏢 *Studio:* {movie['studio']}\n"
        f"🌐 *Languages:* English / Hindi\n\n"
        f"📝 *Overview:*\n{overview}"
    )
    
    try:
        # স্ট্যাটাস মেসেজ ডিলিট করে ফ্রেশ পোস্ট পাঠানো
        bot.delete_message(m.chat.id, status_msg.message_id)
        
        if movie['poster']:
            # ফটো সহ পাঠানোর চেষ্টা
            bot.send_photo(m.chat.id, movie['poster'], caption=caption, parse_mode="Markdown")
        else:
            bot.send_message(m.chat.id, caption, parse_mode="Markdown")
            
    except Exception as e:
        # যদি কোনো কারণে ফটো পাঠাতে সমস্যা হয় (যেমন ইনভ্যালিড ইউআরএল), তবে শুধু টেক্সট পাঠাবে
        print(f"Telegram Post Error: {e}")
        bot.send_message(m.chat.id, caption + "\n\n⚠️ _ইমেজ লোড করা যায়নি, শুধু টেক্সট পাঠানো হলো।_", parse_mode="Markdown")

if __name__ == "__main__":
    keep_alive()
    print("Bot is starting...")
    bot.infinity_polling()
