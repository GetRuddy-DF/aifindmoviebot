import asyncio
import random
import os
import re
import requests
from datetime import date

from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.filters import Command

from dotenv import load_dotenv
from openai import OpenAI


# ================= ENV =================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TMDB_KEY = os.getenv("TMDB_KEY")


# ================= BOT =================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
client = OpenAI(api_key=OPENAI_API_KEY)


# ================= KEYBOARD =================
keyboard = ReplyKeyboardBuilder()
keyboard.row(
    KeyboardButton(text="🎬 Угадай фильм"),
    KeyboardButton(text="🎯 Фильм на вечер")
)
keyboard.row(
    KeyboardButton(text="🌟 Фильм дня"),
    KeyboardButton(text="ℹ️ Информация о боте")
)


# ================= UTILS =================
def clean_movie_title(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\(.*?\)", "", text)
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return text.strip()


def detect_language(text: str) -> str:
    if re.search(r"[а-яА-Я]", text):
        return "ru"
    return "en"


def movie_keyboard(movie_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="▶ Трейлер",
                    callback_data=f"trailer:{movie_id}"
                ),
                InlineKeyboardButton(
                    text="🔁 Похожие",
                    callback_data=f"similar:{movie_id}"
                ),
            ]
        ]
    )


# ================= CARD =================
async def send_movie_card(
    message: types.Message,
    movie: dict,
    prefix: str = "",
    lang: str = "ru"
):
    movie_id = movie.get("id")
    title = movie.get("title", "No title" if lang == "en" else "Без названия")
    rating = movie.get("vote_average", "—")
    overview = movie.get("overview") or ("No description available" if lang == "en" else "Описание отсутствует")
    poster = movie.get("poster_path")

    rating_label = "Rating" if lang == "en" else "Рейтинг"

    caption = (
        f"{prefix}*{title}*\n"
        f"⭐ {rating_label}: {rating}\n\n"
        f"{overview}"
    )

    markup = movie_keyboard(movie_id)

    if poster:
        await message.answer_photo(
            photo=f"https://image.tmdb.org/t/p/w500{poster}",
            caption=caption,
            parse_mode="Markdown",
            reply_markup=markup
        )
    else:
        await message.answer(
            caption,
            parse_mode="Markdown",
            reply_markup=markup
        )


# ================= TMDB =================
def get_trailer_url(movie_id: int):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}/videos"
    params = {"api_key": TMDB_KEY}

    data = requests.get(url, params=params).json()
    videos = data.get("results", [])

    # 🇷🇺 Русский
    for v in videos:
        if (
            v.get("site") == "YouTube"
            and v.get("type") == "Trailer"
            and v.get("iso_639_1") == "ru"
        ):
            return "ru", f"https://www.youtube.com/watch?v={v.get('key')}"

    # 🇺🇸 Английский
    for v in videos:
        if (
            v.get("site") == "YouTube"
            and v.get("type") == "Trailer"
        ):
            return "en", f"https://www.youtube.com/watch?v={v.get('key')}"

    return None, None


def get_similar_movies(movie_id: int, limit: int = 5, tmdb_lang: str = "ru-RU"):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}/similar"
    params = {
        "api_key": TMDB_KEY,
        "language": tmdb_lang
    }

    data = requests.get(url, params=params).json()
    return data.get("results", [])[:limit]


def get_evening_movie(tmdb_lang: str = "ru-RU"):
    data = requests.get(
        "https://api.themoviedb.org/3/discover/movie",
        params={
            "api_key": TMDB_KEY,
            "language": tmdb_lang,
            "sort_by": "popularity.desc",
            "vote_average.gte": 7,
        }
    ).json()

    results = data.get("results", [])
    return random.choice(results)


def get_movie_of_the_day(tmdb_lang: str = "ru-RU"):
    data = requests.get(
        "https://api.themoviedb.org/3/trending/movie/day",
        params={
            "api_key": TMDB_KEY,
            "language": tmdb_lang
        }
    ).json()

    movies = data.get("results", [])
    return movies[date.today().toordinal() % len(movies)] if movies else None


# ================= HANDLERS =================
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "🎉 Привет! Я помогу найти фильм 🎥\n"
        "Опиши фильм или выбери действие ниже 👇",
        reply_markup=keyboard.as_markup(resize_keyboard=True)
    )


@dp.message()
async def process_message(message: types.Message):
    lang = detect_language(message.text)
    tmdb_lang = "ru-RU" if lang == "ru" else "en-US"

    if message.text == "🎬 Угадай фильм":
        await message.answer("Опиши фильм, который ты ищешь 🎬")
        return

    elif message.text == "🎯 Фильм на вечер":
        movie = get_evening_movie(tmdb_lang)
        if movie:
            await send_movie_card(message, movie, "🎯 *Фильм на вечер*\n\n", lang)
        else:
            await message.answer("😔 Не удалось подобрать фильм")
        return

    elif message.text == "🌟 Фильм дня":
        movie = get_movie_of_the_day(tmdb_lang)
        if movie:
            await send_movie_card(message, movie, "🌟 *Фильм дня*\n\n", lang)
        else:
            await message.answer("😔 Сегодня без фильма дня")
        return

    elif message.text == "ℹ️ Информация о боте":
        await message.answer(
            "🤖 Я бот, который:\n"
            "• угадывает фильмы по описанию\n"
            "• показывает постеры и трейлеры\n"
            "• рекомендует фильмы 🎬"
        )
        return

    await find_movie(message)


async def find_movie(message: types.Message):
    lang = detect_language(message.text)
    tmdb_lang = "ru-RU" if lang == "ru" else "en-US"

    searching_msg = "🔎 Думаю... ищу фильм..." if lang == "ru" else "🔎 Thinking... searching for a movie..."
    await message.answer(searching_msg)

    gpt_response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "Write ONLY the original English movie title. No year. No explanation."
            },
            {"role": "user", "content": message.text}
        ]
    )

    raw_guess = gpt_response.choices[0].message.content.strip()
    query = clean_movie_title(raw_guess)

    if not query:
        await message.answer("😔 Couldn't identify the movie" if lang == "en" else "😔 Не понял фильм")
        return

    search = requests.get(
        "https://api.themoviedb.org/3/search/movie",
        params={
            "api_key": TMDB_KEY,
            "query": query,
            "language": tmdb_lang
        }
    ).json()

    results = search.get("results", [])

    if not results:
        msg = f"😔 Movie not found.\nMy guess: *{raw_guess}*" if lang == "en" else f"😔 Не нашёл фильм.\nМой вариант: *{raw_guess}*"
        await message.answer(msg, parse_mode="Markdown")
        return

    movie = max(results, key=lambda x: x.get("popularity", 0))
    await send_movie_card(message, movie, lang=lang)


# ================= CALLBACKS =================
@dp.callback_query()
async def handle_callbacks(callback: types.CallbackQuery):
    data = callback.data

    if data.startswith("trailer:"):
        movie_id = int(data.split(":")[1])
        lang, url = get_trailer_url(movie_id)

        if url:
            label = "🇷🇺 Русский трейлер" if lang == "ru" else "🇺🇸 Оригинальный трейлер"
            await callback.message.answer(f"{label}\n{url}")
        else:
            await callback.message.answer("😔 Трейлер не найден")

    elif data.startswith("similar:"):
        movie_id = int(data.split(":")[1])
        movies = get_similar_movies(movie_id)

        if not movies:
            await callback.message.answer("😔 Похожие фильмы не найдены")
            return

        text = "🔁 *Похожие фильмы:*\n\n"
        for m in movies:
            text += f"🎬 {m.get('title')} — ⭐ {m.get('vote_average', '—')}\n"

        await callback.message.answer(text, parse_mode="Markdown")


# ================= RUN =================
async def main():
    print("✅ Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
