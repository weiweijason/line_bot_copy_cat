from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)

# 初始化 Firebase Admin SDK
cred = credentials.Certificate('src/serviceAccountKey.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

configuration = Configuration(access_token='55NGn5yJij8QKVilZXCUI3fyn9UheWmYTVpbjtnzyklQR4FRtXHYKQYiuuJV9oLUb7gXfg5N0O3b556wMe7+vVOaRtAx0e3IeBdCIzg+1TQA+Ks7uoeseofTk6NKZrkCDhvz94IjOZmqKKt2ofrYwgdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('d4b7963c257240af6564ccaf2e1730dc')

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
            user_states[user_id]['step'] = 1
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="請輸入您的名稱：")]
                )
            )
        elif user_states[user_id]['step'] == 1:
            user_states[user_id]['name'] = user_message
            user_states[user_id]['step'] = 2
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="請輸入您的所在地區：")]
                )
            )
        elif user_states[user_id]['step'] == 2:
            user_states[user_id]['location'] = user_message
            user_states[user_id]['step'] = 0

            # 儲存使用者資料到 Firebase
            doc_ref = db.collection('users').document(user_id)
            doc_ref.set({
                'name': user_states[user_id]['name'],
                'location': user_states[user_id]['location']
            })

            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="您的資料已儲存。")]
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
    app.run()