print("Код начал выполняться")  # отладка уровня 1

import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, FSInputFile, InputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from PIL import Image, ImageOps
import os

# === НАСТРОЙКИ ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
FRAME_PATH = "templates/frame.png"  # рамка (PNG с прозрачностью)
DB_PATH = "posts.db"

# === Клавиатура с кнопкой "Старт" ===
start_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Старт")]],
    resize_keyboard=True,
    one_time_keyboard=True
)

# === FSM Состояния ===
class PostForm(StatesGroup):
    waiting_for_photo = State()
    waiting_for_job_type = State()
    waiting_for_key_type = State()
    waiting_for_car = State()
    waiting_for_description = State()  # Для описания работ
    waiting_for_price = State()        # Для ввода цены
    waiting_for_location = State()

# === КНОПКИ для выбора типа работы и локации ===
job_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Ремонт"), KeyboardButton(text="Изготовление")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

locations = {
    "Загородное шоссе 36/1 ТЦ ЛЕНТА": "46-80-99",
    "Рокоссовского 2 ТЦ ЛЕНТА": "45-52-04",
    "Чкалова 51 ТЦ ЛЕНТА": "95-77-71",
    "Чичерина 2 ТЦ ЛЮБИМЫЙ": "94-05-60"
}

location_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=addr)] for addr in locations.keys()],
    resize_keyboard=True,
    one_time_keyboard=True
)

# === ИНИЦИАЛИЗАЦИЯ БОТА ===
print("Инициализация бота...")  # отладка уровня 2
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# === БАЗА ДАННЫХ ===
def init_db():
    print("Создание/проверка базы данных...")  # отладка уровня 3
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_path TEXT,
            job_type TEXT,
            key_type TEXT,
            car TEXT,
            description TEXT,
            price TEXT,
            location TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

# === ХЭНДЛЕРЫ ===

# Обработчик команды /start – сбрасывает состояние и отправляет рекомендации для создания поста.
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.set_state(PostForm.waiting_for_photo)
    await message.answer(
        "📸 Рекомендации для фото:\n"
        "✅ Снимай горизонтально (альбомный режим)\n"
        "✅ Включи сетку в настройках камеры\n"
        "✅ Используй 1x зум (широкоугольный)\n"
        "✅ Заполняй кадр — объект по центру и без пустот\n\n"
        "Теперь отправь фото или видео для поста."
    )

# Обработчик кнопки "Старт". Если пользователь нажимает "Старт", сбрасываем состояние и запускаем процесс.
@router.message(lambda message: message.text and message.text.lower() == "старт")
async def start_button_handler(message: Message, state: FSMContext):
    await state.clear()
    await cmd_start(message, state)

# (Дефолтный обработчик входящих текстовых сообщений удалён,
# чтобы текстовые ответы обрабатывались только через FSM-хендлеры.)

@router.message(PostForm.waiting_for_photo, F.photo | F.video)
async def handle_media(message: Message, state: FSMContext):
    try:
        if message.photo:
            file = await bot.get_file(message.photo[-1].file_id)
            file_path = f"user_data/{message.photo[-1].file_unique_id}.jpg"
            await asyncio.wait_for(bot.download_file(file.file_path, destination=file_path), timeout=30)
            media_type = "photo"
        elif message.video:
            if message.video.duration > 15:
                await message.answer("Видео должно быть не длиннее 15 секунд. Пожалуйста, сократи его и отправь снова.")
                return
            file = await bot.get_file(message.video.file_id)
            file_path = f"user_data/{message.video.file_unique_id}.mp4"
            await asyncio.wait_for(bot.download_file(file.file_path, destination=file_path), timeout=30)
    
            # Загружаем превью как картинку (если есть)
            thumb_path = f"user_data/{message.video.file_unique_id}_thumb.jpg"
            if message.video.thumbnail:
                thumb_file = await bot.get_file(message.video.thumbnail.file_id)
                await asyncio.wait_for(bot.download_file(thumb_file.file_path, destination=thumb_path), timeout=30)
                media_type = "video"
            else:
                await message.answer("Видео без превью не поддерживается. Прикрепи короткое видео с обложкой.")
                return
        else:
            await message.answer("Пожалуйста, отправь фото или видео")
            return
    
        await state.update_data(media_path=file_path, media_type=media_type,
                                  thumb_path=thumb_path if message.video else None)
        await state.set_state(PostForm.waiting_for_job_type)
        await message.answer("Выбери тип работы:", reply_markup=job_kb)
    except asyncio.TimeoutError:
        await message.answer("Ошибка: Таймаут при загрузке файла. Попробуйте ещё раз.")
    except Exception as e:
        await message.answer("Произошла ошибка при обработке вашего медиа. Попробуйте ещё раз.")
        print("Ошибка в handle_media:", e)
    
@router.message(PostForm.waiting_for_job_type)
async def handle_job_type(message: Message, state: FSMContext):
    await state.update_data(job_type=message.text)
    await state.set_state(PostForm.waiting_for_key_type)
    await message.answer("Какой тип ключа? (Например: выкидной, чип, смарт)")

@router.message(PostForm.waiting_for_key_type)
async def handle_key_type(message: Message, state: FSMContext):
    await state.update_data(key_type=message.text)
    await state.set_state(PostForm.waiting_for_car)
    await message.answer("Укажи марку авто")

@router.message(PostForm.waiting_for_car)
async def handle_car(message: Message, state: FSMContext):
    await state.update_data(car=message.text)
    await state.set_state(PostForm.waiting_for_description)
    await message.answer("Кратко опиши, какие работы были выполнены (например: изготовление, замена корпуса, перепайка и т.п.)")

@router.message(PostForm.waiting_for_description)
async def handle_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(PostForm.waiting_for_price)
    await message.answer("Укажи цену работы")

@router.message(PostForm.waiting_for_price)
async def handle_price(message: Message, state: FSMContext):
    await state.update_data(price=message.text)
    await state.set_state(PostForm.waiting_for_location)
    await message.answer("Где выполнена работа?", reply_markup=location_kb)

@router.message(PostForm.waiting_for_location)
async def handle_location(message: Message, state: FSMContext):
    data = await state.get_data()
    media_path = data['media_path']
    media_type = data['media_type']
    thumb_path = data.get('thumb_path')
    job_type = data['job_type']
    key_type = data['key_type']
    car = data['car']
    description = data['description']
    price = data['price']
    location = message.text
    phone = locations.get(location, "")

    # Генерация обложки с рамкой (если фото или превью видео)
    if media_type == "photo":
        image = Image.open(media_path).convert("RGBA")
    else:
        image = Image.open(thumb_path).convert("RGBA")

    frame = Image.open(FRAME_PATH).convert("RGBA")
    frame_size = frame.size
    image.thumbnail((frame_size[0] - 100, frame_size[1] - 100), Image.Resampling.LANCZOS)

    bg = Image.new("RGBA", frame_size, (0, 0, 0, 0))
    offset = ((frame_size[0] - image.size[0]) // 2, (frame_size[1] - image.size[1]) // 2)
    bg.paste(image, offset)
    combined = Image.alpha_composite(bg, frame)

    final_image_path = media_path.replace(".jpg", "_framed.png").replace(".mp4", "_thumb.png")
    combined.save(final_image_path)

    caption = (
        f"🔧 Работа: {job_type}\n"
        f"🗝️ Ключ: {key_type}\n"
        f"🚘 Авто: {car}\n"
        f"📄 Описание: {description}\n"
        f"💰 Цена: {price}\n"
        f"📍 {location}\n"
        f"📞 Тел.: {phone}"
    )

    if media_type == "photo":
        await bot.send_photo(chat_id=CHANNEL_ID, photo=FSInputFile(final_image_path), caption=caption)
    else:
        video_file = FSInputFile(media_path)
        thumb_file = FSInputFile(final_image_path)
        await bot.send_video(chat_id=CHANNEL_ID, video=video_file, caption=caption, thumbnail=thumb_file)

    await message.answer("Пост отправлен в канал ✅")

    # Сохраняем данные в базе, включая описание работы
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO posts (photo_path, job_type, key_type, car, description, price, location)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (final_image_path, job_type, key_type, car, description, price, location))
    conn.commit()
    conn.close()

    await state.clear()

# === ЗАПУСК ===
if __name__ == "__main__":
    os.makedirs("user_data", exist_ok=True)
    print("Бот запускается... Ожидаем ввода команды /start или нажатия кнопки 'Старт'")
    asyncio.run(dp.start_polling(bot))
