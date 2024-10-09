from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
from dotenv import load_dotenv

# 載入 .env 檔案
load_dotenv()

app = Flask(__name__)

# 從環境變數中讀取 JSON 檔案內容
service_account_info = json.loads(os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON"))

# 初始化 Firebase Admin SDK
cred = credentials.Certificate(service_account_info)
firebase_admin.initialize_app(cred)
db = firestore.client()

configuration = Configuration(access_token=os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

user_states = {}

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text.lower()

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        if user_id not in user_states:
            user_states[user_id] = {'step': 0}

        if user_message in ["開始", "start"]:
            # 獲取使用者的顯示名稱
            profile = line_bot_api.get_profile(user_id)
            display_name = profile.display_name

            user_states[user_id]['name'] = display_name
            user_states[user_id]['step'] = 1

            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=f"歡迎 {display_name}，請輸入您的所在地區：")]
                )
            )
        elif user_states[user_id]['step'] == 1:
            user_states[user_id]['region'] = user_message
            user_states[user_id]['step'] = 0

            # 儲存使用者資料到 Firebase Firestore
            db.collection('User').add({
                'user_id': user_id,
                'name': user_states[user_id]['name'],
                'region': user_states[user_id]['region']
            })

            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="您的資料已儲存。")]
                )
            )
        elif user_message in ["我是誰", "who am i"]:
            # 查詢使用者資料
            users_ref = db.collection('User')
            query = users_ref.where('user_id', '==', user_id).limit(1)
            results = query.stream()

            user_name = None
            for doc in results:
                user_name = doc.to_dict().get('name')

            if user_name:
                reply_text = f"歡迎使用本系統 {user_name}"
            else:
                reply_text = "找不到您的資料，請先輸入 '開始' 來註冊。"

            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )
        else:
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="請輸入 '開始' 或 'Start' 來開始。")]
                )
            )

if __name__ == "__main__":
    app.run(host='127.0.0.1', port=8080)