# ---------------------------------------------------------------------------------
# Name: LoveCustomSendFix
# Description: Отправляет в чат сообщение "Я тебя люблю" в формате blockquote
#              с поддержкой обычных эмодзи и кастомных (Telegram Premium) по ID.
#              Исправлена проблема совместимости с разными версиями Telethon:
#              если client.send_message не принимает entities, используется
#              низкоуровневый вызов functions.messages.SendMessageRequest.
# Author: adapted-from-user-example
# ---------------------------------------------------------------------------------
# meta developer: @NFTkarma
# scope: LoveCustomSendFix
# scope: LoveCustomSendFix 0.0.1
# ---------------------------------------------------------------------------------

import logging
import inspect
import random

from herokutl.types import Message
from .. import loader, utils

logger = logging.getLogger(__name__)


@loader.tds
class LoveCustomSendFix(loader.Module):
    """
    Модуль для отправки сообщения "Я тебя люблю"
    """

    strings = {
        "name": "LoveCustomSendFix",
        "usage": "Использование:\n.люблю\n.люблю 😍\n.люблю id:<custom_id>\n.setcustom 1234567890123456789\n.cleancustom",
        "sent": "Отправлено: {}",
        "no_emoji": "Эмодзи не задан. Используйте .setcustom или передайте эмодзи в команде.",
        "set_custom_ok": "Стандартный custom emoji id сохранён: {}",
        "cleared": "Стандартный custom emoji id очищен",
        "help": "Отправляет сообщение в виде цитаты (blockquote). Весь текст внутри цитаты — жирный. Поддерживает custom emoji .",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "default_emoji",
                "",
                "Стандартный текстовый эмодзи (символ)",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "custom_emoji_id",
                "",
                "Стандартный custom emoji id (числа)",
                validator=loader.validators.String(),
            ),
        )
        self._default_emoji = ""
        self._custom_emoji_id = ""

    async def client_ready(self, client, db):
        self.client = client
        self._default_emoji = self.config["default_emoji"] or ""
        self._custom_emoji_id = self.config["custom_emoji_id"] or ""

    @loader.command(
        ru_doc="Отправить 'Я тебя люблю' (опционально: добавить эмодзи/id). Пример: .люблю 😍 или .люблю id:123",
        en_doc="Send 'I love you' (optionally with emoji/id). Example: .люблю 😍 or .люблю id:123",
    )
    async def люблю(self, message: Message):
        """Отправляет blockquote 'Я тебя люблю' — весь текст внутри цитаты помечен как жирный.
           Поддерживает обычный текстовый эмодзи и кастомный эмодзи по id."""
        args_raw = utils.get_args_raw(message) or ""
        args = args_raw.strip()

        custom_id_for_message = None
        emoji_for_message = ""

        if args.startswith("id:"):
            maybe_id = args[3:].strip()
            digits = "".join(ch for ch in maybe_id if ch.isdigit())
            if digits:
                custom_id_for_message = digits
        elif args:
            emoji_for_message = args

        if not custom_id_for_message:
            custom_id_for_message = self._custom_emoji_id or None

        if not custom_id_for_message and not emoji_for_message:
            emoji_for_message = self._default_emoji or ""

        # Базовый текст (без markdown). Entities будут применены отдельно:
        base_text = "Я тебя люблю"

        # Где отправлять
        chat_id = getattr(message, "chat_id", None) or getattr(message, "to_id", None) or getattr(message, "peer_id", None)

        # Собираем текст — если кастомный эмодзи будет использован, вставляем плейсхолдер,
        # иначе добавляем текстовый эмодзи (если есть).
        placeholder = "◽"  # один символ-заменитель для кастомного эмодзи
        if custom_id_for_message:
            text = f"{base_text} {placeholder}"
        else:
            text = f"{base_text}" + (f" {emoji_for_message}" if emoji_for_message else "")

        # Функция для создания entity аккуратно в разных версиях Telethon
        def make_entity(cls, offset, length, **kwargs):
            if cls is None:
                return None
            try:
                sig = inspect.signature(cls.__init__)
                params = [p for p in list(sig.parameters.keys()) if p != "self"]
            except Exception:
                params = []
            # попытка по именованным параметрам
            for try_name in kwargs.keys():
                if try_name in params and "offset" in params and "length" in params:
                    try:
                        created = cls(offset=offset, length=length, **{try_name: kwargs[try_name]})
                        return created
                    except Exception:
                        pass
            # попытка позиционного конструктора
            try:
                created = cls(offset, length, *[kwargs[k] for k in kwargs.keys()])
                return created
            except Exception:
                pass
            return None

        # Попытка собрать необходимые классы сущностей из telethon.tl.types
        try:
            from telethon.tl import types as tltypes
        except Exception:
            tltypes = None

        # Найдём классы для BlockQuote, Bold и CustomEmoji (варианты имён для разных версий)
        BlockClass = None
        BoldClass = None
        CustomEmojiClass = None

        if tltypes is not None:
            for n in ("MessageEntityBlockQuote", "MessageEntityBlockquote", "MessageEntityBlock", "MessageEntityBlockQuote"):
                if hasattr(tltypes, n):
                    BlockClass = getattr(tltypes, n)
                    break
            for n in ("MessageEntityBold", "MessageEntityBoldText", "MessageEntityBold"):
                if hasattr(tltypes, n):
                    BoldClass = getattr(tltypes, n)
                    break
            for n in ("MessageEntityCustomEmoji",):
                if hasattr(tltypes, n):
                    CustomEmojiClass = getattr(tltypes, n)
                    break

        # Создаём entities: хотим, чтобы весь текст был и blockquote, и bold; кастомный эмодзи — своя entity
        entities = []

        # Попытка создать blockquote covering full text
        block_ent = None
        if BlockClass is not None:
            try:
                block_ent = None
                try:
                    block_ent = BlockClass(offset=0, length=len(text))
                except Exception:
                    try:
                        block_ent = BlockClass(0, len(text))
                    except Exception:
                        block_ent = None
                if block_ent is not None:
                    entities.append(block_ent)
            except Exception:
                block_ent = None

        # Попытка создать bold covering full text
        bold_ent = None
        if BoldClass is not None:
            try:
                bold_ent = None
                try:
                    bold_ent = BoldClass(offset=0, length=len(text))
                except Exception:
                    try:
                        bold_ent = BoldClass(0, len(text))
                    except Exception:
                        bold_ent = None
                if bold_ent is not None:
                    entities.append(bold_ent)
            except Exception:
                bold_ent = None

        # Если используется кастомный эмодзи — создаём entity для него и вставляем в entities
        custom_ent = None
        if custom_id_for_message and CustomEmojiClass is not None:
            try:
                # custom emoji offset: после base_text + space
                offset_for_custom = len(base_text) + 1
                # попробуем по-разному создать entity
                custom_ent = make_entity(CustomEmojiClass, offset_for_custom, 1, custom_emoji_id=int(custom_id_for_message), document_id=int(custom_id_for_message), custom_emoji=int(custom_id_for_message))
                if custom_ent is not None:
                    # поместим custom emoji entity после block и bold (order не критичен, но оставим в конце)
                    entities.append(custom_ent)
            except Exception:
                custom_ent = None

        # Если Telethon не предоставляет нужные entity-классы — всё равно попытаемся отправить текст (фоллбек)
        # Попытка отправки через client.send_message с entities/message_entities
        send = getattr(self.client, "send_message", None)
        if callable(send) and entities:
            try:
                sig = inspect.signature(send)
                params_names = list(sig.parameters.keys())
                if "entities" in params_names:
                    await self.client.send_message(chat_id, text, entities=entities)
                elif "message_entities" in params_names:
                    await self.client.send_message(chat_id, text, message_entities=entities)
                else:
                    raise TypeError("send_message no entities param")
                try:
                    await self._try_delete(message)
                except Exception:
                    pass
                return
            except TypeError:
                # перейдём к low-level
                pass
            except Exception as e:
                logger.exception(f"[LoveCustomSendFix] Ошибка при отправке через client.send_message с entities: {e}")
                # fallthrough to low-level

        # Попытка низкоуровневой отправки (functions.messages.SendMessageRequest)
        try:
            from telethon import functions
            try:
                peer = await self.client.get_input_entity(chat_id)
            except Exception:
                peer = chat_id
            random_id = random.getrandbits(63)
            # Если entities пусты, передадим None
            await self.client(functions.messages.SendMessageRequest(peer=peer, message=text, entities=entities or None, random_id=random_id))
            try:
                await self._try_delete(message)
            except Exception:
                pass
            return
        except Exception as e:
            logger.exception(f"[LoveCustomSendFix] Низкоуровневая отправка не удалась: {e}")
            # fallthrough to simple text responses

        # Если ничего не получилось с entity — отправим "ручной" вариант: обрамим текст символами цитаты и жирности
        # (фоллбек, но обычно Telethon поддерживает entities)
        try:
            # Попробуем отправить текст с визуальным префиксом цитаты и символами выделения жирного
            fallback_text = f"┏━ Цитата ━\n*{base_text}*"
            if not custom_id_for_message:
                if emoji_for_message:
                    fallback_text = f"┏━ Цитата ━\n*{base_text}* {emoji_for_message}"
            else:
                # при кастомном эмодзи — вставляем плейсхолдер (получатели без поддержки не увидят эмодзи)
                fallback_text = f"┏━ Цитата ━\n*{base_text}* {placeholder}"
            await utils.answer(message, fallback_text)
            await self._try_delete(message)
        except Exception as e:
            logger.exception(f"[LoveCustomSendFix] Финальный фоллбек не удался: {e}")
            try:
                await self.client.send_message(chat_id, base_text)
                await self._try_delete(message)
            except Exception as e2:
                logger.exception(f"[LoveCustomSendFix] Fallback send_message failed: {e2}")
                await utils.answer(message, self.strings["no_emoji"])

    @loader.command(
        ru_doc="Установить стандартный custom emoji id. Пример: .setcustom 1234567890123456789",
        en_doc="Set default custom emoji id. Example: .setcustom 1234567890123456789",
    )
    async def setcustom(self, message: Message):
        args_raw = utils.get_args_raw(message) or ""
        maybe_id = args_raw.strip()
        if not maybe_id:
            await utils.answer(message, "Укажите id. Пример: .setcustom 1234567890123456789")
            return
        digits = "".join(ch for ch in maybe_id if ch.isdigit())
        if not digits:
            await utils.answer(message, "Не найдено чисел в переданном значении. Укажите только цифры custom id.")
            return
        self.config["custom_emoji_id"] = digits
        self._custom_emoji_id = digits
        await utils.answer(message, self.strings["set_custom_ok"].format(digits))

    @loader.command(
        ru_doc="Очистить стандартный custom emoji id",
        en_doc="Clear default custom emoji id",
    )
    async def cleancustom(self, message: Message):
        self.config["custom_emoji_id"] = ""
        self._custom_emoji_id = ""
        await utils.answer(message, self.strings["cleared"])

    @loader.command(
        ru_doc="Показать справку по модулю",
        en_doc="Show module help",
    )
    async def lovehelp(self, message: Message):
        await utils.answer(message, self.strings["usage"])

    async def _try_delete(self, message: Message):
        try:
            delete_method = getattr(message, "delete", None)
            if callable(delete_method):
                await delete_method()
            else:
                remove = getattr(utils, "delete_message", None) or getattr(utils, "remove", None)
                if callable(remove):
                    await remove(message)
        except Exception:
            pass