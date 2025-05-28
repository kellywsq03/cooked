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

# Initialise LLM
load_dotenv("keys.env")

if not os.environ.get("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = getpass.getpass("Enter API key for Google Gemini: ")

class State(TypedDict):
    messages: Annotated[list, add_messages]


graph_builder = StateGraph(State)


llm = init_chat_model(
    model="gemini-2.0-flash", 
    model_provider="google_genai",
    temperature="0.2"
)

search_tool = JinaSearch()

@tool
def get_article(url: str) -> str:
    """Search results only contain snippets of the recipe. You should read the full recipe.
    You can do this by visiting the webpage using the url. Read the article. If there are links in
    the article, you should visit those links using this tool as well.
    Args: 
        url: One url to an article you are interested in reading. The url should only contain one 'www.'
    """
    print(url[:50])
    jina_key = os.environ.get("JINA_API_KEY")
    new_link = f"https://r.jina.ai/{url}"
    headers = {
        "Authorization": f"Bearer {jina_key}"
    }
    response = requests.get(new_link, headers=headers)
    # print(response.text[:50])
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

structured_llm = recipe_llm.with_structured_output(Recipe)

@tool
def create_recipe(state: State):
    """
    Creates a structured recipe. Utilises detailed recipes found on the web as references for the created recipe.
    """
    system_msg = SystemMessage(
        "You are a helpful assistant that creates a recipe by closely referencing the online recipes provided, "
        "using your creativity whenever necessary to fit user requirements. You will maintain as much detail as possible "
        "regarding how the user should handle the food.  Include weight, time or size quantities as much as possible."
    )
    full_context = state["messages"] + [system_msg]
    response = structured_llm.invoke(full_context)
    print(response)
    return {"messages": [response]}

tools = [search_tool, get_article]
llm_with_tools = llm.bind_tools(tools)

def chatbot(state: State):
    return {"messages": [llm_with_tools.invoke(state["messages"])]}

graph_builder.add_node("chatbot", chatbot)
graph_builder.add_edge(START, "chatbot")
tool_node = ToolNode(tools=tools)
graph_builder.add_node("tools", tool_node)
graph_builder.add_conditional_edges(
    "chatbot",
    tools_condition,
)
graph_builder.add_edge("tools", "chatbot")
graph = graph_builder.compile()
def stream_graph_updates(user_input: str):
    for event in graph.stream({"messages": [{"role": "user", "content": user_input}]}):
        for value in event.values():
            print("Assistant:", value["messages"][-1].content)

while True:
    try:
        user_input = input("User: ")
        if user_input.lower() in ["quit", "exit", "q"]:
            print("Goodbye!")
            break
        stream_graph_updates(user_input)
    except:
        # fallback if input() is not available
        user_input = "What do you know about LangGraph?"
        print("User: " + user_input)
        stream_graph_updates(user_input)
        break