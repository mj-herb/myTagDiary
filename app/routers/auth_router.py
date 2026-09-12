from fastapi import APIRouter, Depends, HTTPException, status, Form, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from ..auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    get_current_user,
    validate_refresh_token,
    revoke_refresh_token,
    SECRET_KEY,
    ALGORITHM
)
from jose import jwt
from ..database import get_session
from ..redis_client import redis_client

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(prefix="/auth")

@router.post("/token")
async def login_for_access_token(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_session)
):
    user = authenticate_user(db, username, password)
    if not user:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "잘못된 아이디 또는 비밀번호입니다."
        })

    access_token = create_access_token(data={"sub": user.username})
    refresh_token = create_refresh_token(data={"sub": user.username})

    response = RedirectResponse(url=f"/users/{user.id}", status_code=303)
    # 쿠키에 토큰 저장 (httpOnly 설정하여 클라이언트 자바스크립트 접근 차단)
    response.set_cookie(key="access_token", value=access_token, httponly=True)
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True)
    return response

@router.post("/refresh")
async def refresh_token(refresh_token: str = Form(...)):
    if not validate_refresh_token(refresh_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
    username = payload.get("sub")
    access_token = create_access_token(data={"sub": username})
    return JSONResponse({"access_token": access_token, "token_type": "bearer"})

@router.post("/logout")
async def logout(access_token: str = Form(...), refresh_token: str = Form(...)):
    revoke_refresh_token(refresh_token)
    response = JSONResponse({"message": "로그아웃 완료"})
    # 쿠키 삭제 (반드시 클라이언트 로그아웃 시도시 설정)
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response
