from pymongo import MongoClient
import os
from flask import Flask, request, render_template
app = Flask(__name__)

client = MongoClient(os.environ.get('MONGODB_URL'))
db = client.rmdr

@app.route("/")
def hello():
    return "Hello World!"

@app.route("/webhook", methods=['GET', 'POST'])
def webhook():
    VERIFY_TOKEN = "NSjntmHrbzysHOEX6F4DrG6P4zAprPUxdHpsUKyR"
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
                app.logger.warning(entry.get('messaging')[0].get('message'))
            return 'EVENT_RECEIVED'
        else:
            '', 404
    return '', 403
