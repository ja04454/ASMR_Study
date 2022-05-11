import time

from flask import Flask, render_template, redirect, url_for, jsonify, request
from pymongo import MongoClient
import requests
import certifi
import re
import jwt
import hashlib

from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

client = MongoClient('mongodb+srv://test:sparta@cluster0.2rz7w.mongodb.net/Cluster0?retryWrites=true&w=majority',
                     tlsCAFile=certifi.where())
db = client.ASMR_Study

app = Flask(__name__)

SECRET_KEY = 'SPARTA'


@app.route('/')
def intro():
    return render_template('intro.html')


@app.route('/login')
def login():
    msg = request.args.get("msg")
    return render_template('login.html', msg=msg)


@app.route('/main')
def home():
    token_receive = request.cookies.get('mytoken')
    try:
        # DB에서 저장된 asmrs 리스트를 가져다가 뽑아옴
        asmr_list = list(db.asmrs.find({}))

        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.user.find_one({"username": payload["id"]})
        users_star = user_info['star']

        star_arr = []

        for x in users_star:
            temp = list(db.asmrs.find({"id": x}))
            star_arr.append(temp)


        eqStar = []
        for x in users_star:
            for y in asmr_list:
                if x==y:
                    eqStar.append(x)

        # Jinja2 방식으로 SSR(Server side rendering)를 사용해 main.html 페이지를 렌더링
        # 렌더링 시 asmrs라는 이름으로 가져온 asmr_list 데이터를 보내줌
        return render_template('main.html', user_info=user_info, asmrs=asmr_list, lists=star_arr, username=payload["id"], users_star=users_star)


    except jwt.ExpiredSignatureError:
        return redirect(url_for("login", msg="로그인 시간이 만료되었습니다."))
    except jwt.exceptions.DecodeError:
        return redirect(url_for("login", msg="로그인 정보가 존재하지 않습니다."))


#즐찾삭제
@app.route('/deleteStar', methods=['PUT'])
def deleteStar():
    id = request.form['id']
    username = request.form['username']

    db.user.update_one({'username': username}, {'$pull': {'star': id}})

    return jsonify({'id': id , 'username':username})

#즐찾추가
@app.route('/addStar', methods=['PUT'])
def addStar():
    id = request.form['id']
    username = request.form['username']

    db.user.update_one({'username':username},{'$push':{'star':{'$each':[id],'$position':0}}})

    return jsonify({'id': id , 'username':username})


@app.route('/sign_in', methods=['POST'])
def sign_in():
    # 로그인
    username_receive = request.form['username_give']
    password_receive = request.form['password_give']

    pw_hash = hashlib.sha256(password_receive.encode('utf-8')).hexdigest()
    result = db.user.find_one({'username': username_receive, 'password': pw_hash})

    if result is not None:
        payload = {
            'id': username_receive,
            'exp': datetime.utcnow() + timedelta(seconds=60 * 60 * 24)  # 로그인 24시간 유지
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')

        return jsonify({'result': 'success', 'token': token})
    # 찾지 못하면
    else:
        return jsonify({'result': 'fail', 'msg': '아이디/비밀번호가 일치하지 않습니다.'})


@app.route('/sign_up/save', methods=['POST'])
def sign_up():
    username_receive = request.form['username_give']
    password_receive = request.form['password_give']
    password_hash = hashlib.sha256(password_receive.encode('utf-8')).hexdigest()
    doc = {
        "username": username_receive,
        "password": password_hash,
        "star":[]
    }
    db.user.insert_one(doc)
    return jsonify({'result': 'success'})


@app.route('/sign_up/check_dup', methods=['POST'])
def check_dup():
    username_receive = request.form['username_give']
    exists = bool(db.user.find_one({"username": username_receive}))
    return jsonify({'result': 'success', 'exists': exists})


@app.route("/search", methods=["GET"])
def search():

    word_receive = request.args['word']

    # db에서 특정 문자 포함($regex), 옵션(대소문자 상관없이)을 줘서 가져옴
    find_list = list(db.asmrs.find({'title': {'$regex':word_receive,'$options':'i'}}))

    return render_template('search.html', find_asmr=find_list)

@app.route('/saveAsmr', methods=['POST'])
def saveAsmr():
    print('save')
    title_receive = request.form['title_give']
    link_receive = request.form['link_give']
    img_receive = request.form['img_give']

    doc = {
        'title': title_receive,
        'link': link_receive,
        'img': img_receive
    }
    db.asmrs.insert_one(doc)
    print('저장 완료')

    return jsonify({'result': 'success', 'msg': '저장 완료'})


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
    # DB에서 저장된 asmrs 리스트를 가져다가 뽑아옴
    asmr_list = list(db.asmrs.find({}))
    for asmr in asmr_list:
        link = asmr['link']
        viewers = '';
        # requests를 쓰기 위한 header 정보
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.86 Safari/537.36'}

        # 대상 Asmr에 link에 맞춰 페이지 데이터를 가져옴
        data = requests.get(link, headers=headers)

        # requests가 정상인 경우
        if data.ok:
            #현재 영상이 Live 영상인지 확인
            if (data.text.find('"isLiveContent":true') != -1):
                # 가져온 페이지 데이터를 text 형태로 변환해 videoViewCountRenderer란 단어를 검색한 뒤 그 위치 반환
                startIndex = data.text.find('videoViewCountRenderer')

                # 만약 검색된 단어위치가 존재한다면 실행
                if (startIndex != -1):
                    # videoViewCountRenderer 검색된 위치부터 isLive란 단어를 검색해 그 위치를 찾음
                    endIndex = data.text.find('isLive', startIndex)
                    # 검색된 단어들의 위치를 기반으로 텍스트를 잘라냄
                    targetText = data.text[startIndex:endIndex]
                    # 잘라낸 텍스트에서 문자를 제거하고 숫자(시청자 수)를 추출함
                    viewers = re.sub(r'[^0-9]', '', targetText)
                db.asmrs.update_one({'_id': asmr['_id']}, {"$set": {"viewers": viewers}})
            else:
                db.asmrs.update_one({'_id': asmr['_id']}, {"$set": {"viewers": ''}})


# 스케쥴러를 이용해 1 시간마다 크롤링
scheduler = BackgroundScheduler()
scheduler.add_job(func=getViewers, trigger="interval", seconds=6000)
scheduler.start()

# 디버그 모드에선 플라스크는 앱을 두번 로드함
# 두번 로드시 스케쥴러도 두번 실행되기 때문에 use_reloader를 이용해 비활성화
if __name__ == '__main__':
    app.run('0.0.0.0', port=5000, debug=True, use_reloader=False)
