from flask import Flask, render_template,jsonify, request,redirect,url_for
from bs4 import BeautifulSoup
from pymongo import MongoClient
import requests
import certifi
import re

client = MongoClient('mongodb+srv://test:sparta@cluster0.2rz7w.mongodb.net/Cluster0?retryWrites=true&w=majority',tlsCAFile=certifi.where())
db = client.ASMR_Study

app = Flask(__name__)





@app.route('/')
def index():
    return redirect(url_for('main'))
    #return render_template('index.html')

@app.route("/main", methods=["GET"])
def main():
    asmr_list = list(db.asmrs.find({}))
    #return jsonify({'asmrs':asmr_list})
    return render_template('main.html',asmrs=asmr_list)


@app.route("/getViewers", methods=["POST"])
def getViewers():
    link = request.form['link']
    viewers = '';
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.86 Safari/537.36'}
    data = requests.get(link, headers=headers)
    startIndex = data.text.find('videoViewCountRenderer')
    if(startIndex != -1):
        endIndex = data.text.find('isLive', startIndex)
        targetText = data.text[startIndex:endIndex]
        viewers = re.sub(r'[^0-9]', '', targetText)
        print(viewers)


        #viewer_text = soup.select_one('#count > ytd-video-view-count-renderer > span.view-count.style-scope.ytd-video-view-count-renderer').string
    #viewers = re.sub(r'[^0-9]', '', viewer_text)
    return jsonify({'viewers':viewers})

if __name__ == '__main__':
    app.run('0.0.0.0', port=5000, debug=True)
