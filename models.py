from typing import Literal
from pydantic import BaseModel, Field, field_validator
import re

class Credentials(BaseModel):
    email: str = Field(min_length=3,max_length=254)
    password: str = Field(min_length=12,max_length=128)
    @field_validator('email')
    @classmethod
    def email_valid(cls,v):
        v=v.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',v):
            raise ValueError('Enter a valid email address')
        return v

class Register(Credentials):
    name: str = Field(min_length=1,max_length=60)
    @field_validator('name')
    @classmethod
    def name_valid(cls,v):
        if not v.strip(): raise ValueError('Name is required')
        return v.strip()

class PasswordChange(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=12,max_length=128)

class Submission(BaseModel):
    answers: list[str] = Field(min_length=1,max_length=20)
    @field_validator('answers')
    @classmethod
    def lengths(cls,v):
        if any(len(x)>500 for x in v): raise ValueError('Answer too long')
        return v

class Command(BaseModel):
    command: str = Field(min_length=1,max_length=200)

class TutorMessage(BaseModel):
    unit_id: str = Field(max_length=80)
    message: str = Field(min_length=1,max_length=1500)
    allow_external: bool = False

class UserUpdate(BaseModel):
    role: Literal['learner','admin']
    active: bool

class Section(BaseModel):
    title: str = Field(min_length=1,max_length=120)
    text: str = Field(min_length=1,max_length=10000)

class Task(BaseModel):
    prompt: str = Field(min_length=1,max_length=500)
    hint: str = Field(min_length=1,max_length=1000)
    options: list[str] = Field(default_factory=list,max_length=8)
    answer: str | None = Field(default=None,min_length=1,max_length=500)
    answer_hash: str | None = Field(default=None,pattern=r'^[a-f0-9]{64}$')

class Content(BaseModel):
    sections: list[Section] = Field(min_length=1,max_length=20)
    tasks: list[Task] = Field(min_length=1,max_length=20)
    evidence: str = Field(default='',max_length=30000)
    commands: dict[str,str] = Field(default_factory=dict,max_length=20)
    @field_validator('commands')
    @classmethod
    def commands_valid(cls,v):
        if any(len(k)>200 or len(val)>10000 for k,val in v.items()): raise ValueError('Command content is too large')
        return v

class UnitWrite(BaseModel):
    id: str = Field(pattern=r'^[a-z0-9-]{1,80}$')
    path_id: str = Field(max_length=80)
    title: str = Field(min_length=1,max_length=120)
    summary: str = Field(min_length=1,max_length=300)
    kind: Literal['lesson','lab','challenge','capstone']
    minutes: int = Field(ge=1,le=180)
    xp: int = Field(ge=0,le=1000)
    published: bool = False
    revision: int = Field(default=0,ge=0)
    content: Content

class PathWrite(BaseModel):
    id: str = Field(pattern=r'^[a-z0-9-]{1,80}$')
    title: str = Field(min_length=1,max_length=120)
    description: str = Field(min_length=1,max_length=500)
    level: Literal['Beginner','Intermediate','Advanced']
