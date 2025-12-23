import os
import asyncio
import logging
import requests
import urllib.parse
import json

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler
)
from dotenv import load_dotenv

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

def get_api_url():
    if os.getenv("DOCKER_ENV", "").lower() == "true":
        logger.info("Running in Docker container, connecting to 'api:8000'")
        return "http://api:8000"

    env_api_url = os.getenv("API_URL")
    if env_api_url:
        logger.info(f"Using API_URL from env: {env_api_url}")
        return env_api_url.rstrip('/')

    logger.info("Running locally, using localhost")
    return "http://localhost:8000"

def get_website_url():
    web_url = os.getenv("WEB_URL")
    if web_url:
        return web_url.rstrip('/')

    return "http://5.129.215.111:8501"

API_URL = get_api_url()
BOT_TOKEN = os.getenv("BOT_TOKEN", "8510568874:AAE6SzEheVnaHpaoSyvURy3-4C0tblP17do")
WEBSITE_URL = get_website_url()

logger.info(f"=== MoodBoard Bot Configuration ===")
logger.info(f"API_URL: {API_URL}")
logger.info(f"WEBSITE_URL: {WEBSITE_URL}")
logger.info(f"BOT_TOKEN present: {bool(BOT_TOKEN)}")

if not BOT_TOKEN:
    logger.error("BOT_TOKEN not found! Check .env file or environment variables")
    exit(1)

(
    REGISTER_CONFIRM,
    BOARD_NAME,
    BOARD_DESC,
    BOARD_VISIBILITY,
    ADD_COLLABORATOR,
    DELETE_CONFIRM,
    ADD_CONTENT_TYPE,
    ADD_TEXT_CONTENT,
    ADD_FILE_CONTENT,
    EDIT_BOARD_NAME,
    EDIT_BOARD_DESC,
    REMOVE_COLLABORATOR_SELECT,
    REMOVE_COLLABORATOR_CONFIRM,
) = range(13)


async def call_api(endpoint, method="GET", data=None, params=None, max_retries=3):
    for attempt in range(max_retries):
        try:
            url = f"{API_URL}{endpoint}"
            logger.info(f"API Call {attempt + 1}/{max_retries}: {method} {url}")

            if data:
                logger.info(f"Request data (type: {type(data)}): {str(data)[:100]}...")
            logger.info(f"Request params: {params}")

            if params:
                clean_params = {k: v for k, v in params.items() if v is not None}
                if clean_params:
                    query_string = urllib.parse.urlencode(clean_params)
                    url = f"{url}?{query_string}"

            logger.info(f"Final URL: {method} {url}")

            timeout_config = (10, 30)
            headers = {}
            if method in ["POST", "PUT"] and data:
                headers["Content-Type"] = "application/json"

            response = None
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=timeout_config)
            elif method == "POST":
                response = requests.post(url, json=data, headers=headers, timeout=timeout_config)
            elif method == "PUT":
                response = requests.put(url, json=data, headers=headers, timeout=timeout_config)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers, timeout=timeout_config)
            else:
                return None, "Неподдерживаемый метод"

            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response body (first 500 chars): {response.text[:500]}")

            if response.status_code == 200:
                try:
                    result = response.json()
                    return result, None
                except:
                    return {"status": "success"}, None
            else:
                error_msg = f"API ошибка {response.status_code}"
                try:
                    error_data = response.json()
                    if "detail" in error_data:
                        error_msg = error_data["detail"]
                    elif "message" in error_data:
                        error_msg = error_data["message"]
                    elif "error" in error_data:
                        error_msg = error_data["error"]
                except:
                    error_msg = response.text[:200]

                logger.error(f"API error: {error_msg}")

                if response.status_code in [400, 401, 403, 404]:
                    return None, error_msg

                if attempt < max_retries - 1:
                    wait_time = 2 * (attempt + 1)
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                    continue

                return None, error_msg

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {str(e)}")
            if attempt < max_retries - 1:
                wait_time = 2 * (attempt + 1)
                logger.info(f"Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
                continue
            return None, "Не могу подключиться к серверу API"

        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout error: {str(e)}")
            if attempt < max_retries - 1:
                wait_time = 2 * (attempt + 1)
                logger.info(f"Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
                continue
            return None, "Таймаут при подключении к API"

        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            if attempt < max_retries - 1:
                wait_time = 2 * (attempt + 1)
                logger.info(f"Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
                continue
            return None, f"Ошибка при подключении: {str(e)}"

    return None, "Не удалось подключиться к API после нескольких попыток"


async def call_api_with_user(endpoint, user, method="GET", data=None, params=None):
    if params is None:
        params = {}

    if "boards" in endpoint:
        params["telegram_id"] = user.id

    return await call_api(endpoint, method=method, data=data, params=params)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    welcome_text = (
        f"👋 Привет, {user.first_name}!\n\n"
        "🎨 **Добро пожаловать в MoodBoard бота!**\n\n"
        "Я помогу вам создавать доски вдохновения, куда можно добавлять:\n"
        "• 📷 Фотографии\n"
        "• 📝 Текстовые заметки\n"
        "• 🔗 Ссылки на интересные ресурсы\n\n"
        "🌐 **Для полного доступа к функциям нужна регистрация.**\n"
    )

    data, error = await call_api(f"/api/users/{user.id}/status")

    if error:
        await update.message.reply_text(
            f"{welcome_text}\n"
            "⚠️ *Сервер временно недоступен*\n"
            "Попробуйте позже или обратитесь к администратору.",
            parse_mode="Markdown"
        )
        return

    if data and data.get("is_registered"):
        await update.message.reply_text(
            f"{welcome_text}\n"
            "✅ *Вы уже зарегистрированы!*\n\n"
            "Используйте /menu для доступа ко всем функциям.",
            parse_mode="Markdown"
        )
    else:
        keyboard = [
            [
                InlineKeyboardButton("✅ Да, зарегистрировать", callback_data="register_yes"),
                InlineKeyboardButton("❌ Нет, позже", callback_data="register_no")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"{welcome_text}\n"
            "Хотите зарегистрироваться сейчас?\n\n"
            "После регистрации вы получите:\n"
            "✅ Логин и пароль для входа на сайт\n"
            "✅ Возможность создавать доски\n"
            "✅ Доступ к веб-редактору",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

async def register_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "register_no":
        await query.edit_message_text(
            "👌 Хорошо! Вы можете зарегистрироваться позже, отправив /start\n\n"
            "Пока что вы можете:\n"
            "• Посмотреть как работает бот - /help\n"
            "• Узнать больше о MoodBoard"
        )
        return ConversationHandler.END

    user = query.from_user
    await query.edit_message_text("🔄 Регистрирую вас в системе...")

    register_data = {
        "telegram_id": user.id,
        "username": user.username or user.first_name
    }

    data, error = await call_api("/api/users/register", method="POST", data=register_data)

    if error:
        await query.edit_message_text(
            f"❌ Ошибка при регистрации: {error}\n\n"
            "Попробуйте снова позже или обратитесь к администратору."
        )
        return ConversationHandler.END

    if data and "login" in data and "password" in data:
        login = data["login"]
        password = data["password"]

        message = (
            f"🎉 **Регистрация успешна!**\n\n"
            f"✅ **Ваши данные для входа на сайт:**\n\n"
            f"👤 **Логин:** `{login}`\n"
            f"🔑 **Пароль:** `{password}`\n\n"
            f"📌 **ВАЖНО:**\n"
            f"• Сохраните эти данные!\n"
            f"• Вы всегда можете посмотреть их в разделе **'Мои данные'**\n"
            f"• Используйте кнопку 'Мои данные' в главном меню\n\n"
            f"🌐 **Ссылка на сайт:**\n"
            f"{WEBSITE_URL}\n\n"
            f"🎨 **Что дальше?**\n"
            f"1. Войдите на сайт с логином и паролем\n"
            f"2. Создайте свою первую доску\n"
            f"3. Начните добавлять контент!"
        )

        keyboard = [
            [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(message, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await query.edit_message_text(
            "❌ Ошибка: не получилось зарегистрироваться. Попробуйте позже."
        )

    return ConversationHandler.END

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user=None):
    if not user:
        if update.message:
            user = update.effective_user
        elif update.callback_query:
            user = update.callback_query.from_user
        else:
            return

    data, error = await call_api(f"/api/users/{user.id}/status")

    keyboard = []

    if error or not data:
        keyboard = [
            [InlineKeyboardButton("🔁 Проверить статус", callback_data="check_status")],
            [InlineKeyboardButton("❓ Помощь", callback_data="help")]
        ]
        status_text = "❓ Статус неизвестен (сервер недоступен)"
    else:
        if data.get("is_registered"):
            keyboard = [
                [InlineKeyboardButton("➕ Создать доску", callback_data="create_board")],
                [InlineKeyboardButton("📋 Мои доски", callback_data="my_boards")],
                [InlineKeyboardButton("👤 Мои данные", callback_data="my_data")],
                [InlineKeyboardButton("❓ Помощь", callback_data="help")]
            ]
            status_text = "✅ Вы зарегистрированы"
        else:
            keyboard = [
                [InlineKeyboardButton("📝 Зарегистрироваться", callback_data="register_start")],
                [InlineKeyboardButton("❓ Помощь", callback_data="help")]
            ]
            status_text = "❌ Вы не зарегистрированы"

    reply_markup = InlineKeyboardMarkup(keyboard)

    message = (
        f"🎨 **Главное меню MoodBoard**\n\n"
        f"Привет, {user.first_name}!\n"
        f"{status_text}\n\n"
        "С помощью этого бота вы можете создавать и управлять досками вдохновения.\n\n"
        f"🌐 **Веб-сайт:** {WEBSITE_URL}"
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode="Markdown")


async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user

    data, error = await call_api("/health")

    if error:
        status_text = f"❌ API недоступен: {error}"
    else:
        status_text = f"✅ API работает: {data.get('message', 'OK')}"

    user_data, user_error = await call_api(f"/api/users/{user.id}/status")

    if user_error:
        user_status = "❓ Не удалось проверить статус пользователя"
    elif user_data and user_data.get("is_registered"):
        user_status = "✅ Вы зарегистрированы"
    else:
        user_status = "❌ Вы не зарегистрированы"

    message = (
        f"🔧 **Статус системы**\n\n"
        f"**API сервер:** {status_text}\n"
        f"**Ваш статус:** {user_status}\n\n"
        f"**Ссылки:**\n"
        f"• API: {API_URL}\n"
        f"• Сайт: {WEBSITE_URL}"
    )

    keyboard = [[InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, parse_mode="Markdown", reply_markup=reply_markup)

async def create_board_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user

    data, error = await call_api(f"/api/users/{user.id}/status")

    if error:
        await query.edit_message_text(f"❌ Ошибка при проверке статуса: {error}")
        return

    if not data or not data.get("is_registered"):
        keyboard = [
            [InlineKeyboardButton("📝 Зарегистрироваться", callback_data="register_start")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "📝 **Сначала нужно зарегистрироваться!**\n\n"
            "Для создания досок требуется регистрация в системе.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return

    await query.edit_message_text(
        "🎨 **Создание новой доски**\n\n"
        "Шаг 1 из 3\n"
        "Введите **название** для вашей доски:\n"
        "(Например: 'Мое вдохновение', 'Идеи для интерьера')\n\n"
        "Для отмены отправьте /cancel",
        parse_mode="Markdown"
    )

    return BOARD_NAME


async def get_board_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    board_name = update.message.text.strip()

    if not board_name or len(board_name) < 2:
        await update.message.reply_text(
            "❌ Название должно содержать хотя бы 2 символа.\n"
            "Пожалуйста, введите название еще раз:"
        )
        return BOARD_NAME

    context.user_data['board_name'] = board_name

    await update.message.reply_text(
        f"✅ Название сохранено: **{board_name}**\n\n"
        "Шаг 2 из 3\n"
        "Введите **описание** для вашей доски:\n"
        "(Можно оставить пустым, отправив /skip)\n\n"
        "Для отмены отправьте /cancel",
        parse_mode="Markdown"
    )

    return BOARD_DESC


async def skip_board_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['board_description'] = ""

    await update.message.reply_text(
        "⏭️ Описание пропущено.\n\n"
        "Шаг 3 из 3\n"
        "Выберите видимость доски:"
    )

    return await ask_board_visibility(update, context)


async def get_board_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    board_description = update.message.text.strip()
    context.user_data['board_description'] = board_description

    await update.message.reply_text(
        f"✅ Описание сохранено.\n\n"
        "Шаг 3 из 3\n"
        "Выберите видимость доски:"
    )

    return await ask_board_visibility(update, context)


async def ask_board_visibility(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("🔒 Приватная", callback_data="visibility_private"),
            InlineKeyboardButton("🌐 Публичная", callback_data="visibility_public")
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = (
        "Шаг 3 из 3\n"
        "Выберите видимость доски:\n\n"
        "• 🔒 **Приватная** - только вы и приглашенные соавторы\n"
        "• 🌐 **Публичная** - доступна всем по коду"
    )

    await update.message.reply_text(message, reply_markup=reply_markup, parse_mode="Markdown")

    return BOARD_VISIBILITY


async def process_board_visibility(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
        await query.edit_message_text("❌ Создание доски отменено.")
        context.user_data.clear()
        return ConversationHandler.END

    is_public = query.data == "visibility_public"
    context.user_data['is_public'] = is_public

    user = query.from_user
    board_name = context.user_data.get('board_name')
    board_description = context.user_data.get('board_description', '')

    await query.edit_message_text("🔄 Создаю вашу доску...")

    board_data = {
        "name": board_name,
        "description": board_description,
        "is_public": is_public
    }

    data, error = await call_api_with_user("/api/boards", user, method="POST", data=board_data)

    if error:
        await query.edit_message_text(f"❌ Ошибка при создании доски: {error}")
        context.user_data.clear()
        return ConversationHandler.END

    board_code = data.get("board_code", "N/A")
    visibility_text = "🌐 Публичная" if is_public else "🔒 Приватная"

    message = (
        f"🎉 **Доска создана успешно!**\n\n"
        f"📋 **Название:** {data.get('name', 'Без названия')}\n"
        f"📝 **Описание:** {board_description or 'Нет описания'}\n"
        f"🔓 **Видимость:** {visibility_text}\n\n"
        f"🔑 **Код вашей доски:**\n"
        f"```\n{board_code}\n```\n\n"
        f"🌐 **Для работы с доской:**\n"
        f"1. Перейдите на сайт: {WEBSITE_URL}\n"
        f"2. Войдите под своими логином и паролем\n"
        f"Или используйте кнопку ниже чтобы вернуться в меню."
    )

    keyboard = [
        [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, parse_mode="Markdown", reply_markup=reply_markup)

    context.user_data.clear()
    return ConversationHandler.END


async def my_boards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user

    data, error = await call_api(f"/api/users/{user.id}/boards-with-roles")

    if error:
        await query.edit_message_text(f"❌ Ошибка при загрузке досок: {error}")
        return

    if not data or len(data) == 0:
        keyboard = [
            [InlineKeyboardButton("➕ Создать первую доску", callback_data="create_board")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "📭 У вас пока нет досок.\n\n"
            "Создайте свою первую доску вдохновения!",
            reply_markup=reply_markup
        )
        return

    context.user_data['all_boards'] = data
    context.user_data['boards_page'] = 0

    boards_per_page = 10
    boards_on_page = data[:boards_per_page]

    keyboard = []
    for board in boards_on_page:
        emoji = "🌐" if board.get("is_public", False) else "🔒"
        board_name = board.get("name", "Без названия")[:20]
        board_id = board.get("id")

        user_role = board.get("user_role", "")
        if user_role == "owner":
            role_emoji = "👑"
        elif user_role == "collaborator":
            role_emoji = "👥"
            owner_name = board.get("owner_username", "")
            if owner_name:
                board_name = f"{board_name} (от {owner_name})"
        else:
            role_emoji = ""

        keyboard.append([
            InlineKeyboardButton(
                f"{emoji} {role_emoji} {board_name}",
                callback_data=f"board_{board_id}"
            )
        ])

    if len(data) > boards_per_page:
        keyboard.append([InlineKeyboardButton("📄 Показать еще...", callback_data="more_boards")])

    keyboard.append([InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    total_pages = (len(data) + boards_per_page - 1) // boards_per_page
    page_info = f" (Страница 1 из {total_pages})" if total_pages > 1 else ""

    await query.edit_message_text(
        f"📋 Ваши доски ({len(data)}){page_info}:\n\n"
        f"👑 - вы владелец\n"
        f"👥 - вы соавтор\n\n"
        "Выберите доску для управления:",
        reply_markup=reply_markup
    )

async def board_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    board_id = int(query.data.split("_")[1])
    context.user_data['current_board_id'] = board_id
    user = query.from_user

    data, error = await call_api(f"/api/boards/{board_id}?telegram_id={user.id}")

    if error:
        await query.edit_message_text(f"❌ Ошибка при загрузке доски: {error}")
        return

    board = data
    emoji = "🌐" if board.get("is_public", False) else "🔒"
    board_name = board.get("name", "Без названия")
    description = board.get("description", "Нет описания")

    user_role = board.get("user_role", "collaborator")

    members_count = board.get("members_count", {})
    collaborators_count = members_count.get("collaborator", 0)

    message = (
        f"{emoji} **{board_name}**\n\n"
        f"📝 {description}\n\n"
        f"👤 Автор: {board.get('owner_username', 'Неизвестно')}\n"
        f"🔑 Код доски: `{board.get('board_code', 'N/A')}`\n"
        f"📊 Контента: {board.get('content_count', 0)} элементов\n"
        f"👥 Количество соавторов: {collaborators_count}\n"
        f"🎭 Ваша роль: {'👑 Владелец' if user_role == 'owner' else '👥 Соавтор'}\n\n"
        f"**Действия с доской:**"
    )

    if user_role == "owner":
        keyboard = [
            [
                InlineKeyboardButton("➕ Добавить соавтора", callback_data=f"add_collaborator_{board_id}"),
                InlineKeyboardButton("➖ Удалить соавтора", callback_data=f"remove_collaborator_select_{board_id}")
            ],
            [
                InlineKeyboardButton("⚙️ Настройки доски", callback_data=f"board_settings_{board_id}"),
                InlineKeyboardButton("🗑️ Удалить доску", callback_data=f"delete_board_start_{board_id}")
            ],
            [
                InlineKeyboardButton("👥 Список соавторов", callback_data=f"board_members_{board_id}"),
                InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_board_{board_id}")
            ],
            [InlineKeyboardButton("📋 К списку досок", callback_data="my_boards")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton("👥 Список соавторов", callback_data=f"board_members_{board_id}"),
                InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_board_{board_id}")
            ],
            [InlineKeyboardButton("📋 К списку досок", callback_data="my_boards")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, parse_mode="Markdown", reply_markup=reply_markup)


async def board_members_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    board_id = int(query.data.split("_")[2])
    context.user_data['current_board_id'] = board_id
    user = query.from_user

    try:
        data, error = await call_api(f"/api/boards/{board_id}/members")

        if error:
            logger.error(f"Ошибка при получении участников: {error}")
            await query.edit_message_text(f"❌ Ошибка при загрузке участников: {error}")
            return

        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                logger.error(f"Не удалось распарсить ответ как JSON: {data}")
                await query.edit_message_text("❌ Ошибка формата данных от сервера")
                return
        elif not isinstance(data, dict):
            logger.error(f"Некорректный формат данных: {type(data)}")
            await query.edit_message_text("❌ Некорректный формат данных от сервера")
            return

        board_data_response, board_error = await call_api(f"/api/boards/{board_id}?telegram_id={user.id}")

        is_owner = False
        if not board_error and board_data_response:
            if isinstance(board_data_response, str):
                try:
                    board_data_response = json.loads(board_data_response)
                except:
                    pass

            if isinstance(board_data_response, dict):
                user_role = board_data_response.get("user_role", "")
                is_owner = (user_role == "owner")

        if not isinstance(data, dict):
            logger.error(f"Некорректная структура данных: {type(data)} - {data}")
            await query.edit_message_text("❌ Некорректная структура данных от сервера")
            return

        if "members" not in data or len(data["members"]) == 0:
            message = "👥 **Список участников**\n\n"
            message += "На этой доске пока нет других участников.\n\n"

            if is_owner:
                message += "Вы можете добавить соавторов для совместной работы."

            keyboard = []
            if is_owner:
                keyboard.append(
                    [InlineKeyboardButton("➕ Добавить соавтора", callback_data=f"add_collaborator_{board_id}")])
            keyboard.append([InlineKeyboardButton("↩️ Назад к доске", callback_data=f"board_{board_id}")])
            keyboard.append([InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")])
        else:
            message = "👥 **Список участников**\n\n"

            members = data["members"]

            if not isinstance(members, list):
                logger.error(f"Некорректный формат members: {type(members)}")
                await query.edit_message_text("❌ Некорректный формат данных от сервера")
                return

            owners = []
            collaborators = []

            for member in members:
                if not isinstance(member, dict):
                    logger.warning(f"Пропускаем некорректный элемент в members: {member}")
                    continue

                role = member.get("role", "")
                username = member.get("username", "Неизвестно")
                telegram_username = member.get("telegram_username", "")

                if role == "owner":
                    owners.append(f"👑 {username}" + (f" (@{telegram_username})" if telegram_username else ""))
                elif role == "collaborator":
                    collaborators.append(f"👥 {username}" + (f" (@{telegram_username})" if telegram_username else ""))

            if owners:
                message += "**Владелец:**\n"
                message += "\n".join(owners) + "\n\n"

            if collaborators:
                message += f"**Соавторы ({len(collaborators)}):**\n"
                message += "\n".join(collaborators) + "\n\n"

            keyboard = []
            if is_owner:
                keyboard.append(
                    [InlineKeyboardButton("➕ Добавить соавтора", callback_data=f"add_collaborator_{board_id}")])
                if collaborators:
                    keyboard.append([InlineKeyboardButton("➖ Удалить соавтора",
                                                          callback_data=f"remove_collaborator_select_{board_id}")])
            keyboard.append([InlineKeyboardButton("↩️ Назад к доске", callback_data=f"board_{board_id}")])
            keyboard.append([InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, parse_mode="Markdown", reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Ошибка в board_members_list: {e}", exc_info=True)
        await query.edit_message_text(
            "❌ Произошла ошибка при загрузке списка участников. Попробуйте позже."
        )

async def board_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    board_id = int(query.data.split("_")[2])
    context.user_data['current_board_id'] = board_id
    user = query.from_user

    board_data, error = await call_api(f"/api/boards/{board_id}?telegram_id={user.id}")

    if error:
        await query.edit_message_text(f"❌ Ошибка при загрузке доски: {error}")
        return

    user_role = board_data.get("user_role", "")
    if user_role != "owner":
        await query.edit_message_text(
            "❌ **Доступ запрещен!**\n\n"
            "Настройки доски доступны только владельцу.",
            parse_mode="Markdown"
        )
        return

    message = "⚙️ **Настройки доски**\n\nВыберите действие:"

    keyboard = [
        [InlineKeyboardButton("✏️ Изменить название", callback_data=f"edit_board_name_{board_id}")],
        [InlineKeyboardButton("📝 Изменить описание", callback_data=f"edit_board_desc_{board_id}")],
        [InlineKeyboardButton("🔐 Изменить приватность", callback_data=f"edit_board_privacy_{board_id}")],
        [InlineKeyboardButton("↩️ Назад к доске", callback_data=f"board_{board_id}")],
        [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode="Markdown")


async def edit_board_name_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    board_id = int(query.data.split("_")[3])
    context.user_data['current_board_id'] = board_id
    user = query.from_user

    board_data, error = await call_api(f"/api/boards/{board_id}?telegram_id={user.id}")

    if error:
        await query.edit_message_text(f"❌ Ошибка при загрузке доски: {error}")
        return

    user_role = board_data.get("user_role", "")
    if user_role != "owner":
        await query.edit_message_text(
            "❌ **Доступ запрещен!**\n\n"
            "Изменение названия доступно только владельцу.",
            parse_mode="Markdown"
        )
        return

    current_name = board_data.get("name", "")

    message = "✏️ **Изменение названия доски**\n\n"

    if current_name:
        message += f"📋 Текущее название: **{current_name}**\n\n"

    message += (
        "Введите новое название для доски:\n\n"
        "✅ **Требования:**\n"
        "• От 2 до 100 символов\n"
        "• Может содержать буквы, цифры, пробелы\n\n"
        "Для отмены отправьте /cancel"
    )

    await query.edit_message_text(message, parse_mode="Markdown")

    return EDIT_BOARD_NAME


async def edit_board_desc_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    board_id = int(query.data.split("_")[3])
    context.user_data['current_board_id'] = board_id
    user = query.from_user

    board_data, error = await call_api(f"/api/boards/{board_id}?telegram_id={user.id}")

    if error:
        await query.edit_message_text(f"❌ Ошибка при загрузке доски: {error}")
        return

    user_role = board_data.get("user_role", "")
    if user_role != "owner":
        await query.edit_message_text(
            "❌ **Доступ запрещен!**\n\n"
            "Изменение описания доступно только владельцу.",
            parse_mode="Markdown"
        )
        return

    current_desc = board_data.get("description", "")

    message = "📝 **Изменение описания доски**\n\n"

    if current_desc:
        message += f"📋 Текущее описание: {current_desc}\n\n"
    else:
        message += "📭 Текущее описание отсутствует\n\n"

    message += (
        "Введите новое описание для доски:\n\n"
        "✅ **Требования:**\n"
        "• До 500 символов\n"
        "• Может быть пустым\n\n"
        "Для пропуска отправьте /skip\n"
        "Для отмены отправьте /cancel"
    )

    await query.edit_message_text(message, parse_mode="Markdown")

    return EDIT_BOARD_DESC


async def process_board_name_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    new_name = update.message.text.strip()

    board_id = context.user_data.get('current_board_id')

    if not board_id:
        await update.message.reply_text("❌ Ошибка: не выбрана доска")
        return ConversationHandler.END

    if not new_name or len(new_name) < 2:
        await update.message.reply_text(
            "❌ Название должно содержать хотя бы 2 символа.\n"
            "Пожалуйста, введите новое название еще раз:"
        )
        return EDIT_BOARD_NAME

    if len(new_name) > 100:
        await update.message.reply_text(
            "❌ Название слишком длинное (максимум 100 символов).\n"
            "Пожалуйста, введите более короткое название:"
        )
        return EDIT_BOARD_NAME

    await update.message.reply_text("🔄 Обновляю название доски...")

    update_data = {
        "name": new_name
    }

    data, error = await call_api_with_user(
        f"/api/boards/{board_id}/settings",
        user,
        method="PUT",
        data=update_data
    )

    if error:
        await update.message.reply_text(
            f"❌ Ошибка при обновлении названия: {error}\n\n"
            f"Попробуйте еще раз или отправьте /cancel"
        )
        return EDIT_BOARD_NAME

    message = (
        f"✅ **Название доски успешно обновлено!**\n\n"
        f"Новое название: **{new_name}**"
    )

    keyboard = [
        [
            InlineKeyboardButton("⚙️ К настройкам", callback_data=f"board_settings_{board_id}"),
            InlineKeyboardButton("📋 К доске", callback_data=f"board_{board_id}")
        ],
        [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(message, parse_mode="Markdown", reply_markup=reply_markup)
    context.user_data.clear()
    return ConversationHandler.END


async def process_board_desc_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    new_desc = update.message.text.strip()

    board_id = context.user_data.get('current_board_id')

    if not board_id:
        await update.message.reply_text("❌ Ошибка: не выбрана доска")
        return ConversationHandler.END

    if len(new_desc) > 500:
        await update.message.reply_text(
            "❌ Описание слишком длинное (максимум 500 символов).\n"
            "Пожалуйста, введите более короткое описание:"
        )
        return EDIT_BOARD_DESC

    await update.message.reply_text("🔄 Обновляю описание доски...")

    update_data = {
        "description": new_desc
    }

    data, error = await call_api_with_user(
        f"/api/boards/{board_id}/settings",
        user,
        method="PUT",
        data=update_data
    )

    if error:
        await update.message.reply_text(
            f"❌ Ошибка при обновлении описания: {error}\n\n"
            f"Попробуйте еще раз или отправьте /cancel"
        )
        return EDIT_BOARD_DESC

    if new_desc:
        message = f"✅ **Описание доски успешно обновлено!**\n\nНовое описание: {new_desc}"
    else:
        message = "✅ **Описание доски удалено**\n\nОписание доски было очищено."

    keyboard = [
        [
            InlineKeyboardButton("⚙️ К настройкам", callback_data=f"board_settings_{board_id}"),
            InlineKeyboardButton("📋 К доске", callback_data=f"board_{board_id}")
        ],
        [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(message, parse_mode="Markdown", reply_markup=reply_markup)
    context.user_data.clear()
    return ConversationHandler.END


async def edit_board_privacy_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    board_id = int(query.data.split("_")[3])
    context.user_data['current_board_id'] = board_id
    user = query.from_user

    board_data, error = await call_api(f"/api/boards/{board_id}?telegram_id={user.id}")

    if error:
        await query.edit_message_text(f"❌ Ошибка при загрузке доски: {error}")
        return

    user_role = board_data.get("user_role", "")
    if user_role != "owner":
        await query.edit_message_text(
            "❌ **Доступ запрещен!**\n\n"
            "Изменение приватности доступно только владельцу.",
            parse_mode="Markdown"
        )
        return

    current_privacy = board_data.get("is_public", False)
    board_name = board_data.get("name", "доски")

    message = (
        f"🔐 **Изменение приватности доски**\n\n"
        f"Текущий статус: {'🌐 Публичная' if current_privacy else '🔒 Приватная'}\n\n"
        f"**Выберите новый статус:**\n\n"
        f"• 🔒 **Приватная** - только вы и приглашенные соавторы могут просматривать и редактировать доску\n"
        f"• 🌐 **Публичная** - любой, у кого есть код доски, может просматривать её\n"
    )

    keyboard = [
        [
            InlineKeyboardButton("🔒 Сделать приватной", callback_data=f"set_privacy_private_{board_id}"),
            InlineKeyboardButton("🌐 Сделать публичной", callback_data=f"set_privacy_public_{board_id}")
        ],
        [
            InlineKeyboardButton("↩️ Назад", callback_data=f"board_settings_{board_id}"),
            InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, parse_mode="Markdown", reply_markup=reply_markup)


async def process_board_privacy_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split('_')
    new_privacy = parts[2]
    board_id = int(parts[3])

    user = query.from_user
    is_public = (new_privacy == 'public')

    await query.edit_message_text("🔄 Изменяю настройки приватности...")

    update_data = {
        "is_public": is_public
    }

    data, error = await call_api_with_user(
        f"/api/boards/{board_id}/settings",
        user,
        method="PUT",
        data=update_data
    )

    if error:
        await query.edit_message_text(f"❌ Ошибка при изменении приватности: {error}")
        return

    board_data, _ = await call_api(f"/api/boards/{board_id}")

    if board_data:
        board_code = board_data.get("board_code", "N/A")

        if is_public:
            message = (
                f"✅ **Доска теперь публичная!**\n\n"
                f"Теперь любой пользователь с кодом доски может просматривать её.\n\n"
                f"🔑 **Код доски:**\n"
                f"```\n{board_code}\n```\n\n"
                f"🌐 **Ссылка на сайт:**\n"
                f"{WEBSITE_URL}"
            )
        else:
            message = (
                f"✅ **Доска теперь приватная!**\n\n"
                f"Теперь только вы и приглашенные соавторы могут просматривать и редактировать доску."
            )
    else:
        message = f"✅ Приватность доски изменена на: {'🌐 Публичная' if is_public else '🔒 Приватная'}"

    keyboard = [
        [
            InlineKeyboardButton("⚙️ К настройкам", callback_data=f"board_settings_{board_id}"),
            InlineKeyboardButton("📋 К доске", callback_data=f"board_{board_id}")
        ],
        [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, parse_mode="Markdown", reply_markup=reply_markup)


async def skip_board_description_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    board_id = context.user_data.get('current_board_id')

    if not board_id:
        await update.message.reply_text("❌ Ошибка: не выбрана доска")
        return ConversationHandler.END

    await update.message.reply_text("🔄 Очищаю описание доски...")

    update_data = {
        "description": ""
    }

    data, error = await call_api_with_user(
        f"/api/boards/{board_id}/settings",
        user,
        method="PUT",
        data=update_data
    )

    if error:
        await update.message.reply_text(f"❌ Ошибка при очистке описания: {error}")
        return EDIT_BOARD_DESC
    else:
        await update.message.reply_text("✅ Описание доски очищено.")

    keyboard = [
        [
            InlineKeyboardButton("⚙️ К настройкам", callback_data=f"board_settings_{board_id}"),
            InlineKeyboardButton("📋 К доске", callback_data=f"board_{board_id}")
        ],
        [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Выберите следующее действие:", reply_markup=reply_markup)
    context.user_data.clear()
    return ConversationHandler.END


async def edit_board(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    board_id = int(query.data.split("_")[2])
    context.user_data['current_board_id'] = board_id

    message = "✏️ **Редактирование доски**\n\nВыберите действие:"

    keyboard = [
        [
            InlineKeyboardButton("➕ Добавить элемент", callback_data=f"add_content_{board_id}"),
            InlineKeyboardButton("🗑️ Удалить элемент", callback_data=f"delete_content_{board_id}")
        ],
        [InlineKeyboardButton("📋 К деталям доски", callback_data=f"board_{board_id}")],
        [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode="Markdown")


async def delete_board_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        board_id = int(query.data.split("_")[3])
    except (IndexError, ValueError) as e:
        logger.error(f"Ошибка парсинга board_id: {e}, data: {query.data}")
        await query.edit_message_text("❌ Ошибка: неверный формат запроса")
        return

    user = query.from_user
    board_data, error = await call_api(f"/api/boards/{board_id}?telegram_id={user.id}")

    if error:
        await query.edit_message_text(f"❌ Ошибка при загрузке доски: {error}")
        return

    user_role = board_data.get("user_role", "")
    if user_role != "owner":
        await query.edit_message_text(
            "❌ **Доступ запрещен!**\n\n"
            "Удаление доски доступно только владельцу.",
            parse_mode="Markdown"
        )
        return

    context.user_data['board_to_delete'] = board_id

    board_name = board_data.get("name", "Без названия")
    content_count = board_data.get("content_count", 0)

    message = (
        f"⚠️ **Подтверждение удаления доски**\n\n"
        f"Вы действительно хотите удалить доску:\n"
        f"**«{board_name}»**?\n\n"
        f"📊 На доске:\n"
        f"• Элементов контента: {content_count}\n"
        f"• Соавторов: {board_data.get('members_count', {}).get('collaborator', 0)}\n\n"
        f"❌ **Это действие необратимо!**\n"
        f"Будет удалено всё:\n"
        f"• Вся доска\n"
        f"• Весь контент ({content_count} элементов)\n"
        f"• Все файлы\n"
        f"• Все настройки доступа\n\n"
        f"Вы уверены?"
    )

    keyboard = [
        [
            InlineKeyboardButton("✅ Да, удалить доску", callback_data=f"delete_board_confirm_{board_id}"),
            InlineKeyboardButton("❌ Нет, отменить", callback_data=f"board_{board_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, parse_mode="Markdown", reply_markup=reply_markup)


async def delete_board_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        board_id = int(query.data.split("_")[3])
    except (IndexError, ValueError) as e:
        logger.error(f"Ошибка парсинга board_id: {e}, data: {query.data}")
        await query.edit_message_text("❌ Ошибка: неверный формат запроса")
        return

    user = query.from_user

    await query.edit_message_text("🔄 Удаляю доску и весь контент...")

    data, error = await call_api_with_user(
        f"/api/boards/{board_id}",
        user,
        method="DELETE"
    )

    if error:
        logger.error(f"Ошибка API при удалении доски {board_id}: {error}")
        await query.edit_message_text(f"❌ Ошибка при удалении доски: {error}")
    else:
        message = (
            f"✅ **Доска успешно удалена!**\n\n"
            f"Все данные доски были удалены из системы."
        )

        if data and isinstance(data, dict):
            if 'message' in data:
                message += f"\n\n{data['message']}"
            if 'deleted_content_count' in data:
                message += f"\n\n🗑️ Удалено элементов: {data['deleted_content_count']}"

        keyboard = [
            [InlineKeyboardButton("📋 К списку досок", callback_data="my_boards")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(message, parse_mode="Markdown", reply_markup=reply_markup)

    if 'board_to_delete' in context.user_data:
        del context.user_data['board_to_delete']
    if 'current_board_id' in context.user_data:
        del context.user_data['current_board_id']


async def add_content_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    board_id = int(query.data.split("_")[2])
    context.user_data['current_board_id'] = board_id

    message = (
        "➕ **Добавление элемента**\n\n"
        "Выберите тип элемента:\n\n"
        "• 📝 **Текст** - текстовая заметка\n"
        "• 📷 **Изображение** - фото или картинка\n"
    )

    keyboard = [
        [
            InlineKeyboardButton("📝 Текст", callback_data="content_type_text"),
            InlineKeyboardButton("📷 Изображение", callback_data="content_type_image")
        ],
        [
            InlineKeyboardButton("↩️ Назад", callback_data=f"edit_board_{board_id}")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode="Markdown")

    return ADD_CONTENT_TYPE


async def process_content_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    content_type = query.data.replace("content_type_", "")
    context.user_data['content_type'] = content_type

    type_names = {
        "text": "текст",
        "image": "изображение",
    }

    type_name = type_names.get(content_type, "элемент")

    if content_type == "text":
        await query.edit_message_text(
            f"📝 Добавление текста\n\n"
            f"Введите текст:\n\n"
            f"Для отмены отправьте /cancel"
        )
        return ADD_TEXT_CONTENT
    elif content_type == "image":
        await query.edit_message_text(
            f"📤 Добавление {type_name}\n\n"
            f"Отправьте изображение:\n\n"
            f"Для отмены отправьте /cancel"
        )
        return ADD_FILE_CONTENT
    else:
        await query.edit_message_text(
            "❌ Этот тип контента не поддерживается."
        )
        return ConversationHandler.END


async def add_text_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text_content = update.message.text.strip()
    board_id = context.user_data.get('current_board_id')

    if not text_content:
        await update.message.reply_text("❌ Текст не может быть пустым. Попробуйте еще раз:")
        return ADD_TEXT_CONTENT

    if not board_id:
        await update.message.reply_text("❌ Ошибка: не выбрана доска")
        return ConversationHandler.END

    await update.message.reply_text("🔄 Добавляю текст на доску...")

    content_data = {
        "type": "text",
        "content": text_content,
        "x_position": 50,
        "y_position": 50,
        "width": 200,
        "height": 100
    }

    logger.info(f"Отправка текста на API: {content_data}")

    data, error = await call_api_with_user(
        f"/api/boards/{board_id}/content",
        user,
        method="POST",
        data=content_data
    )

    if error:
        logger.error(f"API Error when adding text: {error}")
        logger.error(f"Request data was: {content_data}")
        await update.message.reply_text(
            f"❌ Ошибка при добавлении текста: {error}\n\nПопробуйте еще раз или обратитесь к администратору.")
    else:
        await update.message.reply_text(f"✅ Текст добавлен на доску!")

    keyboard = [[InlineKeyboardButton("↩️ К редактированию", callback_data=f"edit_board_{board_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Выберите следующее действие:", reply_markup=reply_markup)
    return ConversationHandler.END


async def add_file_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    board_id = context.user_data.get('current_board_id')
    content_type = context.user_data.get('content_type', 'image')

    if not board_id:
        await update.message.reply_text("❌ Ошибка: не выбрана доска")
        return ConversationHandler.END

    if content_type == "image" and update.message.photo:
        try:
            photo = update.message.photo[-1]

            await update.message.reply_text("🔄 Загружаю изображение...")

            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                temp_path = tmp_file.name

                file = await photo.get_file()
                await file.download_to_drive(temp_path)

                url = f"{API_URL}/api/boards/{board_id}/content/upload"

                params = {
                    'telegram_id': str(user.id)
                }

                form_data = {
                    'type': 'image',
                    'x_position': '100',
                    'y_position': '100',
                    'width': '300',
                    'height': '200'
                }

                with open(temp_path, 'rb') as f:
                    files = {
                        'file': (f'photo_{file.file_id}.jpg', f, 'image/jpeg')
                    }

                    response = requests.post(
                        url,
                        files=files,
                        data=form_data,
                        params=params,
                        timeout=60
                    )

                os.unlink(temp_path)

                if response.status_code == 200:
                    result = response.json()

                    file_url = result.get('content_url') or result.get('content')
                    if file_url and not file_url.startswith('http'):
                        if file_url.startswith('/static/'):
                            file_url = f"http://5.129.215.111{file_url}"

                    message_text = "✅ Изображение успешно добавлено на доску!"
                    if file_url:
                        message_text += f"\n\n🌐 Ссылка на файл: {file_url}"

                    await update.message.reply_text(message_text)
                else:
                    error_msg = f"Ошибка {response.status_code}"
                    try:
                        error_data = response.json()
                        error_msg = error_data.get('detail', error_data.get('message', str(response.text)))
                    except:
                        error_msg = response.text[:200]

                    await update.message.reply_text(f"❌ Ошибка при добавлении изображения: {error_msg}")

        except Exception as e:
            logger.error(f"Ошибка при обработке фото: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    else:
        await update.message.reply_text("❌ Пожалуйста, отправьте изображение")
        return ADD_FILE_CONTENT

    keyboard = [[InlineKeyboardButton("↩️ К редактированию", callback_data=f"edit_board_{board_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите следующее действие:", reply_markup=reply_markup)

    return ConversationHandler.END


async def delete_content_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    board_id = int(query.data.split("_")[2])
    context.user_data['current_board_id'] = board_id

    data, error = await call_api(f"/api/boards/{board_id}/content")

    if error:
        await query.edit_message_text(f"❌ Ошибка при загрузке контента: {error}")
        return

    if not data or len(data) == 0:
        keyboard = [[InlineKeyboardButton("↩️ Назад", callback_data=f"edit_board_{board_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "📭 На этой доске пока нет элементов.\n\n"
            "Добавьте первый элемент!",
            reply_markup=reply_markup
        )
        return

    keyboard = []
    for item in data[:10]:
        emoji = {
            "text": "📝",
            "image": "📷"
        }.get(item.get("type", ""), "📎")

        content = item.get("content", "")
        content_preview = content[:20] + "..." if len(content) > 20 else content

        keyboard.append([
            InlineKeyboardButton(
                f"{emoji} {content_preview}",
                callback_data=f"delete_item_{item.get('id')}"
            )
        ])

    keyboard.append([InlineKeyboardButton("↩️ Назад", callback_data=f"edit_board_{board_id}")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "🗑️ Удаление элемента\n\n"
        "Выберите элемент для удаления:",
        reply_markup=reply_markup
    )


async def delete_content_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    content_id = int(query.data.split("_")[2])
    context.user_data['content_to_delete'] = content_id
    board_id = context.user_data.get('current_board_id')

    keyboard = [
        [
            InlineKeyboardButton("✅ Да, удалить", callback_data=f"confirm_delete_{content_id}"),
            InlineKeyboardButton("❌ Нет, отмена", callback_data=f"delete_content_{board_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "⚠️ Подтверждение удаления\n\n"
        "Вы уверены, что хотите удалить этот элемент?\n"
        "Это действие нельзя отменить.",
        reply_markup=reply_markup
    )

    return DELETE_CONFIRM


async def delete_content_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    content_id = int(query.data.split("_")[2])
    board_id = context.user_data.get('current_board_id')
    user = query.from_user

    if not board_id:
        await query.edit_message_text("❌ Ошибка: не выбрана доска")
        return ConversationHandler.END

    data, error = await call_api_with_user(
        f"/api/boards/{board_id}/content/{content_id}",
        user,
        method="DELETE"
    )

    if error:
        await query.edit_message_text(f"❌ Ошибка при удалении: {error}")
    else:
        await query.edit_message_text("✅ Элемент успешно удален!")

    if 'content_to_delete' in context.user_data:
        del context.user_data['content_to_delete']

    keyboard = [[InlineKeyboardButton("↩️ К списку элементов", callback_data=f"delete_content_{board_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.reply_text("Выберите следующее действие:", reply_markup=reply_markup)
    return ConversationHandler.END


async def add_collaborator_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    board_id = int(query.data.split("_")[2])
    context.user_data['current_board_id'] = board_id
    user = query.from_user

    board_data, error = await call_api(f"/api/boards/{board_id}?telegram_id={user.id}")

    if error:
        await query.edit_message_text(f"❌ Ошибка при загрузке доски: {error}")
        return

    user_role = board_data.get("user_role", "")
    if user_role != "owner":
        await query.edit_message_text(
            "❌ **Доступ запрещен!**\n\n"
            "Добавление соавторов доступно только владельцу.",
            parse_mode="Markdown"
        )
        return

    await query.edit_message_text(
        "👥 Добавление соавтора\n\n"
        "Введите username пользователя в Telegram (без @):\n\n"
        "Например: `ivanov` или `anna_smith`\n\n"
        "Для отмены отправьте /cancel"
    )

    return ADD_COLLABORATOR


async def add_collaborator_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    board_id = context.user_data.get('current_board_id')
    telegram_username = update.message.text.strip().lstrip('@')

    if not board_id:
        await update.message.reply_text("❌ Ошибка: не выбрана доска")
        return ConversationHandler.END

    if not telegram_username:
        await update.message.reply_text("❌ Имя пользователя не может быть пустым. Попробуйте еще раз:")
        return ADD_COLLABORATOR

    collaborator_data = {
        "telegram_username": telegram_username,
        "role": "collaborator"
    }

    data, error = await call_api_with_user(
        f"/api/boards/{board_id}/collaborators",
        user,
        method="POST",
        data=collaborator_data
    )

    if error:
        await update.message.reply_text(f"❌ Ошибка: {error}")
    elif data and data.get("success"):
        await update.message.reply_text(f"✅ {data.get('message', 'Соавтор добавлен')}")
    else:
        await update.message.reply_text(f"❌ {data.get('message', 'Не удалось добавить соавтора')}")

    keyboard = [[InlineKeyboardButton("👥 К списку участников", callback_data=f"board_members_{board_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Выберите следующее действие:", reply_markup=reply_markup)
    return ConversationHandler.END


def escape_markdown(text: str) -> str:
    if not text:
        return ""

    escape_chars = r'_*[]()~`>#+-=|{}.!'
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text


async def remove_collaborator_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    board_id = int(query.data.split("_")[3])
    context.user_data['current_board_id'] = board_id
    user = query.from_user

    board_data, error = await call_api(f"/api/boards/{board_id}?telegram_id={user.id}")

    if error:
        await query.edit_message_text(f"❌ Ошибка при загрузке доски: {error}")
        return

    user_role = board_data.get("user_role", "")
    if user_role != "owner":
        await query.edit_message_text(
            "❌ **Доступ запрещен!**\n\n"
            "Удаление соавторов доступно только владельцу.",
            parse_mode="Markdown"
        )
        return

    data, error = await call_api(f"/api/boards/{board_id}/collaborators?telegram_id={user.id}")

    if error:
        await query.edit_message_text(f"❌ Ошибка при загрузке соавторов: {error}")
        return

    if not data or "collaborators" not in data or len(data["collaborators"]) == 0:
        await query.edit_message_text(
            "📭 **Нет соавторов для удаления**\n\n"
            "На этой доске нет соавторов.",
            parse_mode="Markdown"
        )
        return

    keyboard = []
    for collaborator in data["collaborators"]:
        username = collaborator.get("username", "Неизвестно")
        telegram_username = collaborator.get("telegram_username", "")
        user_id = collaborator.get("user_id")

        button_text = f"👥 {username}"
        if telegram_username:
            button_text += f" (@{telegram_username})"

        keyboard.append([
            InlineKeyboardButton(
                button_text,
                callback_data=f"remove_collaborator_{board_id}_{user_id}"
            )
        ])

    keyboard.append([InlineKeyboardButton("↩️ Назад", callback_data=f"board_members_{board_id}")])
    keyboard.append([InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "➖ Удаление соавтора\n\n"
        "Выберите соавтора для удаления:",
        reply_markup=reply_markup
    )

async def remove_collaborator_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    board_id = int(parts[2])
    collaborator_id = int(parts[3])

    context.user_data['collaborator_to_remove'] = collaborator_id
    context.user_data['current_board_id'] = board_id
    user = query.from_user

    data, error = await call_api(f"/api/boards/{board_id}/members")

    collaborator_name = "Неизвестно"
    if not error and data and "members" in data:
        for member in data["members"]:
            if member.get("user_id") == collaborator_id and member.get("role") == "collaborator":
                collaborator_name = member.get("username", "Неизвестно")
                break

    message = (
        f"⚠️ ПОДТВЕРЖДЕНИЕ УДАЛЕНИЯ СОАВТОРА\n\n"
        f"Вы уверены, что хотите удалить соавтора:\n\n"
        f"👤 {collaborator_name}\n\n"
        f"После удаления этот пользователь больше не сможет:\n"
        f"• Просматривать доску\n"
        f"• Редактировать контент\n"
        f"• Добавлять новые элементы\n\n"
        f"Это действие можно отменить только повторным добавлением пользователя."
    )

    keyboard = [
        [
            InlineKeyboardButton("✅ Да, удалить",
                                 callback_data=f"confirm_remove_collaborator_{board_id}_{collaborator_id}"),
            InlineKeyboardButton("❌ Нет, отмена", callback_data=f"remove_collaborator_select_{board_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(
            text=message,
            reply_markup=reply_markup,
            parse_mode=None
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения подтверждения: {e}")
        try:
            await query.message.reply_text(message, reply_markup=reply_markup)
        except:
            pass

    return REMOVE_COLLABORATOR_CONFIRM


async def remove_collaborator_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    board_id = int(parts[3])
    collaborator_id = int(parts[4])

    user = query.from_user

    try:
        await query.edit_message_text("🔄 Удаляю соавтора...")

        endpoint = f"/api/boards/{board_id}/collaborators/{collaborator_id}"

        params = {"telegram_id": user.id}

        logger.info(f"Удаление соавтора: {endpoint}, telegram_id: {user.id}")

        data, error = await call_api(
            endpoint,
            method="DELETE",
            params=params
        )

        if error:
            logger.error(f"Ошибка API при удалении соавтора {collaborator_id} с доски {board_id}: {error}")
            await query.edit_message_text(f"❌ Ошибка при удалении соавтора: {error}")
        else:
            success_message = "✅ Соавтор успешно удален!\n\nТеперь этот пользователь больше не имеет доступа к доске."

            if 'collaborator_to_remove' in context.user_data:
                del context.user_data['collaborator_to_remove']

            await query.edit_message_text(success_message)

            keyboard = [[InlineKeyboardButton("👥 К списку участников", callback_data=f"board_members_{board_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.message.reply_text("Выберите следующее действие:", reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Ошибка в remove_collaborator_execute: {e}", exc_info=True)
        await query.edit_message_text(f"❌ Произошла ошибка: {str(e)}")

    return ConversationHandler.END

async def share_board(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    board_id = int(query.data.split("_")[2])

    data, error = await call_api(f"/api/boards/{board_id}")

    if error:
        await query.edit_message_text(f"❌ Ошибка при загрузке доски: {error}")
        return

    board = data

    if not board.get("is_public", False):
        message = (
            f"🔒 **Доска приватная!**\n\n"
            f"Доска **{board.get('name', 'Без названия')}** в настоящее время приватная.\n"
            f"Её невозможно открыть для просмотра другими пользователями.\n\n"
            f"Хотите сделать её публичной?"
        )

        keyboard = [
            [
                InlineKeyboardButton("✅ Сделать публичной", callback_data=f"make_public_{board_id}"),
                InlineKeyboardButton("❌ Оставить приватной", callback_data=f"board_{board_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(message, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        board_code = board.get("board_code", "N/A")
        message = (
            f"🌐 **Поделиться доской**\n\n"
            f"Доска **{board.get('name', 'Без названия')}** публичная!\n\n"
            f"🔑 **Код доски:**\n"
            f"```\n{board_code}\n```\n\n"
            f"🌐 **Ссылка на сайт:**\n"
            f"{WEBSITE_URL}\n\n"
            f"📋 **Как поделиться:**\n"
            f"1. Отправьте код доски другому пользователю\n"
            f"2. Он перейдет на сайт {WEBSITE_URL}\n"
            f"3. Введет код доски для просмотра"
        )

        keyboard = [
            [InlineKeyboardButton("📋 К деталям доски", callback_data=f"board_{board_id}")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(message, parse_mode="Markdown", reply_markup=reply_markup)


async def make_board_public(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    board_id = int(query.data.split("_")[2])
    user = query.from_user

    board_data, error = await call_api(f"/api/boards/{board_id}?telegram_id={user.id}")

    if error:
        await query.edit_message_text(f"❌ Ошибка при загрузке доски: {error}")
        return

    user_role = board_data.get("user_role", "")
    if user_role != "owner":
        await query.edit_message_text(
            "❌ **Доступ запрещен!**\n\n"
            "Изменение приватности доступно только владельцу.",
            parse_mode="Markdown"
        )
        return

    data, error = await call_api_with_user(
        f"/api/boards/{board_id}/settings",
        user,
        method="PUT",
        data={"is_public": True}
    )

    if error:
        await query.edit_message_text(f"❌ Ошибка при изменении настроек: {error}")
        return

    board_data, _ = await call_api(f"/api/boards/{board_id}")

    if board_data:
        board_code = board_data.get("board_code", "N/A")
        message = (
            f"✅ **Доска теперь публичная!**\n\n"
            f"Доск**{board_data.get('name', 'Без названия')}** теперь доступна всем по коду.\n\n"
            f"🔑 **Код доски:**\n"
            f"```\n{board_code}\n```\n\n"
            f"🌐 **Ссылка на сайт:**\n"
            f"{WEBSITE_URL}"
        )

        keyboard = [
            [InlineKeyboardButton("📋 К деталям доски", callback_data=f"board_{board_id}")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(message, parse_mode="Markdown", reply_markup=reply_markup)


async def my_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user

    data, error = await call_api(f"/api/users/{user.id}/password")

    if error:
        status_data, status_error = await call_api(f"/api/users/{user.id}/status")

        if status_error:
            message = (
                f"❌ **Ошибка при загрузке данных**\n\n"
                f"Не удалось подключиться к серверу.\n"
                f"Попробуйте позже."
            )
        elif not status_data.get("is_registered"):
            message = (
                f"👤 **Ваши данные**\n\n"
                f"❌ **Вы еще не зарегистрированы!**\n\n"
                f"Для регистрации отправьте /start"
            )
        else:
            message = (
                f"✅ **Вы зарегистрированы**\n\n"
                f"⚠️ **Пароль не доступен**\n\n"
                f"Используйте /start для получения пароля."
            )
    else:
        login = data.get("login", "Неизвестно")
        password = data.get("password", "Не найден")

        message = (
            f"🔐 **ВАШИ ДАННЫЕ ДЛЯ ВХОДА**\n\n"
            f"✅ **Вы зарегистрированны в системе**\n\n"
            f"👇 **Скопируйте эти данные:**\n\n"
            f"**👤 ЛОГИН:**\n"
            f"```\n{login}\n```\n\n"
            f"**🔑 ПАРОЛЬ:**\n"
            f"```\n{password}\n```\n\n"
            f"🌐 **Ссылка на сайт:**\n"
            f"{WEBSITE_URL}\n\n"
            f"⚠️ **ВНИМАНИЕ!**\n"
            f"• Не передавайте эти данные никому\n"
            f"• Сохраните их в надежном месте"
        )

    keyboard = [
        [InlineKeyboardButton("📝 Перерегистрироваться", callback_data="register_start")],
        [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message, parse_mode="Markdown", reply_markup=reply_markup)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        user = update.effective_user
        message_source = update.message
    else:
        query = update.callback_query
        await query.answer()
        user = query.from_user
        message_source = query

    message = (
        f"❓ **Помощь по MoodBoard боту**\n\n"
        f"👋 Привет, {user.first_name}!\n\n"
        f"🎨 **Что такое MoodBoard?**\n"
        f"Это платформа для создания досок вдохновения, где вы можете собирать:\n"
        f"• Фотографии\n"
        f"• Текстовые заметки\n\n"
        f"🤖 **Основные команды бота:**\n"
        f"• /start - Начать работу с ботом\n"
        f"• /menu - Показать главное меню\n"
        f"• /help - Показать эту справку\n\n"
        f"📱 **Как использовать бота:**\n"
        f"1. Зарегистрируйтесь через /start\n"
        f"2. Создайте доску через меню\n"
        f"3. Добавляйте контент на доску\n"
        f"4. Приглашайте соавторов\n"
        f"5. Делитесь досками с другими\n\n"
        f"🌐 **Веб-сайт:**\n"
        f"{WEBSITE_URL}\n"
    )

    keyboard = [
        [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(message, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await query.edit_message_text(message, parse_mode="Markdown", reply_markup=reply_markup)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    data, error = await call_api("/health")

    if error:
        api_status = f"❌ Недоступен: {error}"
    else:
        api_status = f"✅ Работает: {data.get('message', 'OK')}"

    user_data, user_error = await call_api(f"/api/users/{user.id}/status")

    if user_error:
        user_status = "❓ Не удалось проверить"
    elif user_data and user_data.get("is_registered"):
        user_status = "✅ Зарегистрирован"
    else:
        user_status = "❌ Не зарегистрирован"

    message = (
        f"🔧 **Статус системы**\n\n"
        f"**API сервер:** {api_status}\n"
        f"**Ваш статус:** {user_status}\n\n"
        f"**URL:**\n"
        f"• API: {API_URL}\n"
        f"• Сайт: {WEBSITE_URL}"
    )

    await update.message.reply_text(message, parse_mode="Markdown")


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_main_menu(update, context)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            "❌ Действие отменено.\n\n"
            "Используйте /menu для возврата в главное меню."
        )
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "❌ Действие отменено.\n\n"
            "Используйте /menu для возврата в главное меню."
        )

    context.user_data.clear()
    return ConversationHandler.END


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Произошла ошибка. Пожалуйста, попробуйте позже.\n"
            "Если ошибка повторяется, используйте /status для проверки системы."
        )


async def register_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user

    await query.edit_message_text("🔄 Регистрирую вас в системе...")

    register_data = {
        "telegram_id": user.id,
        "username": user.username or user.first_name
    }

    data, error = await call_api("/api/users/register", method="POST", data=register_data)

    if error:
        await query.edit_message_text(f"❌ Ошибка при регистрации: {error}")
        return

    if data and "login" in data and "password" in data:
        login = data["login"]
        password = data["password"]

        message = (
            f"🎉 **Регистрация успешна!**\n\n"
            f"✅ Ваши данные для входа на сайт:\n\n"
            f"👤 **Логин:** `{login}`\n"
            f"🔐 **Пароль:** `{password}`\n\n"
            f"⚠️ **СОХРАНИТЕ ЭТИ ДАННЫЕ!**\n\n"
            f"🌐 **Ссылка на сайт:**\n"
            f"{WEBSITE_URL}"
        )

        keyboard = [
            [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(message, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await query.edit_message_text(
            "❌ Ошибка: не получилось зарегистрироваться. Попробуйте позже."
        )


async def show_more_boards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    current_page = context.user_data.get('boards_page', 0)
    context.user_data['boards_page'] = current_page + 1

    user = query.from_user

    if 'all_boards' in context.user_data:
        data = context.user_data['all_boards']
    else:
        data, error = await call_api(f"/api/users/{user.id}/boards-with-roles")
        if error:
            await query.edit_message_text(f"❌ Ошибка при загрузке досок: {error}")
            return
        context.user_data['all_boards'] = data

    boards_per_page = 10
    current_page = context.user_data.get('boards_page', 0)
    start_idx = current_page * boards_per_page
    end_idx = start_idx + boards_per_page

    boards_on_page = data[start_idx:end_idx]

    keyboard = []

    if current_page > 0:
        keyboard.append([
            InlineKeyboardButton("◀️ Назад", callback_data="boards_back")
        ])

    for board in boards_on_page:
        emoji = "🌐" if board.get("is_public", False) else "🔒"
        board_name = board.get("name", "Без названия")[:20]
        board_id = board.get("id")

        user_role = board.get("user_role", "")
        if user_role == "owner":
            role_emoji = "👑"
        elif user_role == "collaborator":
            role_emoji = "👥"
            owner_name = board.get("owner_username", "")
            if owner_name:
                board_name = f"{board_name} (от {owner_name})"
        else:
            role_emoji = ""

        keyboard.append([
            InlineKeyboardButton(
                f"{emoji} {role_emoji} {board_name}",
                callback_data=f"board_{board_id}"
            )
        ])

    if end_idx < len(data):
        keyboard.append([
            InlineKeyboardButton("Далее ▶️", callback_data="more_boards")
        ])

    keyboard.append([InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    total_pages = (len(data) + boards_per_page - 1) // boards_per_page
    page_info = f" (Страница {current_page + 1} из {total_pages})" if total_pages > 1 else ""

    await query.edit_message_text(
        f"📋 Ваши доски ({len(data)}){page_info}:\n\n"
        f"👑 - вы владелец\n"
        f"👥 - вы соавтор\n\n"
        "Выберите доску для управления:",
        reply_markup=reply_markup
    )


async def show_previous_boards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    current_page = context.user_data.get('boards_page', 1)
    new_page = max(0, current_page - 1)
    context.user_data['boards_page'] = new_page

    user = query.from_user

    if 'all_boards' in context.user_data:
        data = context.user_data['all_boards']
    else:
        data, error = await call_api(f"/api/users/{user.id}/boards-with-roles")
        if error:
            await query.edit_message_text(f"❌ Ошибка при загрузке досок: {error}")
            return
        context.user_data['all_boards'] = data

    boards_per_page = 10
    start_idx = new_page * boards_per_page
    end_idx = start_idx + boards_per_page

    boards_on_page = data[start_idx:end_idx]

    keyboard = []

    if new_page > 0:
        keyboard.append([
            InlineKeyboardButton("◀️ Назад", callback_data="boards_back")
        ])

    for board in boards_on_page:
        emoji = "🌐" if board.get("is_public", False) else "🔒"
        board_name = board.get("name", "Без названия")[:20]
        board_id = board.get("id")

        user_role = board.get("user_role", "")
        if user_role == "owner":
            role_emoji = "👑"
        elif user_role == "collaborator":
            role_emoji = "👥"
            owner_name = board.get("owner_username", "")
            if owner_name:
                board_name = f"{board_name} (от {owner_name})"
        else:
            role_emoji = ""

        keyboard.append([
            InlineKeyboardButton(
                f"{emoji} {role_emoji} {board_name}",
                callback_data=f"board_{board_id}"
            )
        ])

    if end_idx < len(data):
        keyboard.append([
            InlineKeyboardButton("Далее ▶️", callback_data="more_boards")
        ])

    keyboard.append([InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    total_pages = (len(data) + boards_per_page - 1) // boards_per_page
    page_info = f" (Страница {new_page + 1} из {total_pages})" if total_pages > 1 else ""

    try:
        await query.edit_message_text(
            f"📋 Ваши доски ({len(data)}){page_info}:\n\n"
            f"👑 - вы владелец\n"
            f"👥 - вы соавтор\n\n"
            "Выберите доску для управления:",
            reply_markup=reply_markup
        )
    except Exception as e:
        if "Message is not modified" not in str(e):
            logger.error(f"Ошибка при обновлении сообщения: {e}")
            await query.message.reply_text(
                f"📋 Ваши доски ({len(data)}){page_info}:\n\n"
                f"👑 - вы владелец\n"
                f"👥 - вы соавтор\n\n"
                "Выберите доску для управления:",
                reply_markup=reply_markup
            )

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CallbackQueryHandler(board_members_list, pattern="^board_members_\\d+$"))
    application.add_handler(CallbackQueryHandler(board_settings_menu, pattern="^board_settings_\\d+$"))
    application.add_handler(CallbackQueryHandler(delete_board_start, pattern="^delete_board_start_\\d+$"))
    application.add_handler(CallbackQueryHandler(delete_board_confirm, pattern="^delete_board_confirm_\\d+$"))
    application.add_handler(CallbackQueryHandler(edit_board_privacy_start, pattern="^edit_board_privacy_\\d+$"))
    application.add_handler(CallbackQueryHandler(show_more_boards, pattern="^more_boards$"))
    application.add_handler(CallbackQueryHandler(show_previous_boards, pattern="^boards_back$"))
    application.add_handler(
        CallbackQueryHandler(process_board_privacy_change, pattern="^set_privacy_(private|public)_\\d+$"))

    application.add_handler(
        CallbackQueryHandler(remove_collaborator_select, pattern="^remove_collaborator_select_\\d+$"))

    edit_name_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_board_name_start, pattern="^edit_board_name_\\d+$")],
        states={
            EDIT_BOARD_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_board_name_edit),
                CommandHandler("cancel", cancel)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
        per_message=False
    )
    application.add_handler(edit_name_handler)

    edit_desc_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_board_desc_start, pattern="^edit_board_desc_\\d+$")],
        states={
            EDIT_BOARD_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_board_desc_edit),
                CommandHandler("skip", skip_board_description_edit),
                CommandHandler("cancel", cancel)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
        per_message=False
    )
    application.add_handler(edit_desc_handler)

    register_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(register_confirmation, pattern="^register_(yes|no)$")
        ],
        states={
            REGISTER_CONFIRM: []
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=False,
        per_message=False
    )

    create_board_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(create_board_start, pattern="^create_board$")
        ],
        states={
            BOARD_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_board_name),
                CommandHandler("cancel", cancel)
            ],
            BOARD_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_board_description),
                CommandHandler("skip", skip_board_description),
                CommandHandler("cancel", cancel)
            ],
            BOARD_VISIBILITY: [
                CallbackQueryHandler(process_board_visibility, pattern="^visibility_(private|public|cancel)$"),
                CommandHandler("cancel", cancel)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
        per_message=False
    )

    add_collaborator_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(add_collaborator_start, pattern="^add_collaborator_\\d+$")
        ],
        states={
            ADD_COLLABORATOR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_collaborator_process),
                CommandHandler("cancel", cancel)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
        per_message=False
    )
    application.add_handler(add_collaborator_handler)

    remove_collaborator_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(remove_collaborator_confirm, pattern="^remove_collaborator_\\d+_\\d+$")
        ],
        states={
            REMOVE_COLLABORATOR_CONFIRM: [
                CallbackQueryHandler(remove_collaborator_execute, pattern="^confirm_remove_collaborator_\\d+_\\d+$"),
                CommandHandler("cancel", cancel)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
        per_message=False
    )
    application.add_handler(remove_collaborator_handler)

    delete_content_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(delete_content_confirm, pattern="^delete_item_\\d+$")
        ],
        states={
            DELETE_CONFIRM: [
                CallbackQueryHandler(delete_content_execute, pattern="^confirm_delete_\\d+$"),
                CommandHandler("cancel", cancel)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(delete_content_list, pattern="^delete_content_\\d+$")
        ],
        allow_reentry=True,
        per_message=False
    )
    application.add_handler(delete_content_handler)

    add_content_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(process_content_type, pattern="^content_type_(text|image|video|audio|gif)$"),
        ],
        states={
            ADD_TEXT_CONTENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_text_content),
                CommandHandler("cancel", cancel)
            ],
            ADD_FILE_CONTENT: [
                MessageHandler(filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.ANIMATION, add_file_content),
                CommandHandler("cancel", cancel)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
        per_message=False
    )
    application.add_handler(add_content_handler)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("cancel", cancel))

    application.add_handler(register_handler)
    application.add_handler(create_board_handler)
    application.add_handler(add_collaborator_handler)
    application.add_handler(delete_content_handler)
    application.add_handler(add_content_handler)

    application.add_handler(CallbackQueryHandler(show_main_menu, pattern="^main_menu$"))
    application.add_handler(CallbackQueryHandler(check_status, pattern="^check_status$"))
    application.add_handler(CallbackQueryHandler(my_boards, pattern="^my_boards$"))
    application.add_handler(CallbackQueryHandler(board_detail, pattern="^board_\\d+$"))
    application.add_handler(CallbackQueryHandler(edit_board, pattern="^edit_board_\\d+$"))
    application.add_handler(CallbackQueryHandler(add_content_start, pattern="^add_content_\\d+$"))
    application.add_handler(CallbackQueryHandler(delete_content_list, pattern="^delete_content_\\d+$"))
    application.add_handler(CallbackQueryHandler(share_board, pattern="^share_board_\\d+$"))
    application.add_handler(CallbackQueryHandler(make_board_public, pattern="^make_public_\\d+$"))
    application.add_handler(CallbackQueryHandler(my_data, pattern="^my_data$"))
    application.add_handler(CallbackQueryHandler(help_command, pattern="^help$"))
    application.add_handler(CallbackQueryHandler(register_start_callback, pattern="^register_start$"))

    application.add_error_handler(error_handler)

    logger.info("🤖 MoodBoard бот запускается...")
    logger.info(f"API URL: {API_URL}")
    logger.info(f"Website URL: {WEBSITE_URL}")

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()