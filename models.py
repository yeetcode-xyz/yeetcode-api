"""
Pydantic models for YeetCode API
"""

from pydantic import BaseModel, EmailStr, model_validator
from typing import Optional, Dict, List


class EmailOTPRequest(BaseModel):
    email: EmailStr
    code: str


class EmailOTPResponse(BaseModel):
    success: bool
    message: str
    message_id: Optional[str] = None
    error: Optional[str] = None


class UserData(BaseModel):
    username: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    group_id: Optional[str] = None


class UserResponse(BaseModel):
    success: bool
    data: Optional[Dict] = None
    error: Optional[str] = None


class GroupRequest(BaseModel):
    username: str
    display_name: Optional[str] = None


class JoinGroupRequest(BaseModel):
    username: str
    invite_code: str
    display_name: Optional[str] = None


class GroupResponse(BaseModel):
    success: bool
    group_id: Optional[str] = None
    error: Optional[str] = None


class DailyProblemRequest(BaseModel):
    username: str
    date: Optional[str] = None


class DailyProblemResponse(BaseModel):
    success: bool
    data: Optional[Dict] = None
    error: Optional[str] = None


class BountyRequest(BaseModel):
    username: str
    bounty_id: Optional[str] = None
    increment: Optional[int] = 1


class DuelRequest(BaseModel):
    username: str
    duel_id: Optional[str] = None
    opponent: Optional[str] = None
    problem_slug: Optional[str] = None
    problem_title: Optional[str] = None
    problem_number: Optional[str] = None
    difficulty: Optional[str] = None
    is_wager: Optional[bool] = False
    wager_amount: Optional[int] = None

    @model_validator(mode='before')
    @classmethod
    def accept_camel_case_fields(cls, data):
        if not isinstance(data, dict):
            return data
        mapping = {
            'duelId':        'duel_id',
            'challenger':    'username',
            'challengee':    'opponent',
            'problemSlug':   'problem_slug',
            'problemTitle':  'problem_title',
            'problemNumber': 'problem_number',
            'isWager':       'is_wager',
            'wagerAmount':   'wager_amount',
        }
        for camel, snake in mapping.items():
            if camel in data and not data.get(snake):
                data[snake] = data[camel]
        return data