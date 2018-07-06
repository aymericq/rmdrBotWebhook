from pymongo import MongoClient
import os
from flask import Flask, request, render_template
import requests
import json

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
        if(body.get('object') == 'page'):
            for entry in body.get('entry'):
                if 'message' in entry.get('messaging')[0]:
                    db.logs.insert_one(body)
                    message = entry.get('messaging')[0].get('message')
                    handle_message(message, entry.get('messaging')[0].get('sender').get('id'))
                    if 'attachments' in message:
                        handle_attachments(message.get('attachments'), entry.get('messaging')[0].get('sender').get('id'))
            return 'EVENT_RECEIVED'
    return '', 403

def handle_message(message, sender_psid):
    if 'text' in message and not('is_echo' in message):
        if message.get('text').lower().find("bonjour") != -1:
            # TODO : recup les infos de profil avec < https://graph.facebook.com/v2.6/<PSID>?fields=first_name,last_name,profile_pic&access_token=<PAGE_ACCESS_TOKEN>" >
            r = requests.get("https://graph.facebook.com/v2.6/{}?fields=first_name,last_name&access_token={}".format(sender_psid, PAGE_ACCESS_TOKEN))
            body = r.json()
            resp_text = "Bonjour {}.".format(body.get("first_name"))
            if db.users.count({"psid" : sender_psid}) >= 1:
                resp_text += "\n\
                Bienvenue à nouveau parmi nous ! :)"
            else:
                user = {
                    "first_name" : body.get("first_name"),
                    "last_name" : body.get("last_name"),
                    "psid" : sender_psid,
                    "films" : []
                }
                db.users.insert_one(user)
            resp_text += "\n\
            Qu'est-ce qui t'ammène ?"
            res = {
                "text" : resp_text,
                "quick_replies" : [
                    {
                        "content_type":"text",
                        "title":"Ajout film vu"
                    },
                    {
                        "content_type":"text",
                        "title":"Ajout envie"
                    },
                ]
            }
            call_send_API(res, sender_psid)

def handle_attachments(attachments, sender_psid):
    attachment = attachments[0]
    res = {
        "text" : "Cette image est également disponible à l'url : {}".format(attachment.get('payload').get('url'))
    }
    call_send_API(res, sender_psid)

def call_send_API(res, sender_psid):
    request_body = {
        "recipient": {
            "id": sender_psid
        },
        "message": res
    }
    requests.post('https://graph.facebook.com/v2.6/me/messages?access_token='+PAGE_ACCESS_TOKEN, json = request_body)