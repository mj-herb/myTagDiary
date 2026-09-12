from fastapi import Body, FastAPI, Request, Form, HTTPException, Depends, Query, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.encoders import jsonable_encoder
from sqlmodel import Session, select
from passlib.context import CryptContext
from .models import Dot, DotTagLink, User, Diary, Weather, DiaryEntry, DiaryEntryTagLink, Tag, ReplyToDot
from .database import engine, get_session, create_db_and_tables 
from .auth import create_access_token, get_current_user, get_password_hash, verify_password, ACCESS_TOKEN_EXPIRE_MINUTES, SECRET_KEY, ALGORITHM, pwd_context, oauth2_scheme
from app.routers import auth_router, user_router
from .redis_client import redis_client, MAX_ATTEMPTS, LOCKOUT_TIME, get_redis_key
from datetime import datetime, date, time, timedelta
from collections import defaultdict
import requests
from pydantic import BaseModel, Field
from typing import List, Optional
from urllib.parse import urlencode
from time import strptime
import json
import pandas as pd
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
import logging
import calendar
from collections import defaultdict
import holidays
from sqlalchemy import and_, delete, text
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import selectinload


app = FastAPI()
app.include_router(auth_router.router)
app.include_router(user_router.router)

templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session)
):
    redis_key = get_redis_key(username)
    print(f'redis_key : {redis_key}')
    attempts = redis_client.get(redis_key)
    print(f'attempts : {attempts}')
    # print(f'int attempts : {int(attempts)} ')
    attempts_left = MAX_ATTEMPTS - int(attempts) if attempts else MAX_ATTEMPTS

    if attempts_left <= 0:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": f"계정이 잠겼습니다. {LOCKOUT_TIME//60}분 후에 다시 시도해주세요."
        })

    statement = select(User).where(User.username == username)
    user = session.exec(statement).first()

    if not user or not verify_password(password, user.hashed_password):
        redis_client.incr(redis_key)
        redis_client.expire(redis_key, LOCKOUT_TIME)
        attempts_left -= 1
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": f"로그인 실패. {attempts_left}회 남았습니다."
        })

    redis_client.delete(redis_key)

    access_token = create_access_token(data={"sub": user.username})
    print(f'access_token: {access_token}------------------------')

    response = RedirectResponse(url="/user/profile", status_code=303)
    response.set_cookie(
    key="access_token",
    value=access_token,
    httponly=True,
    max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    path="/",
    secure=True,  # 프로덕션 환경에서 True 권장
    samesite="lax"
)

    return response


@app.get("/register")
async def register_get(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register")
async def register_post(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
):
    with Session(engine) as session:
        statement = select(User).where((User.email == email) | (User.username == username))
        existing_user = session.exec(statement).first()
        if existing_user:
            return templates.TemplateResponse(
                "register.html",
                {"request": request, "error": "Username or email already exists."}
            )
        hashed_password = get_password_hash(password)
        user = User(username=username, email=email, hashed_password=hashed_password)
        session.add(user)
        session.commit()
        return RedirectResponse(url="/login", status_code=303)
    
# date, datetime type serializable 못하기 때문에     
# exist_dates_json = json.dumps(exist_dates, default=json_serial) 
# javascript에 넘겨주기 전에 string 으로 변환해준다. 
def json_serial(obj):
    if isinstance(obj, (date,datetime)):
        return obj.isoformat()
    raise TypeError(f"Type {obj.__class__.__name__} not serializeable")

# 달력창 접속
# 여기서 내가 만든 dot 에 관한 모든 data select 해서 넘겨줘야함 !!!!
@app.get("/user/profile")
async def user_profile(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    year: int = None
):
    today = date.today()
    year = today.year
    month = today.month
    now = datetime.now()
    exist_dates = []
    cal = calendar.Calendar(firstweekday=6)
    month_dates = cal.monthdatescalendar(year, month) # 주 단위 리스트로 반환
    statement = select(Diary).where(Diary.user_id == current_user.id)
    results = session.exec(statement)
    diary_dates = {diary.diary_date for diary in results}
    for week in month_dates:
        for day in week:
            if day in diary_dates:
                exist_dates.append(day)
    exist_dates_json = json.dumps(exist_dates, default=json_serial)

    
    
    def dot_data():
        # 나의 모든 dot_tag_link들
        dotTagLinks = session.exec(select(DotTagLink).where(DotTagLink.user_id == current_user.id)).all()
        print(f'findMyDot :: {dotTagLinks}')
        # 하나의 링크에서 하나의 dot 찾기
        i = 1
        
        for dotTagLink in dotTagLinks:
            print(f'-----------------------{i}번째 dot')
            print(f'-dotTagLink :: {dotTagLink}')
            dot = session.exec(select(Dot).where(dotTagLink.dot_id == Dot.id)).one()
            print(f'-dot :: {dot}')
            print(f'-dot.name :: {dot.name}')
            print(f'-dot.descrbe :: {dot.describe}')
            print(f'-tags:: {dot.tags}')

            for tag in dot.tags:
                print(f'-tag.nameList :: {tag.name}')
            
            # 각 tag에 해당하는 diaryEntry를 찾는다.(시간순)
            for tag in dot.tags:
                print(f'--tag.name start')
                print(f'-tag.name :: {tag.name}')
                print(f'-tag.id :: {tag.id}')
                # 각 tag에 해당하는 diaryEntry들 출력
                diaryEntryTagLinks = session.exec(select(DiaryEntryTagLink).where(DiaryEntryTagLink.user_id == current_user.id, DiaryEntryTagLink.tag_id == tag.id)).all()
                print(f'-diaryEntryTagLinks : {diaryEntryTagLinks}')
                for diaryEntryTagLink in diaryEntryTagLinks:
                    diaryEntry = session.exec(select(DiaryEntry).where(diaryEntryTagLink.diary_entry_id == DiaryEntry.id)).all()
                    print(f'-diaryEntry :: {diaryEntry}')
                    # print(f'-time_recorded :: {diaryEntry}')
                    
            i = i + 1   
    print('what is going on..........')
    join_link_table = session.exec(
    select(DotTagLink, DiaryEntryTagLink)
    .join(
        DiaryEntryTagLink,
        and_(
            DotTagLink.tag_id == DiaryEntryTagLink.tag_id,
            DotTagLink.user_id == DiaryEntryTagLink.user_id
        )
    )
    .where(DotTagLink.user_id == current_user.id)).all()
    
    # DotTagLink.dot_id 와 DiaryEntryTagLink.diary_entry_id 이 두개의 항목이 중복되는 행은 제거
    seen = set()
    unique_rows = [] # join_link_table에서 key = (dot_tag.dot_id, diary_tag.diary_entry_id) -> 이 key값을 빼준것

    for dot_tag, diary_tag in join_link_table:
        key = (dot_tag.dot_id, diary_tag.diary_entry_id)  # 중복 기준 키
        if key not in seen:
            unique_rows.append((dot_tag, diary_tag))
            seen.add(key)
            
    print(f'unique_rows :: {unique_rows}')  

    # unique rows가 비어있을때 화면에 null이라고 뜬다.   
    if  not unique_rows:
        return templates.TemplateResponse("user_calender.html", {
                "request": request,
                "today": today,
                "year" : year,
                "month": month,
                "now": now,
                "month_dates": month_dates,
                "exist_dates": exist_dates_json,
                # "dot_data_list": encoded_dot_data_list,
            }) 
    else:
        unique_dot_list = set()
        for dot_tag, diary_tag in join_link_table:
            key = (dot_tag.dot_id)
            if key not in unique_dot_list:
                unique_dot_list.add(key)
        print(f'unique_dot_list :: {unique_dot_list}')

        n = 1
        dot_data_list = []

# 내가 작성한 dot data 출력
        for unique_dot in unique_dot_list:
            print(f'-----------{n}번째 dot 시작')
            n += 1
            print(f'unique_dot :: {unique_dot}') # dot.id
            # dot = session.exec(select(Dot).where(Dot.id == unique_dot)).one_or_none()
            dot = session.exec(select(Dot).where(Dot.id == unique_dot)).one_or_none()
            print(f'dot : {dot}')
            
            # dot 이 하나도 없을떼 
            if dot is None:
                return templates.TemplateResponse("user_calender.html", {
                "request": request,
                "today": today,
                "year" : year,
                "month": month,
                "now": now,
                "month_dates": month_dates,
                "exist_dates": exist_dates_json,
                # "dot_data_list": encoded_dot_data_list,
            }) 

            # dot 이 존재할때 
            else:
                dot_name = dot.name
                dot_desc = dot.describe
                dot_id = dot.id #MyDotDiv의 고유 id로 부여하여 지우기 용이하게 만듦
                tags = dot.tags
                tag_list = [] # dot 당 tag리스트 구성 
                for tag in tags:
                    tag_name = tag.name
                    tag_list.append(tag_name)
                diary_entries = []
                print(f'-------------------unique_rows: {unique_rows}')
                for unique_row in unique_rows:
                    print(f'unique_row[0] : {unique_row[0]}') #tag_id=4 user_id=1 dot_id=8
                    print(f'unique_row[1] : {unique_row[1]}') #diary_entry_id=4 tag_id=5 user_id=1
                    if unique_row[0].dot_id == unique_dot:
                        print(f'unique_row[1].diary_entry_id : {unique_row[1].diary_entry_id}')
                        print('일치한다...')
                        diary_entry = session.exec(select(DiaryEntry).where(DiaryEntry.id == unique_row[1].diary_entry_id)).one()
                        diary = session.exec(select(Diary).where(Diary.id == diary_entry.diary_id)).one()
                        diary_date = diary.diary_date
                        diary_entry_with_date = {
                            **diary_entry.model_dump(),
                            "diary_date": diary_date                    
                        }
                        diary_entries.append(diary_entry_with_date)

                        # replies를 받아올때 계층 처리 해서 받아오기
                        # replies = session.exec(select(ReplyToDot).where(ReplyToDot.dot_id == dot_id)).all()                        
                replyList = recursive_query(session= session, dot_id = dot_id)
                
                # 여기서 부터 하나의 dot에 대한 data를 다 넣기....
                dot_data_list.append({
                "dotName": dot_name,
                "dotDescription": dot_desc,
                "dotId" : dot_id,
                "tags": tag_list,
                "diary_entries": diary_entries,
                # "replyData" : oneDotReplyList,
                "replyData" : replyList,
            })

        dot_data_list = dot_data_list or []
        encoded_dot_data_list = jsonable_encoder(dot_data_list)
        print(f'--------------------------dot_data_list : {encoded_dot_data_list}')
        print(len(encoded_dot_data_list))
        return templates.TemplateResponse("user_calender.html", {
            "request": request,
            "today": today,
            "year" : year,
            "month": month,
            "now": now,
            "month_dates": month_dates,
            "exist_dates": exist_dates_json,
            "dot_data_list": encoded_dot_data_list,
        })

@app.get("/popup.html", response_class=HTMLResponse)
async def popup(request: Request):
    return templates.TemplateResponse("popup.html", {"request": request})

class TagItem(BaseModel):
    tag_id: str

class CreateDotRequest(BaseModel):
    name: str
    describe: str
    tags: List[TagItem]

# dot검색
@app.get("/api/searchDot/{inputValue}")
def search_dot(inputValue: str,
               session: Session = Depends(get_session),):
    inputValue = inputValue
    # 여기서 받은 input을 tag, dot db에서 검색해야한다.  
    # session 시작.
    # Dot 에는 relationship에 tags가 있긴 하지만 join을 안하고 그냥 Dot에서 검색을 하면 안나온다.
    query = (
        select(Dot)
        .join(DotTagLink)
        .join(Tag)
        .where(
            (Dot.name.like(f"%{inputValue}%")) |
            (Tag.name.like(f"%{inputValue}%"))
        )
        .options(joinedload(Dot.tags))
    )
    
    queryResult = session.exec(query) #중복된 결과를 출력할 가능성이 많다.
    uniqueDotResults = queryResult.unique().all();
    print(f"-------------uniqueDotResults: :{uniqueDotResults}" )
    #print(f"-------------------------uniqueQueryResult : {uniqueQueryResults}")

    # 이제부터 한개의 dot씩 돌린다..  그리고 tag 검색하고 tag.id 를 entry와 일치하는 걸 찾고 diary도 찾음
    dotList = []
    for dot in uniqueDotResults:
        print(f'-------dot: {dot}')
        tagList = []
        tagEntriesList = []
        for tag in dot.tags:
            print(f'--------tag : {tag}')
            tagList.append(tag)
            # print(f'--------tag.entries : {tag.entries}')
            for entry in tag.entries:
                print(f'----------entry : {entry}')
                diaryDate = entry.diary.diary_date
                entryInfo = {
                             "diaryEntry" : entry,
                             "diaryDate" : diaryDate,
                             }
                tagEntriesList.append(entryInfo);
        uniqueEntriesDict = {}
        for entryInfo in tagEntriesList:
            entryId = entryInfo["diaryEntry"].id
            if entryId not in uniqueEntriesDict:
                uniqueEntriesDict[entryId] = entryInfo        

        oneDotReplyList = recursive_query(session= session, dot_id=dot.id)
       
        uniqueEntriesList = list(uniqueEntriesDict.values())
        DotInfo = {
            "dotName" : dot.name,
            "dotDesc" : dot.describe,
            "dotId" : dot.id,
            "tags" : tagList,
            "diaryEntries" : uniqueEntriesList,
            "replyData" : oneDotReplyList,
        }
        dotList.append(DotInfo)

    print(f'-------------------dotList: {dotList}')
    # javascript에 데이터 넘어감
    return {"dotInfoList" : dotList}


# dot 만들기
@app.post("/api/createDot")
def create_new_dot(
    createDotRequest: CreateDotRequest = Body(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    print(f'createDotRequest: {CreateDotRequest}')
    createDotRequest = createDotRequest
    
    dot_orm = Dot(
        name=createDotRequest.name,
        describe=createDotRequest.describe,
        # tags=tag_objs
    )
    session.add(dot_orm)
    session.flush()

# 받아온 tag를 db에 검색후 link에 추가
    for tag_item in createDotRequest.tags:
        # tag_item.tag_id는 createDotRequest 넘어올때 
        # tags: addTagList, [{tag_id: 'tag1'}, {tag_id: 'tag2'}, ...] 이렇게 옴
        tag = session.exec(select(Tag).where(Tag.name == tag_item.tag_id, Tag.user_id == current_user.id)).first()
        print(f'tag: {tag}')
        if tag:
            dot_tag_link = DotTagLink(
                dot_id=dot_orm.id,
                tag_id=tag.id,
                user_id=current_user.id
            )
            session.add(dot_tag_link)

    session.commit()

    return {"message":"session complete","data": "createDotRequest"}


def recursive_query(session, dot_id):
        oneDotReplyList = []

        query = text("""
            WITH RECURSIVE reply_tree AS (
                SELECT dot_id AS dotId, parent_reply_id AS parentReplyId, reply,
                    id AS replyId, (SELECT username FROM "user" WHERE "user".id = r.user_id) AS userName,
                    1 AS level, ARRAY[id] AS path
                FROM replytodot r
                WHERE parent_reply_id IS NULL AND dot_id = :dot_id

                UNION ALL

                SELECT r.dot_id, r.parent_reply_id, r.reply, r.id,
                    (SELECT username FROM "user" WHERE "user".id = r.user_id),
                    rt.level + 1, rt.path || r.id
                FROM replytodot r
                INNER JOIN reply_tree rt ON r.parent_reply_id = rt.replyId
                WHERE r.dot_id = :dot_id
            )
            SELECT * FROM reply_tree
            ORDER BY path;
        """)
        result = session.execute(query, {'dot_id' : dot_id})
        reply_tree_list = result.mappings().all()
        print(f'----------------reply_tree_list : {reply_tree_list}');
        
        for oneReply in reply_tree_list:
            replyData = {
                "dotId" : oneReply.dotid,
                "reply" : oneReply.reply,
                "userName" : oneReply.username,
                "replyId" : oneReply.replyid,
                "parentReplyId" : oneReply.parentreplyid,
                "level" : oneReply.level,
            }
            oneDotReplyList.append(replyData)

        replyList = jsonable_encoder(oneDotReplyList)
        return replyList

class CreateDotReplyRequest(BaseModel):
    reply: str
    dotId: int
    # parentReplyId : int | None
# dot 에 reply 저장
@app.post("/api/createDotReply")
def create_dot_reply(createDotReplyRequest: CreateDotReplyRequest = Body(...),
                    current_user: User = Depends(get_current_user),
                    session: Session = Depends(get_session),):
    # data 받아서 다시 넘겨줌
    reply_data = createDotReplyRequest
    dot_id = reply_data.dotId
    reply = reply_data.reply
    user_id = current_user.id
    findUser = session.exec(select(User).where(user_id == User.id)).one()
    # username은 리플을 단 유저를 가리킴
    userName = findUser.username
    # parentReplyId = reply_data.parentReplyId

    new_reply = ReplyToDot(reply=reply, dot_id=dot_id, user_id=user_id)
    session.add(new_reply)
    session.flush()
    new_reply_id = new_reply.id
    session.commit()

    replyList = recursive_query(session= session, dot_id=dot_id)
    return replyList


class CreateReplyToReplyRequest(BaseModel):
    reply: str
    dotId: int
    parentReplyId: int | None
@app.post("/api/createReplyToReply")
def create_reply_to_reply(CreateReplyToReplyRequest: CreateReplyToReplyRequest = Body(...),
                    current_user: User = Depends(get_current_user),
                    session: Session = Depends(get_session),):
    reply_data = CreateReplyToReplyRequest
    dot_id = reply_data.dotId
    reply = reply_data.reply
    user_id = current_user.id
    findUser = session.exec(select(User).where(user_id == User.id)).one()
    userName = findUser.username
    parentReplyId = reply_data.parentReplyId

    new_reply = ReplyToDot(reply=reply, dot_id=dot_id, user_id=user_id, parent_reply_id=parentReplyId)
    session.add(new_reply)
    session.flush()
    new_reply_id = new_reply.id
    session.commit()

    replyList = recursive_query(session= session)
    return replyList
    
    
@app.get("/api/removeDot/{dotId}")
def remove_one_dot(dotId: str, session: Session = Depends(get_session)):
    # Dot 삭제
    removeThisDot = session.get(Dot, dotId)
    if removeThisDot:
        session.delete(removeThisDot)
        session.commit()
    # DotTagLink 삭제
    session.exec(delete(DotTagLink).where(DotTagLink.dot_id == dotId))
    session.commit()
    return {"result": "ok"}


# 달력 옆 화살표 누르면 한 달이 더해지거나 빼진다.
@app.get("/user/profile/{year}/{month}")
async def new_calendar(
    request: Request,
    # data: CalendarRequest,
    year: int = None,
    month: int = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if month == 13:
        year += 1
        month = 1
    elif month == 0:
        year -= 1
        month = 12
    else:
        year = year
        month = month
    now = datetime.now()
    exist_dates = []
    # kr_holidays = holidays.KR(years=2025)
    # print(f'kr_holidays : {kr_holidays}')
    
    cal = calendar.Calendar(firstweekday=6)
    month_dates = cal.monthdatescalendar(year, month) # 주 단위 리스트로 반환
    print(f'---------------------month_dates: {month_dates}')

    
    statement = select(Diary).where(Diary.user_id == current_user.id)
    results = session.exec(statement)
    diary_dates = {diary.diary_date for diary in results}
    print(f'diary_dates : {diary_dates}')
    for week in month_dates:
        for day in week:
            if day in diary_dates:
                exist_dates.append(day)
    print(f'exist_day: {exist_dates}')   
    exist_dates_json = json.dumps(exist_dates, default=json_serial)


    return templates.TemplateResponse("user_calender.html", {
        "request": request,
        "year" : year,
        "month": month,
        "now": now,
        "month_dates": month_dates,
        "exist_dates": exist_dates_json,
    })


@app.get("/api/selectTag")
def get_weather_history(current_user: User = Depends(get_current_user),
                        session: Session = Depends(get_session)):
    statement = select(Tag).where(Tag.user_id == current_user.id)
    tags = session.exec(statement).all() 
    return {"tags": tags}
    
    
def get_user_region():
    # response = requests.get("https://api.ip.pe.kr/")
    response = requests.get("http://ip-api.com/json/?fields=61439").json()
    ip = response["query"]
    country = response["countryCode"]
    city = response["city"]
    user_region = {
        "country" : country,
        "city" : city
    }
    return user_region

weather_api_key = "fd15a8298b5104a2d4f8b7c1c8006fd2"
visualcrossing_api_key = "9KXGGHB7UFLYUXZCCWWFSCHDV" #historical api

def get_user_city_weather(city, api_key):
    url = f'https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}'
    response = requests.get(url=url)
    return response.json()

# calender에서 옴 @app.get(/usr/profile)
@app.get("/user/page/{date}", response_class=HTMLResponse)
def read_user_data(
    date: str,
):
    # print(f'GET /user/profile called with user_id={user_id}, date={date}')
    print(f'-------------------ip검색 api가 늦어지고 있는걸까...?')
    user_region = get_user_region()
    user_country = user_region["country"]
    user_city = user_region["city"]
    print(f'-------------------user_city : {user_city}')
    date = date
    print(f'-------------------date : {date}')
    redirect_url = f"/user/diary?date={date}&country={user_country}&city={user_city}"
    print(f"Redirecting to: {redirect_url}")
    return RedirectResponse(url=redirect_url)


with open('city.list.json', 'r', encoding='utf-8') as f:
    city_list = json.load(f)

countrycode_csv = pd.read_csv("countrycode.csv")


@app.get("/user/diary")
def diary_form(
    request: Request,
    date: date,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    countries = countrycode_csv[["Country Name", "ISO2"]].drop_duplicates()
    countries = countries.to_dict(orient="records")

    statement = (
        select(Diary)
        .where(Diary.user_id == current_user.id)
        .where(Diary.diary_date == date)
        .options(
            selectinload(Diary.entries).selectinload(DiaryEntry.tags)
        )
    )
    diary = session.exec(statement).first()

    if diary:
        diary_entries = diary.entries
        diaryEntries = []
        for entry in diary.entries:
            entryData = {
                "id": entry.id,
                "memo": entry.memo,
                "time": entry.time_recorded.strftime("%H:%M"),
                "tagList": [tag.name for tag in entry.tags],
            }

            diaryEntries.append(entryData)

        diaryData = {
            "diaryDate": diary.diary_date.isoformat(),
            "country_name": diary.country_name,
            "city": diary.city,
            "diaryEntries": jsonable_encoder(diaryEntries),
            "diaryWeather": jsonable_encoder(diary.weather),
            "country_iso2": diary.country_iso2,
        }

        return templates.TemplateResponse("user_diary.html", {
            "request": request,
            "date": date,
            "countries": countries,
            "diary_json": diaryData,
        })

    return templates.TemplateResponse("user_diary.html", {
        "request": request,
        "date": date,
        "countries": countries,
    })



@app.get("/api/cities")
def get_cities_by_country(country_iso2: str):
    filtered_cities = [
        city for city in city_list
        if city['country'].upper() == country_iso2.upper()
    ]
    print(f'filtered city : {filtered_cities}')
    city_names = sorted({city['name'] for city in filtered_cities})
    return city_names


@app.get("/weather/history")
def get_weather_history(request: Request,city: str, country_iso2: str, date: str):
    print(f'city : {city}, country : {country_iso2} ')
    url = f'https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{city},{country_iso2}/{date}?key={visualcrossing_api_key}'
    response = requests.get(url)
    response.raise_for_status()  # 요청 실패시 예외 발생
    data = response.json()
    # return data
    return templates.TemplateResponse("user_diary.html", {
        "request": request,
        "date": date,
        "country_iso2": country_iso2,
        "data" : data
    })

@app.get("/api/weather/history")
def get_weather_history(city: str, country_iso2: str, date: str):
    # 외부 날씨 API 호출
    date = date
    url = f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{city},{country_iso2}/{date}?key={visualcrossing_api_key}&unitGroup=metric"
    response = requests.get(url)
    response.raise_for_status()
    weather_day = response.json()
    weather_hour = weather_day['days'][0]['hours']
    # weather_hour = weather_day.get('days', [{}])[0].get('hours', [])
    print(date)
    hour_list = []
    for hour in weather_hour :
        datetime = hour["datetime"]
        temp = hour["temp"]
        conditions = hour["conditions"]
        hour_dictionary = {
            "datetime" : datetime,
            "temp" : temp,
            "conditions" : conditions
        }
        hour_list.append(hour_dictionary)
    print(f'hour_list : {hour_list}')
    return hour_list  # JSON 데이터 그대로 반환

# class Memo(BaseModel):
#     time: str
#     memo: str
#     tag: list[str]

class Memo(BaseModel):
    id: int | None = None
    time: str
    memo: str
    tag: list[str] = Field(default_factory=list)

class WeatherData(BaseModel):
    datetime: str
    temp: str
    condition: str

class DiaryEntrySaveRequest(BaseModel):
    diary_id: int
    time_recorded: time
    memo: str
    tags: List[str]

class DiarySaveRequest(BaseModel):
    country_iso2: str
    country_name: str
    city: str
    diary_date: date
    weather: List[WeatherData]
    memos: List[Memo]
    entries: Optional[List[DiaryEntrySaveRequest]] = None


class TagSaveRequest(BaseModel):
    name: str

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logging.error(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body}
    )

def custom_encoder(obj):
    if isinstance(obj, WeatherData): # WeatherData는 pydatic model: 바로 상단에 BaseModel 명시
        return obj.__dict__  # 또는 필요한 속성만 골라 dict 형태로 반환
    if isinstance(obj, Memo):  # 예: memo에 저장된 사용자 클래스
        return obj.__dict__
    raise TypeError(f'Object of type {obj.__class__.__name__} is not JSON serializable')


@app.post("/api/diary/save")
def save_diary_data(
    diary: DiarySaveRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    print("받은 memos 개수:", len(diary.memos))

    try:
        # 1. 같은 사용자, 날짜, 국가, 도시의 Diary 조회
        statement = select(Diary).where(
            Diary.user_id == current_user.id,
            Diary.diary_date == diary.diary_date,
            Diary.country_iso2 == diary.country_iso2,
            Diary.city == diary.city,
        )

        existing_diary = session.exec(statement).first()

        # 2. Diary가 없으면 생성, 있으면 기존 Diary 재사용
        if existing_diary:
            diary_orm = existing_diary

            diary_orm.country_name = diary.country_name
            diary_orm.weather = json.dumps(
                diary.weather,
                default=custom_encoder,
            )
            diary_orm.updated_at = datetime.utcnow()

        else:
            diary_orm = Diary(
                user_id=current_user.id,
                diary_date=diary.diary_date,
                country_iso2=diary.country_iso2,
                country_name=diary.country_name,
                city=diary.city,
                weather=json.dumps(
                    diary.weather,
                    default=custom_encoder,
                ),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

            session.add(diary_orm)

        # 새 Diary라면 id를 확보
        session.flush()

        print("현재 diary id:", diary_orm.id)

        # 3. 기존 DiaryEntry 조회
        existing_entries = session.exec(
            select(DiaryEntry)
            .where(DiaryEntry.diary_id == diary_orm.id)
        ).all()

        existing_entry_map = {
            entry.id: entry
            for entry in existing_entries
        }

        print(
            "기존 DiaryEntry:",
            [(entry.id, entry.memo) for entry in existing_entries]
        )

        # 4. 현재 요청에 포함된 기존 DiaryEntry ID 수집
        incoming_entry_ids = {
            memo_item.id
            for memo_item in diary.memos
            if memo_item.id is not None
        }

        print("현재 요청에 포함된 entry id:", incoming_entry_ids)

        # 5. 화면에서 삭제된 DiaryEntry를 DB에서도 삭제
        deleted_entries = [
            entry
            for entry in existing_entries
            if entry.id not in incoming_entry_ids
        ]

        for entry in deleted_entries:
            print("삭제할 DiaryEntry:", entry.id, entry.memo)

            # 먼저 태그 연결 삭제
            session.exec(
                delete(DiaryEntryTagLink).where(
                    DiaryEntryTagLink.diary_entry_id == entry.id
                )
            )

            # DiaryEntry 삭제 표시
            session.delete(entry)

        session.flush()

        # 6. 현재 요청에 포함된 모든 태그 이름 수집
        all_tag_names = set()

        for memo_item in diary.memos:
            if memo_item.tag:
                all_tag_names.update(memo_item.tag)

        print("전체 태그:", all_tag_names)

        # 7. 태그 조회 또는 생성
        tag_objs = {}

        if all_tag_names:
            existing_tags = session.exec(
                select(Tag).where(
                    Tag.user_id == current_user.id,
                    Tag.name.in_(list(all_tag_names)),
                )
            ).all()

            for tag in existing_tags:
                tag_objs[tag.name] = tag

            existing_tag_names = set(tag_objs.keys())

            for tag_name in all_tag_names - existing_tag_names:
                new_tag = Tag(
                    name=tag_name,
                    user_id=current_user.id,
                )

                session.add(new_tag)
                session.flush()

                tag_objs[tag_name] = new_tag

        # 8. DiaryEntry 수정 또는 생성
        for memo_item in diary.memos:
            print(
                "처리 중:",
                "id =", memo_item.id,
                "time =", memo_item.time,
                "memo =", memo_item.memo,
                "tag =", memo_item.tag,
            )

            try:
                time_obj = datetime.strptime(
                    memo_item.time,
                    "%H:%M",
                ).time()

            except ValueError:
                print("잘못된 시간 형식:", memo_item.time)
                continue

            # 8-1. 기존 DiaryEntry 수정
            if memo_item.id is not None:
                diary_entry = existing_entry_map.get(memo_item.id)

                # 현재 Diary에 속하지 않는 entry id 차단
                if diary_entry is None:
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid diary entry",
                    )

                diary_entry.time_recorded = time_obj
                diary_entry.memo = memo_item.memo

                print(
                    "기존 DiaryEntry 수정:",
                    diary_entry.id,
                )

                # 기존 태그 연결 삭제
                session.exec(
                    delete(DiaryEntryTagLink).where(
                        DiaryEntryTagLink.diary_entry_id
                        == diary_entry.id
                    )
                )

            # 8-2. 새 DiaryEntry 생성
            else:
                diary_entry = DiaryEntry(
                    diary_id=diary_orm.id,
                    time_recorded=time_obj,
                    memo=memo_item.memo,
                )

                session.add(diary_entry)
                session.flush()

                print(
                    "새 DiaryEntry 생성:",
                    diary_entry.id,
                )

            # 8-3. 현재 메모의 태그 연결
            for tag_name in memo_item.tag:
                tag = tag_objs.get(tag_name)

                if tag is None:
                    continue

                link = DiaryEntryTagLink(
                    diary_entry_id=diary_entry.id,
                    tag_id=tag.id,
                    user_id=current_user.id,
                )

                session.add(link)

        # 9. 사용하지 않는 태그 삭제
        session.flush()

        unused_tags = session.exec(
            select(Tag).where(
                Tag.user_id == current_user.id,
                ~Tag.entries.any(),
            )
        ).all()

        for tag in unused_tags:
            print("사용하지 않는 태그 삭제:", tag.id, tag.name)
            session.delete(tag)

        # 10. 최종 저장
        session.commit()

        print("Diary 저장 완료")

        return {
            "ok": True,
            "msg": "Diary saved",
            "diary_id": diary_orm.id,
        }

    except Exception:
        session.rollback()
        raise


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


