import requests

# 텔레그램 봇 토큰 (BotFather에서 받은 것)
TOKEN = "7904503518:AAHou71KDVe3mLRSoPFyyHenAC4XrjlMyM8"
# 메시지를 보낼 채팅 ID (@userinfobot을 통해 받은 값)
CHAT_ID = "1985373534"

# 텔레그램 메시지 전송 함수
def send(msg):
    try:
        if not TOKEN or not CHAT_ID:
            print("🚨 [오류] TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 설정되지 않았습니다.")
            return

        # 메시지 길이 제한 (4096자 초과 시 분할)
        max_length = 4096
        messages = [msg[i:i+max_length] for i in range(0, len(msg), max_length)]

        for message in messages:
            response = requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                data={"chat_id": CHAT_ID, "text": message}
            )
            response_data = response.json()

            if response.status_code == 200 and response_data.get("ok"):
                print(f"✅ [성공] 메시지 전송 완료: {message[:50]}...")
            else:
                print(f"❌ [실패] 응답 코드: {response.status_code}, 메시지: {response_data}")

    except requests.exceptions.RequestException as ex:
        print(f"🚨 [요청 오류] {ex}")
    except Exception as ex:
        print(f"🚨 [기타 오류] {ex}")




def SendMessage(msg):
    """호환용 함수: 기존 line_alert.SendMessage와 동일한 시그니처 유지"""
    return send(msg)