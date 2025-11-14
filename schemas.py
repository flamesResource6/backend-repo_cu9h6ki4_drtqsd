"""
Database Schemas for Dating App

Each Pydantic model represents a collection in MongoDB.
Collection name is the lowercase of the class name.
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Literal


class Profile(BaseModel):
    """
    Profiles collection schema
    Collection name: "profile"
    """
    email: EmailStr = Field(..., description="Unique email for login (OTP-based)")
    name: str = Field(..., description="Display name")
    age: Optional[int] = Field(None, ge=18, le=100, description="Age in years")
    gender: Optional[Literal["male", "female", "non-binary", "other"]] = None
    bio: Optional[str] = Field(None, description="Short bio")
    interests: List[str] = Field(default_factory=list, description="List of interests/tags")
    photos: List[str] = Field(default_factory=list, description="List of photo URLs")
    location_lat: Optional[float] = Field(None, description="Latitude")
    location_lng: Optional[float] = Field(None, description="Longitude")
    is_active: bool = Field(True, description="Whether the profile is active")


class Swipe(BaseModel):
    """
    Swipes collection schema
    Collection name: "swipe"
    """
    user_id: str = Field(..., description="User who swiped")
    target_id: str = Field(..., description="User who was swiped on")
    action: Literal["like", "pass"] = Field(..., description="Swipe action")


class Match(BaseModel):
    """
    Matches collection schema
    Collection name: "match"
    """
    user_a: str = Field(..., description="One user in the match")
    user_b: str = Field(..., description="The other user in the match")


class Message(BaseModel):
    """
    Messages collection schema
    Collection name: "message"
    """
    match_id: str = Field(..., description="Match ID this message belongs to")
    sender_id: str = Field(..., description="Sender user id")
    text: str = Field(..., min_length=1, max_length=2000, description="Message text")


class OTP(BaseModel):
    """
    OTP codes collection schema (for demo). In production, send codes via email/SMS.
    Collection name: "otp"
    """
    email: EmailStr
    code: str
