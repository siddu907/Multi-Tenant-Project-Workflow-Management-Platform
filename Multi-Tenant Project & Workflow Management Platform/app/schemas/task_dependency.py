from pydantic import BaseModel, Field


class TaskDependencyCreate(BaseModel):
    depends_on_task_id: int = Field(..., gt=0)


class TaskDependencyResponse(BaseModel):
    id: int
    task_id: int
    depends_on_task_id: int
