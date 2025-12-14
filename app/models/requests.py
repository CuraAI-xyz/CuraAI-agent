from pydantic import BaseModel

class UserIdRequest(BaseModel):
    userId: str
    name: str
    surname: str
    sex: str
    patient_id: str

