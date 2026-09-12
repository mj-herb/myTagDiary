from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from ..auth import get_current_user
from ..database import get_session
from ..models import User

templates = Jinja2Templates(directory="app/templates")
router = APIRouter()

@router.get("/users/{user_id}")
async def user_page(user_id: int, request: Request, current_user=Depends(get_current_user), db: Session = Depends(get_session)):
    if current_user.id != user_id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="권한이 없습니다.")
    user = db.get(User, user_id)
    return templates.TemplateResponse("user_page.html", {"request": request, "user": user})
