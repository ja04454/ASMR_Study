import time

from flask import Flask, render_template, redirect,url_for
from pymongo import MongoClient
import requests
import certifi
import re

from apscheduler.schedulers.background import BackgroundScheduler

client = MongoClient('mongodb+srv://test:sparta@cluster0.2rz7w.mongodb.net/Cluster0?retryWrites=true&w=majority',tlsCAFile=certifi.where())

db = client.ASMR_Study

app = Flask(__name__)





@app.route('/')
def index():
    #현재 index 페이지가 없기 때문에 main 함수로 요청을 돌려버림
    return redirect(url_for('main'))
    #return render_template('index.html')

@app.route("/main", methods=["GET"])
def main():

    asmr_list = list(db.asmrs.find({}, {'_id':False}))

    #DB에서 저장된 asmrs 리스트를 가져다가 뽑아옴
    asmr_list = list(db.asmrs.find({}))

    #return jsonify({'asmrs':asmr_list})

    #Jinja2 방식으로 SSR(Server side rendering)를 사용해 main.html 페이지를 렌더링
    #렌더링 시 asmrs라는 이름으로 가져온 asmr_list 데이터를 보내줌
    return render_template('main.html',asmrs=asmr_list)


# 20220509 김윤교 작업본, Client단에서 시청자 수를 가져오기 위해 만든 크롤링
# 이벤트가 클라이언트 기준으로 실행되기 때문에 과부화 우려가 있음
# 20220510 작업본에서 이벤트를 Server에서 주기적으로 실행하는 방식으로 변경
""" 20220510 비활성화
@app.route("/getViewers", methods=["POST"])
def getViewers():
    #Client 단에서 보내준 link 정보를 가져와 변수에 담음
    link = request.form['link']
    viewers = '';
    #requests를 쓰기 위한 header 정보
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.86 Safari/537.36'}

    #대상 Asmr에 link에 맞춰 페이지 데이터를 가져옴
    data = requests.get(link, headers=headers)

    #가져온 페이지 데이터를 text 형태로 변환해 videoViewCountRenderer란 단어를 검색한 뒤 그 위치 반환
    startIndex = data.text.find('videoViewCountRenderer')

    #만약 검색된 단어위치가 존재한다면 실행
    if(startIndex != -1):
        #videoViewCountRenderer 검색된 위치부터 isLive란 단어를 검색해 그 위치를 찾음
        endIndex = data.text.find('isLive', startIndex)
        #검색된 단어들의 위치를 기반으로 텍스트를 잘라냄
        targetText = data.text[startIndex:endIndex]
        #잘라낸 텍스트에서 문자를 제거하고 숫자(시청자 수)를 추출함
        viewers = re.sub(r'[^0-9]', '', targetText)

    #기존에 bs4 방식으로 selector를 이용해 시청자 수를 가져오려 했지만 제대로 페이지를 읽어오지 못함
    #아마 유튜브는 스크립트로 페이지를 재구성 하기 때문에 온전한 페이지를 가져오기 위해서는 다른 라이브러리를 혼합하거나, 스크립트가 전부 실행되길 기다린 후 가져와야하는 작업이 필요해 보임
    #현재는 requests로 가져온 페이지 데이터에 시청자수를 바로 추출하는 방식으로 해결
    #viewer_text = soup.select_one('#count > ytd-video-view-count-renderer > span.view-count.style-scope.ytd-video-view-count-renderer').string
    #viewers = re.sub(r'[^0-9]', '', viewer_text)

    #시청자 수를 json 형태로 반환
    return jsonify({'viewers':viewers})
"""

# 20220510 시청자 수 크롤링을 서버에서 진행함
def getViewers():
    #DB에서 저장된 asmrs 리스트를 가져다가 뽑아옴
    asmr_list = list(db.asmrs.find({}))
    for asmr in asmr_list:
        link = asmr['link']
        viewers = '';
        #requests를 쓰기 위한 header 정보
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.86 Safari/537.36'}

        #대상 Asmr에 link에 맞춰 페이지 데이터를 가져옴
        data = requests.get(link, headers=headers)

        #requests가 정상인 경우
        if data.ok:
            #가져온 페이지 데이터를 text 형태로 변환해 videoViewCountRenderer란 단어를 검색한 뒤 그 위치 반환
            startIndex = data.text.find('videoViewCountRenderer')

            #만약 검색된 단어위치가 존재한다면 실행
            if(startIndex != -1):
                #videoViewCountRenderer 검색된 위치부터 isLive란 단어를 검색해 그 위치를 찾음
                endIndex = data.text.find('isLive', startIndex)
                #검색된 단어들의 위치를 기반으로 텍스트를 잘라냄
                targetText = data.text[startIndex:endIndex]
                #잘라낸 텍스트에서 문자를 제거하고 숫자(시청자 수)를 추출함
                viewers = re.sub(r'[^0-9]', '', targetText)
            db.asmrs.update_one({'_id':asmr['_id']},{"$set" : {"viewers": viewers}})

#스케쥴러를 이용해 10분마다 크롤링
scheduler = BackgroundScheduler()
scheduler.add_job(func=getViewers, trigger="interval", seconds=600)
scheduler.start()

#디버그 모드에선 플라스크는 앱을 두번 로드함
#두번 로드시 스케쥴러도 두번 실행되기 때문에 use_reloader를 이용해 비활성화
if __name__ == '__main__':
    app.run('0.0.0.0', port=5000, debug=True, use_reloader=False)

