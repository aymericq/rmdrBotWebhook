from pymongo import MongoClient
import os
from flask import Flask, request, render_template
import requests

app = Flask(__name__)

client = MongoClient(os.environ.get('MONGODB_URL'))
VERIFY_TOKEN = os.environ.get('FB_VERIFY_TOKEN')
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
db = client.rmdr

@app.route("/")
def hello():
    return "Hello World!"

@app.route("/webhook", methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if('hub.mode' in request.args and 'hub.verify_token' in request.args and 'hub.challenge' in request.args):
            mode = request.args['hub.mode']
            token = request.args['hub.verify_token']
            challenge = request.args['hub.challenge']
            if mode == 'subscribe' and token == VERIFY_TOKEN:
                app.logger.info('WEBHOOK_VERIFIED')
                return challenge
            else:
                resp = '', 403
                return resp
    elif request.method == 'POST':
        body = request.get_json()
        db.logs.insert_one(body)
        if(body.get('object') == 'page'):
            for entry in body.get('entry'):
                for message in entry.get("messaging"):
                    handleMessage(messaging.message, messaging.sender.id)
            return 'EVENT_RECEIVED'
        else:
            '', 404
    return '', 403

def handleMessage(message, sender_psid):
    if text in message:
        res = {
            "text" : "Vous avez envoyé : '" + message.get('text') + "'."
        }
        callSendAPI(res, sender_psid)

def callSendAPI(sender_psid, res):
    request_body = {
        "recipient": {
            "id": sender_psid
        },
        "message": req
    }
    r = requests.post('https://graph.facebook.com/v2.6/me/messages?access_token='+PAGE_ACCESS_TOKEN, request_body)