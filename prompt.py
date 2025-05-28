import os
import getpass
import requests
from google import genai
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.tools import Tool, tool
from langchain_core.messages import HumanMessage, ToolMessage, SystemMessage
from langchain_google_community import GoogleSearchAPIWrapper
from langchain_community.tools import JinaSearch
from pydantic import BaseModel, Field
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

# Initialise StateGraph
class State(TypedDict):
    messages: Annotated[list, add_messages]

graph_builder = StateGraph(State)

# Initialise LLM
load_dotenv("keys.env")

if not os.environ.get("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = getpass.getpass("Enter API key for Google Gemini: ")

llm = init_chat_model(
    model="gemini-2.0-flash", 
    model_provider="google_genai",
    temperature="0.2"
)

# Initialise tools
search_tool = JinaSearch()

@tool
async def get_article(url: str) -> str:
    """Visit the webpage using the url. Read the article.
    Args: 
        url: First operand
    """
    jina_key = os.environ.get("JINA_API_KEY")
    new_link = f"https://r.jina.ai/{url}"
    headers = {
        "Authorization": f"Bearer {jina_key}"
    }
    response = await requests.get(new_link, headers=headers)
    print(response.text)
    return response.text

recipe_llm = init_chat_model(
    model="gemini-2.0-flash", 
    model_provider="google_genai",
    temperature="0.2"
)

class Recipe(BaseModel):
    title: str = Field(..., description="The title of the recipe. This title describes briefly what food the user will make by following the recipe.")
    serving_size: int = Field(..., description="The number of people that the cooked meal can feed.")
    prep_time: int = Field(..., description="The amount of time, in minutes, required to prepare the ingredients before cooking this meal. This includes but is not limited to time spent peeling, chopping and washing ingredients.")
    cook_time: int = Field(..., description="The amount of time, in minutes, required to cook this meal. This is the total amount of time to follow the instructions given in the recipe, subtracted by the prep_time")
    ingredients: str = Field(..., description="A detailed description of the required ingredients. Provide the required quantities of each ingredient, in UK measurements such as kg and ml.")
    instructions: str = Field(..., description="Provide detailed instructions that are easy to follow by users regardless of their culinary background. When using heat, specify if the heat is low, medium or high. Illustrate with words how each step should be carried out.")

structured_llm = llm.with_structured_output(Recipe)

@tool
def create_recipe(state: State) -> str:
    """
    Creates a recipe following the users requirements. Utilises detailed recipes found on the web as references for the created recipe.
    """
    system_msg = SystemMessage(
        "You are a helpful assistant that creates a recipe by closely referencing the online recipes provided, "
        "using your creativity whenever necessary to fit user requirements. You will maintain as much detail as possible "
        "regarding how the user should handle the food.  Include weight, time or size quantities as much as possible."
    )
    full_context = state["messages"].copy() + [system_msg]
    response = structured_llm.invoke(full_context)
    print(response)
    return response

tools = [search_tool, get_article, create_recipe]
llm_with_tools = llm.bind_tools(tools)

def chatbot(state: State):
    print(state["messages"])
    repsonse = llm_with_tools.invoke(state["messages"])
    print(repsonse)
    return {"messages": [repsonse]}

# Add chatbot node
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_edge(START, "chatbot")

# Add tool node
tool_node = ToolNode(tools=tools)
graph_builder.add_node("tools", tool_node)
graph_builder.add_conditional_edges(
    "chatbot",
    tools_condition,
)

graph = graph_builder.compile()
# from PIL import Image
# try:
#     with open("graph.png", "wb") as f:
#         f.write(graph.get_graph().draw_mermaid_png())
#     img = Image.open("graph.png")
#     img.show()
# except Exception:
#     print("exception")
#     # This requires some extra dependencies and is optional
#     pass

# def stream_graph_updates(user_input: str):
#     for event in graph.stream({"messages": [{"role": "user", "content": user_input}]}):
#         for value in event.values():
#             print("Assistant:", value["messages"][-1].content)

# while True:
#     try:
#         user_input = "User: Give me a recipe for a high-protein meal."
#         if user_input.lower() in ["quit", "exit", "q"]:
#             print("Goodbye!")
#             break
#         print("No error ")
#         stream_graph_updates(user_input)
#     except:
#         # fallback if input() is not available
#         user_input = "What do you know about LangGraph?"
#         print("User: " + user_input)
#         stream_graph_updates(user_input)
#         break
user_input = "User: Give me a recipe for a high-protein meal."
graph.invoke({"messages": [{"role": "user", "content": user_input}]})