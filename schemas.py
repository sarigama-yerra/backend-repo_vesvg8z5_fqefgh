"""
Database Schemas for the 1v1 Coding Platform

Each Pydantic model represents a MongoDB collection. The collection
name is the lowercase of the class name.
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class Question(BaseModel):
    title: str = Field(..., description="Problem title")
    slug: str = Field(..., description="URL-safe identifier")
    difficulty: str = Field(..., description="Easy | Medium | Hard")
    tags: List[str] = Field(default_factory=list)
    statement: str = Field(..., description="Full problem statement (markdown)")
    examples: List[dict] = Field(default_factory=list, description="List of input/output examples")

class Room(BaseModel):
    room_id: str = Field(..., description="Unique room identifier")
    participants: List[str] = Field(default_factory=list, description="User display names")
    question_slug: Optional[str] = Field(None, description="Selected question slug")
    editor_content: str = Field(default="", description="Shared editor content")
    created_at: Optional[datetime] = None

class Message(BaseModel):
    room_id: str
    sender: str
    content: str
    type: str = Field("chat", description="chat | system")

class Match(BaseModel):
    name: str
    status: str = Field("waiting", description="waiting | paired")
    room_id: Optional[str] = None
