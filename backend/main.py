from fastapi import FastAPI, Body
from prompt import get_recipe
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

origins = [
    "http://localhost:3000",
    "http://localhost:5173"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Hello"}


class RecipeRequest(BaseModel):
    recipe: str

@app.post("/")
async def run_app(request: RecipeRequest):
    return {"result": get_recipe(request.recipe).model_dump()}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)