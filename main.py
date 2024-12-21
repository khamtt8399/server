from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# Thay đổi URL kết nối sang MySQL
DATABASE_URL = "mysql+pymysql://khamtt:Tuongkham99!@localhost/chatdb"

# Kết nối đến MySQL
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Khởi tạo cơ sở dữ liệu nếu chưa tồn tại
Base.metadata.create_all(bind=engine)


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String, index=True)
    message = Column(String)
    create_at = Column(DateTime, default=datetime.utcnow)


# Quản lý kết nối kèm username
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, username: str):
        await websocket.accept()
        self.active_connections[websocket] = username

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            del self.active_connections[websocket]

    async def broadcast(self, message: str, sender: WebSocket):
        for connection, username in self.active_connections.items():
            await connection.send_text(message)


def save_message(db, username: str, message: str):
    message = Message(username=username, message=message)
    db.add(message)
    db.commit()


def get_all_messages(db):
    return db.query(Message).order_by(Message.create_at.asc()).all()


manager = ConnectionManager()


@app.get("/", response_class=HTMLResponse)
async def get_chat_page():
    return templates.TemplateResponse("index.html", {"request": {}})


@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    db = SessionLocal()
    await manager.connect(websocket, username)

    # Gửi lịch sử tin nhắn cũ cho user khi kết nối
    messages = get_all_messages(db)
    for msg in messages:
        await websocket.send_text(f"{msg.username}: {msg.message}")

    try:
        while True:
            data = await websocket.receive_text()
            save_message(db, username, data)  # Lưu tin nhắn vào MySQL
            message = f"{username}: {data}"
            await manager.broadcast(message, sender=websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    finally:
        db.close()
