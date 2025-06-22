import os
from dotenv import load_dotenv
from getpass import getpass
from typing_extensions import TypedDict
from typing import Annotated, Literal, List
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from langchain.chat_models import init_chat_model
from prompt import get_recipe
from langchain_core.messages import HumanMessage, ToolMessage, SystemMessage
import asyncio
from langgraph.graph import StateGraph, START, END
from prompt import Recipe

# Get the directory where this script resides
script_dir = os.path.dirname(os.path.abspath(__file__))

# Construct full path to keys.env
env_path = os.path.join(script_dir, "keys.env")

# Load the .env file from that path
load_dotenv(env_path)

if not os.environ.get("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = getpass.getpass("Enter API key for Google Gemini: ")

class UserProfile(BaseModel):
    allergies: List[str] = Field(..., description="The user's allergies.")
    dislikes: List[str] = Field(..., description="Food that the user dislikes.")
    cooking_skill: str = Field(..., description="The user's level of cooking skills.")
    time_limit: float = Field(..., description="The users's preferred time limit for cooking.")
    nutrition: List[str] = Field(..., description="The user's perfence for recipe nutrition.")
    goals: str = Field(..., description="The user's goals in meal planning.")

sample_user_profile = UserProfile(
    allergies=["nuts"],
    dislikes=["chicken breast"],
    cooking_skill="beginner",
    time_limit=float('inf'),
    nutrition=[],
    goals="high protein diet"
)

class MealPlan(BaseModel):
    Monday: Recipe
    Tuesday: Recipe
    Wednesday: Recipe
    Thursday: Recipe
    Friday: Recipe
    Saturday: Recipe
    Sunday: Recipe

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

class State(TypedDict):
    messages: Annotated[list, add_messages]
    user_profile: UserProfile
    meal_plan: dict

llm = init_chat_model(
    model="gemini-2.0-flash", 
    model_provider="google_genai",
    temperature="0.2"
)

class DraftMealPlan(BaseModel):
    meals: list[str] = Field(..., description="A list of names for meal ideas for each day of the week.")

def GenerateInitialMealPlan(state: State):
    system_msg = "You are a helpful assistant that will generate meal ideas. "\
        "Take into account the user's preferences."
    
    assistant_llm = llm.with_structured_output(DraftMealPlan)
    result = assistant_llm.invoke([SystemMessage(system_msg), 
                          HumanMessage("My preferences are:" \
                                f"- allergies: {", ".join(sample_user_profile.allergies)}"\
                                f"- dislikes: {", ".join(sample_user_profile.dislikes)}"\
                                f"- cooking skill: {sample_user_profile.cooking_skill}"\
                                f"- goals: {sample_user_profile.goals}")])
    print(result.meals)
    # recipes = [get_recipe(meal) for meal in result.meals]
    dummy_recipe = Recipe(title="dummy", serving_size=0, prep_time=0, cook_time=0, ingredients="dummy", 
                          instructions="dummy", url=[])
    
    recipes = [get_recipe(result.meals[0]),
               dummy_recipe, 
               dummy_recipe, 
               dummy_recipe, 
               dummy_recipe,
               dummy_recipe,
               dummy_recipe]

    meal_plan = MealPlan(Monday=recipes[0],
                         Tuesday=recipes[1],
                         Wednesday=recipes[2],
                         Thursday=recipes[3],
                         Friday=recipes[4],
                         Saturday=recipes[5],
                         Sunday=recipes[6])

    return {"meal_plan": meal_plan}

graph_builder = StateGraph(State)
graph_builder.add_node("generate", GenerateInitialMealPlan)
graph_builder.add_edge(START, "generate")
graph_builder.add_edge("generate", END)
graph = graph_builder.compile()

if __name__ == "__main__":
    final_state = graph.invoke({
        "messages": [{"role": "user", "content": "Generate a weekly meal plan."}]
    })

    print(final_state["meal_plan"])