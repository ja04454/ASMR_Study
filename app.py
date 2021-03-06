import time

from flask import Flask, render_template, redirect, url_for, jsonify, request
from pymongo import MongoClient
import requests
import certifi
import re
import jwt
import hashlib
from bson.objectid import ObjectId

from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

client = MongoClient('mongodb+srv://test:sparta@cluster0.p0pyn.mongodb.net/Cluster0?retryWrites=true&w=majority')
db = client.ASMR_Study

app = Flask(__name__)

SECRET_KEY = 'SPARTA'


# jwt id 가져오기 모듈화
def GetJwtId():
    # token_check()
    # mytoken이라는 이름으로 저장된 사용자의 쿠키 정보를 가져옴
    token_receive = request.cookies.get('mytoken')
    # jwt 해독 기능을 이용해 가져온 토큰 정보를 암호키와 함께 HS256 방식으로 해석해 저장함
    payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
    # 해독 된 사용자 정보에서 id 정보를 꺼내 DB에서 유저 정보 검색 실행
    user_info = db.user.find_one({"username": payload["id"]})
    # 유저의 아이디를 반환함
    return user_info['username']


@app.route('/')
def intro():
    # jinja2 방식으로 intro.html 페이지를 서버에서 렌더링 한 뒤 사용자에게 제공
    return render_template('intro.html')


@app.route('/login')
def login():
    # 클라이언트에서 전송된 MultiDict 데이터에서 "msg"키를 가진 데이터의 값을 가져옴
    msg = request.args.get("msg")
    # 렌더링 시 변수를 페이지에서 사용하기 위해 msg 데이터를 담아줌
    return render_template('login.html', msg=msg)


@app.route('/main')
def home():
    token_receive = request.cookies.get('mytoken')
    try:
        # DB에서 저장된 asmrs 리스트를 가져다가 뽑아옴
        asmr_list = list(db.asmrs.find({}))

        for asmr in asmr_list:
            asmr['link'] = asmr['link'].replace("watch?v=","embed/")
            print(asmr['link'])

        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.user.find_one({"username": payload["id"]})
        users_star = user_info['star']

        # 유저의 즐겨찾기에 있는 즐겨찾기들의 상세 정보를 불러온다.
        star_arr = []
        for x in users_star:
            temp = list(db.asmrs.find({"_id": ObjectId(x)}))
            star_arr.append(temp)

        # Jinja2 방식으로 SSR(Server side rendering)를 사용해 main.html 페이지를 렌더링
        # 렌더링 시 asmrs라는 이름으로 가져온 asmr_list 데이터를 보내줌
        return render_template('main.html', user_info=user_info, asmrs=asmr_list, lists=star_arr, users_star=users_star)

    # 유저 아이디가 없다면
    except jwt.ExpiredSignatureError:
        return redirect(url_for("login", msg="로그인 시간이 만료되었습니다."))
    except jwt.exceptions.DecodeError:
        return redirect(url_for("login", msg="로그인 정보가 존재하지 않습니다."))


# 즐찾삭제
@app.route('/deleteStar', methods=['PUT'])
def deleteStar():
    id = request.form['id']
    username = GetJwtId()

    db.user.update_one({'username': username}, {'$pull': {'star': id}})

    return jsonify({'id': id, 'username': username})


# 즐찾추가
@app.route('/addStar', methods=['PUT'])
def addStar():
    id = request.form['id']
    username = GetJwtId()

    db.user.update_one({'username': username}, {'$push': {'star': {'$each': [id], '$position': 0}}})

    return jsonify({'id': id, 'username': username})


@app.route('/sign_in', methods=['POST'])
def sign_in():
    # 로그인
    username_receive = request.form['username_give']
    password_receive = request.form['password_give']

    # 입력받은 pw 암호화
    pw_hash = hashlib.sha256(password_receive.encode('utf-8')).hexdigest()
    # id, 암호화된 pw로 해당 유저 찾음
    result = db.user.find_one({'username': username_receive, 'password': pw_hash})

    # 유저가 있으면
    if result is not None:
        # 로그인 한 사람의 id와 로그인이 언제까지 유효한지 정보
        payload = {
            'id': username_receive,
            'exp': datetime.utcnow() + timedelta(seconds=60 * 60 * 24)  # 로그인 24시간 유지
        }
        # SECRET_KEY로 암호화
        token = jwt.encode(payload, SECRET_KEY, algorithm='HS256').decode('utf-8')

        # 토큰을 준다
        return jsonify({'result': 'success', 'token': token})
    # 찾지 못하면
    else:
        return jsonify({'result': 'fail', 'msg': '아이디/비밀번호가 일치하지 않습니다.'})


@app.route('/sign_up/save', methods=['POST'])
def sign_up():
    # 회원가입
    username_receive = request.form['username_give']
    password_receive = request.form['password_give']
    password_hash = hashlib.sha256(password_receive.encode('utf-8')).hexdigest()

    doc = {
        "username": username_receive,   # 아이디
        "password": password_hash,      # 비밀번호
        "star": []                      # 즐겨찾기
    }
    db.user.insert_one(doc)
    return jsonify({'result': 'success'})


@app.route('/sign_up/check_dup', methods=['POST'])
def check_dup():
    # ID 중복 확인
    username_receive = request.form['username_give']
    # id가 하나라도 존재한다면 true
    exists = bool(db.user.find_one({"username": username_receive}))
    return jsonify({'result': 'success', 'exists': exists})

# 검색
@app.route("/search", methods=["GET"])
def search():
    word_receive = request.args['word']

    # db에서 'title'에 검색할 단어가 포함되어 있는 도큐먼트 조회
    # 조건 - 특정 문자 포함($regex), 대소문자 상관없이($option:i)
    find_list = list(db.asmrs.find({'title': {'$regex': word_receive, '$options': 'i'}}))

    # 검색어가 포함된 데이터를 search.html로 전달
    return render_template('search.html', find_asmr=find_list)


# asmr 데이터 저장
@app.route('/saveAsmr', methods=['POST'])
def saveAsmr():
    title_receive = request.form['title_give']
    link_receive = request.form['link_give']
    img_receive = request.form['img_give']

    # db에서 asmr콜렉션에 데이터 저장
    doc = {
        'title': title_receive,
        'link': link_receive,
        'img': img_receive
    }
    db.asmrs.insert_one(doc)

    # 저장 후 저장완료 메세지 전달
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
            # 현재 영상이 Live 영상인지 확인
            if (data.text.find('"isLiveContent":true') != -1):
                if (data.text.find('"isLiveNow":true') != -1):
                    # 가져온 페이지 데이터를 text 형태로 변환해 videoViewCountRenderer란 단어를 검색한 뒤 그 위치 반환
                    startIndex = data.text.find('videoViewCountRenderer')

                    # 만약 검색된 단어위치가 존재한다면 실행
                    if (startIndex != -1):
                        # videoViewCountRenderer 검색된 위치부터 isLive란 단어를 검색해 그 위치를 찾음
                        endIndex = data.text.find('"isLive":true', startIndex)
                        # 검색된 단어들의 위치를 기반으로 텍스트를 잘라냄
                        targetText = data.text[startIndex:endIndex]
                        # 잘라낸 텍스트에서 문자를 제거하고 숫자(시청자 수)를 추출함
                        viewers = re.sub(r'[^0-9]', '', targetText)
                    db.asmrs.update_one({'_id': asmr['_id']}, {"$set": {"viewers": viewers}})
                else:
                    db.asmrs.update_one({'_id': asmr['_id']}, {"$set": {"viewers": 'Not Live'}})
            else:
                db.asmrs.update_one({'_id': asmr['_id']}, {"$set": {"viewers": 'Not Streaming'}})


scheduler = BackgroundScheduler(timezone='Asia/Seoul')
# 스케쥴러를 이용해 1 시간마다 크롤링(getViewers 함수를 호출)
scheduler.add_job(func=getViewers, trigger="interval", seconds=3600)
scheduler.start()

# 디버그 모드에선 플라스크는 앱을 두번 로드함
# 두번 로드시 스케쥴러도 두번 실행되기 때문에 use_reloader를 이용해 비활성화
if __name__ == '__main__':
    app.run('0.0.0.0', port=5000, debug=True, use_reloader=False)
