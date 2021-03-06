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
def hello_world():
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
                db.logs.insert_one(body)
                if 'message' in entry.get('messaging')[0]:
                    message = entry.get('messaging')[0].get('message')
                    handle_message(message, entry.get('messaging')[0].get('sender').get('id'))
                    if 'attachments' in message:
                        handle_attachments(message.get('attachments'), entry.get('messaging')[0].get('sender').get('id'))
                elif 'postback' in entry.get('messaging')[0]:
                    handle_postback(entry.get('messaging')[0].get('postback').get('payload'), entry.get('messaging')[0].get('sender').get('id'))
            return 'EVENT_RECEIVED'
    return '', 403

def handle_message(message, sender_psid):
    if 'text' in message and not('is_echo' in message):
        state =  db.users.find_one({"psid" : sender_psid}, {"_id" : 0, "state" : 1}).get('state')
        print(state)
        if message.get('text').lower().find("bonjour") != -1:
            res = hello(sender_psid)
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
                db.users.update({"psid" : sender_psid}, {"$set":{"state" : "WAITING_WISH_MOVIE_TITLE"}})
                call_send_API(res, sender_psid)
        elif state == "WAITING_SEEN_MOVIE_TITLE":
            r = requests.get('http://www.omdbapi.com/?s={}&apikey={}'.format(message.get('text'), OMDB_API_KEY))
            body = r.json()
            if 'Search' in body:
                res = build_movie_list(body.get('Search'), 1, message.get('text'), "SEEN")
                call_send_API(res, sender_psid)
                db.users.update({"psid" : sender_psid}, {"$set":{"state" : "WAITING_SEEN_TITLE_SELECT_FROM_LIST"}})
            else:
                res = {
                    "text" : "Désolé, aucun film trouvé"
                }
                call_send_API(res, sender_psid)
        elif state == "WAITING_WISH_MOVIE_TITLE":
            r = requests.get('http://www.omdbapi.com/?s={}&apikey={}'.format(message.get('text'), OMDB_API_KEY))
            body = r.json()
            if 'Search' in body:
                res = build_movie_list(body.get('Search'), 1, message.get('text'), "WISH")
                call_send_API(res, sender_psid)
                db.users.update({"psid" : sender_psid}, {"$set":{"state" : "WAITING_WISH_TITLE_SELECT_FROM_LIST"}})
            else:
                res = {
                    "text" : "Désolé, aucun film trouvé"
                }
                call_send_API(res, sender_psid)

def handle_postback(payload, sender_psid):
    json_content = json.loads(payload)
    if 'origin' in json_content:
        if json_content.get('origin') == "WAITING_SEEN_TITLE_SELECT_FROM_LIST_VIEWMORE":
            range_factor = json_content.get('range_factor')
            query = json_content.get('original_search_query')
            r = requests.get('http://www.omdbapi.com/?s={}&apikey={}'.format(query, OMDB_API_KEY))
            body = r.json()
            if 'Search' in body:
                res = build_movie_list(body.get('Search'), range_factor, query, "SEEN")
                call_send_API(res, sender_psid)
                db.users.update({"psid" : sender_psid}, {"$set":{"state" : "WAITING_SEEN_TITLE_SELECT_FROM_LIST"}})
            else:
                res = {
                    "text" : "Désolé, aucun film trouvé"
                }
                call_send_API(res, sender_psid)
        elif json_content.get('origin') == "SELECT_SEEN_MOVIE_FROM_LIST":
            added_user_movie_type = add_movie(json_content, sender_psid, "SEEN")
            res = {}
            if added_user_movie_type == -1:
                res = {
                    "text" : "{} fait déjà partie de votre liste de films vus".format(json_content.get('imdb_title'))
                }
            else:
                res = {
                    "text" : "{} a bien été ajouté à ta liste de films vus.".format(json_content.get('imdb_title'))
                }
            call_send_API(res, sender_psid)
            db.users.update({"psid" : sender_psid}, {"$set":{"state" : "HELLO"}})
        elif json_content.get('origin') == "WAITING_WISH_TITLE_SELECT_FROM_LIST_VIEWMORE":
            range_factor = json_content.get('range_factor')
            query = json_content.get('original_search_query')
            r = requests.get('http://www.omdbapi.com/?s={}&apikey={}'.format(query, OMDB_API_KEY))
            body = r.json()
            if 'Search' in body:
                res = build_movie_list(body.get('Search'), range_factor, query, "WISH")
                call_send_API(res, sender_psid)
                db.users.update({"psid" : sender_psid}, {"$set":{"state" : "WAITING_WISH_TITLE_SELECT_FROM_LIST"}})
            else:
                res = {
                    "text" : "Désolé, aucun film trouvé"
                }
                call_send_API(res, sender_psid)
        elif json_content.get('origin') == "SELECT_WISH_MOVIE_FROM_LIST":
            added_user_movie_type = add_movie(json_content, sender_psid, "WISH")
            res = {}
            if added_user_movie_type == -1:
                res = {
                    "text" : "{} fait déjà partie de votre liste d'envies.".format(json_content.get('imdb_title'))
                }
            else:
                res = {
                    "text" : "{} a bien été ajouté à ta liste d'envies.".format(json_content.get('imdb_title'))
                }
            call_send_API(res, sender_psid)
            db.users.update({"psid" : sender_psid}, {"$set":{"state" : "HELLO"}})
        print("POSTBACK CONTAINS JSON")

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
    print(request_body)
    r = requests.post('https://graph.facebook.com/v2.6/me/messages?access_token='+PAGE_ACCESS_TOKEN, json = request_body)
    print(r.json())

def build_movie_list(omdb_result, range_factor, query, user_movie_type):
    VIEW_LIMIT = 4
    i = (range_factor - 1)*VIEW_LIMIT
    curr_limit = i + VIEW_LIMIT
    elements = []
    while i < curr_limit and i < len(omdb_result):
        payload = {
            "origin" : "SELECT_" + user_movie_type + "_MOVIE_FROM_LIST",
            "imdb_id" : omdb_result[i].get('imdbID'),
            "imdb_title" : omdb_result[i].get('Title')
        }
        poster_url = ""
        if omdb_result[i].get('Poster') != "N/A":
            poster_url = omdb_result[i].get('Poster')
        else:
            poster_url = "https://cdn140.picsart.com/253668100008212.png?r1024x1024"
        elements.append(
            {
                "title" : omdb_result[i].get('Title'),
                "image_url" : poster_url,
                "default_action": {
                    "type": "web_url",
                    "url": "https://www.imdb.com/title/{}/".format(omdb_result[i].get('imdbID')),
                    "messenger_extensions": True,
                    "webview_height_ratio": "tall"
                },
                "buttons": [
                    {
                        "title": "Choisir",
                        "type": "postback",
                        "payload": json.dumps(payload)
                    }
                ]
            }
        )
        i += 1
    
    viewmore_payload = {
        "origin" : "WAITING_" + user_movie_type + "_TITLE_SELECT_FROM_LIST_VIEWMORE",
        "range_factor" : range_factor+1,
        "original_search_query" : query
    }
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
                        "payload": json.dumps(viewmore_payload)           
                    }
                ]  
            }
        }
    }
    return res

def add_movie(mov_info, sender_psid, user_movie_type):
    existing_entry = db.films.find_one({"imdb_id" : mov_info.get('imdb_id')}, {"_id" : 1})
    inserted_id = -1
    if existing_entry == None:
        inserted_id = db.films.insert({
            "imdb_id" : mov_info.get('imdb_id'),
            "title" : mov_info.get('imdb_title'),
            "comments" : []
        })
    else:
        inserted_id = existing_entry.get('_id')
    already_added = db.users.find_one({"psid" : sender_psid, "films.imdb_id" : mov_info.get('imdb_id')}, {"_id" : 1})
    if already_added != None:
        return -1
    else:
        db.users.update({"psid" : sender_psid}, {"$push":{"films" : {
            "user_movie_type" : user_movie_type,
            "imdb_id" : mov_info.get('imdb_id'),
            "film_id" : inserted_id
        }}})
        return 0

def hello(sender_psid):
    r = requests.get("https://graph.facebook.com/v2.6/{}?fields=first_name,last_name&access_token={}".format(sender_psid, PAGE_ACCESS_TOKEN))
    body = r.json()
    resp_text = "Bonjour {}.".format(body.get("first_name"))
    if db.users.count({"psid" : sender_psid}) >= 1:
        resp_text += "\nBienvenue à nouveau parmi nous ! :)"
        resp_text += "\nQu'est-ce qui t'amène ?"
    else:
        user = {
            "first_name" : body.get("first_name"),
            "last_name" : body.get("last_name"),
            "psid" : sender_psid,
            "films" : [],
            "state" : "HELLO"
        }
        db.users.insert_one(user)
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
    db.users.update({"psid" : sender_psid}, {"$set":{"state" : "HELLO"}})
    res = {
        "text" : resp_text,
        "quick_replies" : quick_replies
    }
    return res