import os
import random
import string
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents
from schemas import Question, Room, Message, Match

app = FastAPI(title="1v1 DSA Coding Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------- Utility helpers ---------

def _gen_room_id(n: int = 6) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))


def _get_collection(name: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    return db[name]


# --------- Request models ---------

class JoinPayload(BaseModel):
    name: str

class SendMessagePayload(BaseModel):
    sender: str
    content: str

class UpdateEditorPayload(BaseModel):
    content: str


# --------- Health ---------

@app.get("/")
def root():
    return {"message": "1v1 Coding Platform Backend running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_name"] = getattr(db, "name", "✅ Connected")
            response["connection_status"] = "Connected"
            try:
                response["collections"] = db.list_collection_names()
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:50]}"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    import os as _os
    response["database_url"] = "✅ Set" if _os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if _os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


# --------- Questions ---------

@app.get("/api/questions", response_model=List[Question])
def list_questions():
    col = _get_collection("question")
    docs = list(col.find({}, {"_id": 0}))
    return docs


@app.post("/api/seed-questions")
def seed_questions():
    col = _get_collection("question")
    if col.count_documents({}) > 0:
        return {"seeded": False, "message": "Questions already exist"}
    samples: List[Question] = [
        Question(
            title="Two Sum",
            slug="two-sum",
            difficulty="Easy",
            tags=["array", "hashmap"],
            statement=(
                "Given an array of integers nums and an integer target, return indices of the"
                " two numbers such that they add up to target."
            ),
            examples=[{"input": "nums=[2,7,11,15], target=9", "output": "[0,1]"}],
        ),
        Question(
            title="Valid Parentheses",
            slug="valid-parentheses",
            difficulty="Easy",
            tags=["stack", "string"],
            statement=(
                "Given a string s containing only the characters '()[]{}', determine if the"
                " input string is valid."
            ),
            examples=[{"input": "s=()[]{}", "output": "true"}],
        ),
        Question(
            title="Longest Substring Without Repeating Characters",
            slug="longest-substring",
            difficulty="Medium",
            tags=["hashmap", "sliding-window"],
            statement=(
                "Given a string s, find the length of the longest substring without repeating characters."
            ),
            examples=[{"input": "abcabcbb", "output": "3"}],
        ),
    ]
    for q in samples:
        create_document("question", q)
    return {"seeded": True, "count": len(samples)}


# --------- Matchmaking & Rooms ---------

@app.post("/api/matchmaking/join")
def matchmaking_join(payload: JoinPayload):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    match_col = _get_collection("match")

    # Try to find another waiting user
    other = match_col.find_one({"status": "waiting"})
    if other is None:
        # Put this user in waiting queue
        create_document("match", Match(name=name).model_dump())
        return {"status": "waiting"}

    # Pair and create room
    room_id = _gen_room_id()

    # Choose a random question
    q_col = _get_collection("question")
    qdoc = q_col.aggregate([{ "$sample": {"size": 1}}])
    q = next(qdoc, None)
    question_slug = q.get("slug") if q else None

    room = Room(
        room_id=room_id,
        participants=[other["name"], name],
        question_slug=question_slug,
        editor_content="",
    )
    create_document("room", room)

    # Update other match and remove waiting entries for both
    match_col.delete_one({"_id": other["_id"]})

    # System message
    create_document("message", Message(room_id=room_id, sender="system", content="Match found!", type="system"))

    return {"status": "paired", "room_id": room_id}


@app.get("/api/room/{room_id}")
def get_room(room_id: str):
    col = _get_collection("room")
    doc = col.find_one({"room_id": room_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Room not found")
    # Also include question data
    if doc.get("question_slug"):
        q = _get_collection("question").find_one({"slug": doc["question_slug"]}, {"_id": 0})
        doc["question"] = q
    else:
        doc["question"] = None
    return doc


@app.get("/api/room/{room_id}/messages")
def get_messages(room_id: str, limit: int = 50):
    col = _get_collection("message")
    docs = list(col.find({"room_id": room_id}, {"_id": 0}).sort("created_at", 1).limit(limit))
    return docs


@app.post("/api/room/{room_id}/messages")
def send_message(room_id: str, payload: SendMessagePayload):
    # Validate room exists
    r = _get_collection("room").find_one({"room_id": room_id})
    if not r:
        raise HTTPException(status_code=404, detail="Room not found")
    create_document("message", Message(room_id=room_id, sender=payload.sender, content=payload.content))
    return {"ok": True}


@app.put("/api/room/{room_id}/editor")
def update_editor(room_id: str, payload: UpdateEditorPayload):
    col = _get_collection("room")
    res = col.update_one({"room_id": room_id}, {"$set": {"editor_content": payload.content}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Room not found")
    return {"ok": True}
