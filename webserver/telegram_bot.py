from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
import logging
import subprocess
import os

# 로깅 설정
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = "7904503518:AAHou71KDVe3mLRSoPFyyHenAC4XrjlMyM8"
MINSU = 1985373534

# ✅ 하단 버튼 (ReplyKeyboardMarkup) 설정
reply_keyboard = [
    ["수익차트", "유저ID", "바이낸스수익"],
    ["ℹ️ 도움말", "❌ 종료"]
]
reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=False)

# ✅ 새로운 사용자에게 환영 메시지 표시
async def welcome(update: Update, context: CallbackContext) -> None:
    if update.message is None:
        return

    await update.message.reply_text("안녕하세요! 오토남 봇입니다. 원하는 메뉴를 선택하세요.", reply_markup=reply_markup)

# ✅ 버튼을 눌렀을 때 처리
async def handle_message(update: Update, context: CallbackContext) -> None:
    if update.message is None:
        return

    text = update.message.text
    user = update.message.from_user

    match text:
        case "수익차트":
            if user.id == MINSU:
                await update.message.reply_text("http://kook.iptime.org:5551", reply_markup=reply_markup)
            else:
                await update.message.reply_text("권한이 없습니다.", reply_markup=reply_markup)

        case "바이낸스수익":
            if user.id == MINSU:
                await update.message.reply_text("📊 바이낸스 수익 현황 보고서를 생성 중입니다. 잠시만 기다려주세요...", reply_markup=reply_markup)
                try:
                    # 프로젝트 루트 경로를 기준으로 스크립트 경로 설정
                    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
                    script_path = os.path.join(project_root, 'kook', 'binance', 'yang_bot_report.py')
                    
                    # 스크립트를 백그라운드에서 실행
                    # 윈도우 cp949 인코딩 오류를 방지하기 위해 PYTHONIOENCODING을 utf-8로 설정합니다.
                    env = os.environ.copy()
                    env['PYTHONIOENCODING'] = 'utf-8'
                    process = subprocess.Popen(
                        ['python', script_path], 
                        cwd=project_root, 
                        env=env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        encoding='utf-8'
                    )
                    logger.info(f"Executing script: {script_path} with PID: {process.pid}")

                    # 스크립트 실행이 완료될 때까지 기다리고, 출력을 로깅합니다.
                    stdout, stderr = process.communicate()

                    if stdout:
                        logger.info(f"Script stdout:\n{stdout}")
                    if stderr:
                        logger.error(f"Script stderr:\n{stderr}")

                except Exception as e:
                    logger.error(f"Error executing yang_bot_report.py: {e}")
                    await update.message.reply_text("❌ 보고서 스크립트 실행 중 오류가 발생했습니다.", reply_markup=reply_markup)
            else:
                await update.message.reply_text("권한이 없습니다.", reply_markup=reply_markup)

        case "유저ID":
            await update.message.reply_text("당신의ID : " + str(user.id), reply_markup=reply_markup)

        case "ℹ️ 도움말":
            await update.message.reply_text("ℹ️ 도움말: 필요한 정보를 제공합니다!", reply_markup=reply_markup)

        case "❌ 종료":
            await update.message.reply_text("❌ 메뉴를 닫습니다.", reply_markup=reply_markup)

        case _:
            await update.message.reply_text(f"당신이 입력한 내용: {text}", reply_markup=reply_markup)

# ✅ /글쓰기 명령어 처리
async def write_post(update: Update, context: CallbackContext) -> None:
    if update.message is None:
        return

    if not context.args:
        await update.message.reply_text("❗ 사용법: /w 제목:제목, 링크:https://example.com", reply_markup=reply_markup)
        return

    # ✅ 메시지에서 "title"과 "link" 추출 (키 값 수정)
    params = " ".join(context.args)
    parts = {k.strip().lower(): v.strip() for k, v in (item.split(":", 1) for item in params.split(",") if ":" in item)}

    title = parts.get("제목", "제목 없음")
    link = parts.get("링크", "")

    if not link.startswith("http"):
        await update.message.reply_text("❌ 유효한 링크를 입력하세요! 예: /w 제목:복권 뉴스, 링크:https://example.com", reply_markup=reply_markup)
        return

    await update.message.reply_text(f"📝 제목: {title}\n🔗 링크: {link}\n\n✍️ 글을 생성 중...")

    # ChatGPT 기능은 현재 비활성화 (chatgpt 모듈이 없음)
    if user.id == MINSU:
        await update.message.reply_text("⚠️ ChatGPT 기능은 현재 사용할 수 없습니다.", reply_markup=reply_markup)
    else:
        await update.message.reply_text("⚠️ 권한이 없습니다.", reply_markup=reply_markup)

# ✅ /start 명령어 처리
async def start(update: Update, context: CallbackContext) -> None:
    if update.message is None:
        return

    user = update.message.from_user
    await update.message.reply_text("안녕하세요! 오토남 봇입니다. 원하는 메뉴를 선택하세요.\n유저ID:"+str(user.id), reply_markup=reply_markup)

# ✅ 에러 핸들러
async def error_handler(update: object, context: CallbackContext) -> None:
    logger.error(f"Exception while handling an update: {context.error}")
    if update and hasattr(update, 'message') and update.message:
        await update.message.reply_text("❌ 오류가 발생했습니다. 잠시 후 다시 시도해주세요.", reply_markup=reply_markup)

# ✅ 메인 함수
def main():
    try:
        application = Application.builder().token(TOKEN).build()

        # ✅ 새로운 채팅방에 참가한 경우만 welcome 메시지 표시
        application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

        # ✅ 사용자가 버튼을 눌렀을 때 동작
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        # ✅ /start 명령어 추가
        application.add_handler(CommandHandler("start", start))

        # ✅ /글쓰기 명령어 추가
        application.add_handler(CommandHandler("w", write_post))

        # ✅ 에러 핸들러 추가
        application.add_error_handler(error_handler)

        logger.info("텔레그램 봇을 시작합니다...")
        application.run_polling(drop_pending_updates=True)  # 이전 업데이트 무시
        
    except Exception as e:
        logger.error(f"봇 시작 중 오류 발생: {e}")
        raise

if __name__ == "__main__":
    main()
