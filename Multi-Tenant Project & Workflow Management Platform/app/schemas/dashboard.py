from pydantic import BaseModel


class OrganizationDashboardResponse(BaseModel):
    total_projects: int 
    active_projects: int 
    completed_projects: int 
    total_tasks: int 
    overdue_tasks: int 


class ProjectManagerDashboardResponse(BaseModel):
    my_projects: int 
    open_tasks: int 
    completed_tasks: int 
    overdue_tasks: int 


class MyTasksDashboardResponse(BaseModel):
    my_tasks: int 
    overdue_tasks: int 
    tasks_due_today: int 
    recently_completed_tasks: int 
