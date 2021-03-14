from flask import Flask, request, abort, jsonify, render_template
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    FollowEvent,
    MessageEvent,
    TextMessage,
    TextSendMessage,
)

import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

app = Flask(__name__, static_folder='static')
CORS(app)

# データベースの設定
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get('DATABASE_URL')
db = SQLAlchemy(app)

# 環境変数を読み込む
CHANNEL_ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET')
LIFF_CHANNEL_ID = os.environ.get('LIFF_CHANNEL_ID')
LIFF_ID = os.environ.get('LIFF_ID')

# LINE Botの設定
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)


class user_todo(db.Model):
    __tablename__ = 'user_todo'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(255))
    is_progress = db.Column(db.Boolean, default=True)
    todo_detail = db.Column(db.String(255))
    created_at = db.Column(
        db.DateTime,
        default=datetime.now()
    )
    updated_at = db.Column(
        db.DateTime,
        server_default=db.text('CURRENT_TIMESTAMP')
    )

    def __init__(self, data):
        self.user_id = data['user_id']
        self.is_progress = data['is_progress']
        self.todo_detail = data['todo_detail']

    def __repr__(self):
        return '<user_todo> {}'.format(self.user_id)


@app.route('/')
def login():
    # ログイン画面を表示
    return render_template('login.html', liffId=LIFF_ID)


@app.route('/lists')
def lists():
    todo_lists = []
    user_name = ''
    # IDトークンをパラメータから取得
    id_token = request.args.get('id_token', None)
    if id_token:
        # LIFFのユーザーデータを取得
        data = {
            'id_token': id_token,
            'client_id': LIFF_CHANNEL_ID
        }
        verifyed_data = requests.post(
            'https://api.line.me/oauth2/v2.1/verify', data=data)
        if verifyed_data.status_code == 200:
            user_info = verifyed_data.json()
            user_id = user_info['sub']
            user_name = user_info['name']
            print(user_info)
            # TODOデータの中から該当ユーザーの未完了タスクを取得
            todo_data = db.session.query(user_todo).\
                filter(user_todo.user_id == user_id,
                       user_todo.is_progress.is_(True))
            for data in todo_data:
                param = {
                    'todo_detail': data.todo_detail,
                    'updated_at': data.updated_at.strftime('%Y–%m–%d %H:%M:%S'),
                }
                todo_lists.append(param)
    return render_template('lists.html', user_name=user_name, todo_lists=todo_lists)


@app.route('/insert_todo', methods=['POST'])
def insert_todo():
    body = request.get_json()
    app.logger.info('Request body: ' + json.dumps(body))

    # DBに登録
    todoDB = user_todo(body)
    db.session.add(todoDB)
    db.session.commit()

    response = {
        "message": "OK",
        "status": 200
    }
    return jsonify(response)


@app.route('/callback', methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    # リクエストボディを取得
    body = request.get_data(as_text=True)
    print("Request body: " + body)

    # 接続チェック
    data = json.loads(body)
    if not data["events"]:
        return "OK"

    # Webhookハンドラーを登録
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    body = {
        'user_id': event.source.user_id,
        "todo_detail": event.message.text,
        'is_progress': True,
    }

    # DBに登録
    todoDB = user_todo(body)
    db.session.add(todoDB)
    db.session.commit()

    message_obj = TextSendMessage(text='タスクを追加しました')
    line_bot_api.reply_message(event.reply_token, message_obj)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
