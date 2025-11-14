import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Profile, Swipe, Match, Message, OTP

app = FastAPI(title="Dating App API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Utility to convert Mongo docs to JSON-safe

def to_doc(d):
    if not d:
        return d
    d = dict(d)
    if d.get("_id"):
        d["id"] = str(d.pop("_id"))
    # Convert datetime fields to isoformat if present
    for k, v in list(d.items()):
        try:
            import datetime
            if isinstance(v, (datetime.datetime, datetime.date)):
                d[k] = v.isoformat()
        except Exception:
            pass
    return d


# Health
@app.get("/")
def root():
    return {"message": "Dating API running"}


# Auth (email OTP for demo). In production, send code via email
class RequestOTP(BaseModel):
    email: EmailStr


class VerifyOTP(BaseModel):
    email: EmailStr
    code: str


@app.post("/auth/request-otp")
def request_otp(payload: RequestOTP):
    # Generate a simple 6-digit code and store it
    import random
    code = f"{random.randint(100000, 999999)}"
    create_document("otp", {"email": payload.email, "code": code})
    # For demo, return code directly (in real app, email it)
    return {"sent": True, "code": code}


@app.post("/auth/verify-otp")
def verify_otp(payload: VerifyOTP):
    docs = db["otp"].find({"email": payload.email}).sort("created_at", -1).limit(1)
    doc = next(docs, None)
    if not doc or doc.get("code") != payload.code:
        raise HTTPException(status_code=400, detail="Invalid code")
    # Upsert a profile shell if not exists
    existing = db["profile"].find_one({"email": payload.email})
    if not existing:
        pid = create_document("profile", {"email": payload.email, "name": payload.email.split("@")[0]})
        return {"ok": True, "profile_id": pid}
    return {"ok": True, "profile_id": str(existing.get("_id"))}


# Profile endpoints
class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    bio: Optional[str] = None
    interests: Optional[List[str]] = None
    photos: Optional[List[str]] = None
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None


@app.get("/profiles/me")
def get_me(profile_id: str):
    doc = db["profile"].find_one({"_id": ObjectId(profile_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Profile not found")
    return to_doc(doc)


@app.put("/profiles/me")
def update_me(profile_id: str, payload: ProfileUpdate):
    update = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
    if not update:
        return {"updated": False}
    db["profile"].update_one({"_id": ObjectId(profile_id)}, {"$set": update})
    doc = db["profile"].find_one({"_id": ObjectId(profile_id)})
    return to_doc(doc)


# Discovery - get candidate profiles (very simple: everyone except me)
@app.get("/discover")
def discover(profile_id: str, limit: int = 10):
    cursor = db["profile"].find({"_id": {"$ne": ObjectId(profile_id)}}).limit(limit)
    return [to_doc(d) for d in cursor]


# Swipes and matching
class SwipeIn(BaseModel):
    target_id: str
    action: str  # like | pass


@app.post("/swipe")
def swipe(profile_id: str, payload: SwipeIn):
    if payload.action not in ("like", "pass"):
        raise HTTPException(status_code=400, detail="Invalid action")
    create_document("swipe", {"user_id": profile_id, "target_id": payload.target_id, "action": payload.action})
    is_match = False
    match_id = None
    if payload.action == "like":
        # Check if target already liked me
        liked_me = db["swipe"].find_one({
            "user_id": payload.target_id,
            "target_id": profile_id,
            "action": "like"
        })
        if liked_me:
            # Create match if not existing
            existing = db["match"].find_one({
                "$or": [
                    {"user_a": profile_id, "user_b": payload.target_id},
                    {"user_a": payload.target_id, "user_b": profile_id},
                ]
            })
            if not existing:
                match_id = create_document("match", {"user_a": profile_id, "user_b": payload.target_id})
            else:
                match_id = str(existing.get("_id"))
            is_match = True
    return {"ok": True, "match": is_match, "match_id": match_id}


# Matches list
@app.get("/matches")
def matches(profile_id: str):
    cursor = db["match"].find({
        "$or": [{"user_a": profile_id}, {"user_b": profile_id}]
    }).sort("created_at", -1)
    out = []
    for m in cursor:
        m_doc = to_doc(m)
        other_id = m_doc["user_b"] if m_doc["user_a"] == profile_id else m_doc["user_a"]
        other = db["profile"].find_one({"_id": ObjectId(other_id)})
        m_doc["other"] = to_doc(other) if other else None
        out.append(m_doc)
    return out


# Messages
class MessageIn(BaseModel):
    text: str


@app.get("/messages")
def list_messages(match_id: str, limit: int = 50):
    cursor = db["message"].find({"match_id": match_id}).sort("created_at", -1).limit(limit)
    return [to_doc(m) for m in cursor][::-1]


@app.post("/messages")
def send_message(match_id: str, sender_id: str, payload: MessageIn):
    mid = create_document("message", {"match_id": match_id, "sender_id": sender_id, "text": payload.text})
    doc = db["message"].find_one({"_id": ObjectId(mid)})
    return to_doc(doc)


# Test DB connectivity
@app.get("/test")
def test_database():
    response = {"backend": "✅ Running", "database": "❌ Not Available"}
    try:
        if db is not None:
            response["database"] = "✅ Connected"
            response["collections"] = db.list_collection_names()
        else:
            response["database"] = "❌ Not Connected"
    except Exception as e:
        response["error"] = str(e)
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
