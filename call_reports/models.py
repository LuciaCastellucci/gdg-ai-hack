from pydantic import BaseModel, Field
from typing import List, Optional
from bson import ObjectId


class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler):
        from pydantic_core import core_schema

        return core_schema.union_schema(
            [
                core_schema.is_instance_schema(ObjectId),
                core_schema.chain_schema(
                    [
                        core_schema.str_schema(),
                        core_schema.no_info_plain_validator_function(cls.validate),
                    ]
                ),
            ]
        )

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, _core_schema, handler):
        json_schema = handler(_core_schema)
        json_schema.update(type="string")
        return json_schema


class Report(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    date: str
    topic: str
    content: str
    timestamp_expected: str
    timestamp_actual: str

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str},
        "json_schema_extra": {
            "example": {
                "date": "2025-05-10",
                "topic": "Team Meeting",
                "content": "Discussion about new AI features",
                "timestamp_expected": "10:00",
                "timestamp_actual": "10:05",
            }
        },
    }


class CallLog(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    date: str
    topic: str
    participants: List[str]
    report: str

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str},
        "json_schema_extra": {
            "example": {
                "date": "2025-05-10",
                "topic": "Team Meeting",
                "participants": ["Alice", "Bob", "Charlie"],
                "report": "Discussion about new AI features and project timeline. Action items were assigned to team members.",
            }
        },
    }
