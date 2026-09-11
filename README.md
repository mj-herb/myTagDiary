# myTagDiary

날짜별로 여행과 일상을 기록하고, 시간대별 메모와 태그를 관리할 수 있는 개인 다이어리 기능입니다.

## 다이어리 기능

- 날짜, 국가, 도시, 날씨를 저장
- 하나의 날짜에 여러 개의 시간별 메모 작성
- 메모별 태그 등록 및 수정
- 기존 메모 수정, 새 메모 추가, 삭제 지원
- 달력에서 다이어리가 작성된 날짜 확인
- 날짜별 다이어리와 시간별 메모 조회
- 태그를 기준으로 관련 메모 검색
- 사용자가 만든 Dot과 태그 연결
- Dot별 관련 다이어리 메모와 작성 날짜 확인
- Dot에 대한 댓글 및 답글 관리
- 사용자별 데이터 분리 및 관리

## Dot 이란??

Dot은 여러 다이어리 메모를 하나의 주제나 관심사로 묶어 관리하는 사용자 정의 그룹입니다.
- 사용자가 Dot을 직접 생성
- Dot 이름과 설명 작성
- 여러 태그를 Dot에 연결
- 태그를 기준으로 관련 다이어리 메모 조회
- Dot별 연결 태그 목록 확인
- Dot별 관련 메모와 작성 날짜 조회
- 하나의 태그를 여러 Dot과 DiaryEntry에 연결 가능
- Dot에 댓글 및 답글 작성
- 사용자가 작성한 Dot만 조회 및 관리
- Dot과 다이어리 메모의 연결 관계를 통해 주제별 기록 관리

## 인증 및 사용자 관리

- 회원가입 및 로그인 기능 제공
- 비밀번호를 bcrypt로 해싱하여 저장
- Access Token과 Refresh Token을 이용한 JWT 인증
- Access Token 만료 시간 30분
- Refresh Token 만료 시간 7일
- Redis를 이용한 Refresh Token 유효성 관리
- 로그아웃 시 Refresh Token 폐기
- 인증이 필요한 API에 현재 사용자 검증 적용
- 사용자별 데이터 접근 제한

## CRUD 기능

- Diary 생성, 조회, 수정, 삭제
- DiaryEntry 생성, 조회, 수정, 삭제
- Tag 생성, 조회, 연결 및 삭제
- Dot 생성, 조회, 수정, 삭제
- DiaryEntry와 Tag의 다대다 관계 관리
- Dot과 Tag의 다대다 관계 관리
- Dot 댓글 및 답글 생성과 조회
- 저장 시 화면과 데이터베이스의 메모 목록 동기화
- 사용자 ID를 기준으로 데이터 소유권 검증

## 구현 화면

### 로그인

사용자는 username과 password를 입력하여 서비스에 로그인할 수 있습니다.



### 달력

다이어리가 작성된 날짜를 달력에서 확인할 수 있습니다.



### 다이어리 작성

날짜, 국가, 도시, 날씨와 시간별 메모를 기록할 수 있습니다.



### 태그 기반 메모 관리

메모에 태그를 추가하고, 태그를 기준으로 관련 기록을 관리할 수 있습니다.



### Dot

Dot에 태그를 연결하면 관련된 다이어리 메모를 주제별로 모아볼 수 있습니다.



## 기술 스택

### Backend

- Python
- FastAPI
- SQLModel
- SQLAlchemy
- Pydantic
- JWT
- Passlib
- bcrypt
- Redis

### Database

- PostgreSQL

### Frontend

- HTML
- CSS
- JavaScript
- Jinja2 Template

### Authentication

- JWT Access Token
- JWT Refresh Token
- HTTP Cookie
- Redis 기반 Refresh Token 관리

### Development

- Uvicorn
- Alembic
- Git
- GitHub

## 주요 API

| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/register` | 회원가입 |
| POST | `/auth/token` | 로그인 및 Access Token 발급 |
| POST | `/auth/refresh` | Access Token 갱신 |
| POST | `/auth/logout` | Refresh Token 폐기 |
| GET | `/user/profile` | 사용자 달력 및 Dot 조회 |
| POST | `/api/diary/save` | 다이어리 저장 및 동기화 |
| GET | `/api/diary/{date}` | 날짜별 다이어리 조회 |
| POST | `/api/dot` | Dot 생성 |
| GET | `/api/dot` | Dot 목록 조회 |
| PUT | `/api/dot/{dot_id}` | Dot 수정 |
| DELETE | `/api/dot/{dot_id}` | Dot 삭제 |

## 데이터 흐름

```text
사용자
  ↓
로그인
  ↓
JWT Access Token 발급
  ↓
인증된 요청
  ↓
현재 사용자 확인
  ↓
Diary / DiaryEntry / Tag / Dot 조회 및 수정
  ↓
PostgreSQL 저장

