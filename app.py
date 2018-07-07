from pymongo import MongoClient
import os
from flask import Flask, request, render_template
import requests
import json

app = Flask(__name__)

client = MongoClient(os.environ.get('MONGODB_URL'))
VERIFY_TOKEN = os.environ.get('FB_VERIFY_TOKEN')
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')
OMDB_API_KEY = os.environ.get('OMDB_API_KEY')
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
        state =  db.users.find_one({"psid" : sender_psid}, {"_id" : 0, "state" : 1}).get('state')
        print(state)
        if message.get('text').lower().find("bonjour") != -1:
            # TODO : recup les infos de profil avec < https://graph.facebook.com/v2.6/<PSID>?fields=first_name,last_name,profile_pic&access_token=<PAGE_ACCESS_TOKEN>" >
            r = requests.get("https://graph.facebook.com/v2.6/{}?fields=first_name,last_name&access_token={}".format(sender_psid, PAGE_ACCESS_TOKEN))
            body = r.json()
            resp_text = "Bonjour {}.".format(body.get("first_name"))
            quick_replies = []
            if db.users.count({"psid" : sender_psid}) >= 1:
                resp_text += "\nBienvenue à nouveau parmi nous ! :)"
                resp_text += "\nQu'est-ce qui t'amène ?"
                quick_replies = [
                    {
                        "content_type":"text",
                        "title":"Ajout film vu",
                        "payload":"ADD_SEEN_MOVIE"
                    },
                    {
                        "content_type":"text",
                        "title":"Ajout envie",
                        "payload":"ADD_WISH"
                    }
                ]
            else:
                user = {
                    "first_name" : body.get("first_name"),
                    "last_name" : body.get("last_name"),
                    "psid" : sender_psid,
                    "films" : [],
                    "state" : "HELLO"
                }
                db.users.insert_one(user)
            res = {
                "text" : resp_text,
                "quick_replies" : quick_replies
            }
            call_send_API(res, sender_psid)
        elif 'quick_reply' in message:
            payload = message.get('quick_reply').get('payload')
            if payload == "ADD_SEEN_MOVIE":
                res = {
                    "text" : "Quel est le titre ?"
                }
                db.users.update({"psid" : sender_psid}, {"$set":{"state" : "WAITING_SEEN_MOVIE_TITLE"}})
                call_send_API(res, sender_psid)
            elif payload == "ADD_WISH":
                res = {
                    "text" : "Quel est le titre ?"
                }
                db.users.update({"psid" : sender_psid}, {"$set":{"state" : "WAITING_WISH_TITLE"}})
                call_send_API(res, sender_psid)
        elif state == "WAITING_SEEN_MOVIE_TITLE":
            r = requests.get('http://www.omdbapi.com/?s={}&apikey={}'.format(message.get('text'), OMDB_API_KEY))
            body = r.json().get('Search')
            print(body)
            res = build_movie_list(body)
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
    r = requests.post('https://graph.facebook.com/v2.6/me/messages?access_token='+PAGE_ACCESS_TOKEN, json = request_body)
    print(r.json())

def build_movie_list(omdb_result):
    VIEW_LIMIT = 4
    i = 0
    elements = []
    while i < VIEW_LIMIT and i < len(omdb_result):
        elements.append(
            {
                "title" : omdb_result[i].get('Title'),
                "image_url" : omdb_result[i].get('Poster')
            }
        )
        i += 1
    
    res = {
        "attachment": {
            "type": "template",
            "payload": {
                "template_type": "list",
                "top_element_style": "compact",
                "elements": elements,
                "buttons": [
                    {
                        "title": "View More",
                        "type": "postback",
                        "payload": "payload"            
                    }
                ]  
            }
        }
    }
    return res