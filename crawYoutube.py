import json

import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
import certifi



client = MongoClient('mongodb+srv://test:sparta@cluster0.2rz7w.mongodb.net/Cluster0?retryWrites=true&w=majority',tlsCAFile=certifi.where())

db = client.ASMR_Study

#requests를 쓰기 위한 header 정보
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.86 Safari/537.36'}

#검색 할 텍스트
keyword = 'asmr study'
#대상 Asmr에 link에 맞춰 페이지 데이터를 가져옴
data = requests.get( 'https://www.youtube.com/results?search_query='+keyword, headers=headers)
#requests가 정상인 경우
if data.ok:
    #유튜브 데이터를 분석해 영상 데이터의 배열 시작점 index를 가져옴
    startIndex = data.text.find('{"itemSectionRenderer":')
    #유튜브 데이터를 분석해 영상 데이터의 배열 종료 index를 가져옴
    endIndex = data.text.find(',{"continuationItemRenderer')
    #분석한 index 정보를 기반으로 영상 data가 보관된 데이터를 가져와 json으로 가공
    targetJson = json.loads(data.text[startIndex:endIndex])

    #기존 DB 데이터를 삭제 후 진행
    db.asmrs.delete_many({})

    #json 구조에서 contents에 포함된 요소들을 val에 담아서 가져온 영상 정보 수 만큼 반복함
    for idx, val in enumerate(targetJson['itemSectionRenderer']['contents']):
        #일부 contents 내용이 videoRenderer이 아닌 다른 경우가 있어 제외시킴
        if 'videoRenderer' in val:
            img = val['videoRenderer']['thumbnail']['thumbnails'][0]['url']
            title = val['videoRenderer']['title']['runs'][0]['text']
            link = "https://www.youtube.com" + val['videoRenderer']['navigationEndpoint']['commandMetadata']['webCommandMetadata']['url']
            #DB 저장을 위해 사전 구조를 만듬
            doc = {
                'id':idx,
                'title': title,
                'img': img,
                'link': link,
                'viewers': ''
            }
            #만들어진 데이터를 DB에 저장
            db.asmrs.insert_one(doc)
    '''
    soup = BeautifulSoup(data.text, 'html.parser')
    asmrs = soup.select('#contents > ytd-video-renderer')
    count = 0
    for asmr in asmrs:
        title.append(idx.text)
        url.append(idx.get('href'))
        doc = {
            'title': title,
            'image': src,
            'link': href_tag,
            'viewers': star
    
        }

    db.movie.insert_one(doc)
    '''
