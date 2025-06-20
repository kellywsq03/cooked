from fastapi import FastAPI, Body
from prompt import get_recipe
from pydantic import BaseModel

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello"}


class RecipeRequest(BaseModel):
    recipe: str

@app.post("/")
async def run_app(request: RecipeRequest):
    return {"result": get_recipe(request.recipe).dict()}