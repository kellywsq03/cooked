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

# Initialise chatbot
llm = init_chat_model(
    model="gemini-2.0-flash", 
    model_provider="google_genai",
    temperature="0.2"
)

# Initialise tools
search_tool = JinaSearch()

@tool
async def get_article(url: str):
    """Visit the webpage using the url. Read the article.
    Args: 
        url: First operand
    """
    jina_key = os.environ.get("JINA_API_KEY")
    new_link = f"https://r.jina.ai/{url}"
    headers = {
        "Authorization": f"Bearer {jina_key}"
    }
    await response = requests.get(new_link, headers=headers)
    print(response.text)

tools = [search_tool, get_article]
llm_with_tools = llm.bind_tools(tools)

def chatbot(state: State):
    return {"messages": [llm_with_tools.invoke(state["messages"])]}

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
graph_builder.add_edge("tools", "chatbot")

# Add recipe node
recipe_llm = init_chat_model(
    model="gemini-2.0-flash", 
    model_provider="google_genai",
    temperature="0.2"
)

def recipe_llm(state: State):
    system_msg = SystemMessage(
        "You are a helpful assistant that creates a recipe by closely referencing the online recipes provided, "
        "using your creativity whenever necessary to fit user requirements. You will maintain as much detail as possible "
        "regarding how the user should handle the food.  Include weight, time or size quantities as much as possible."
    )
    state["messages"].add(system_msg)
    return {"messages": [llm_with_tools.invoke(state["messages"])]}

messages = [HumanMessage(("Give me a detailed recipe for a high-protein meal. Include weight, time or size quantities"
                           "whereever possible. Search the web for recipes. Use the search results as close inspiration for your recipe."))]
ai_message = llm_with_tools.invoke(messages)
messages.append(ai_message)

class Link(BaseModel):
    link: str = Field(..., description="The url to a search result.")

for tool_call in ai_message.tool_calls:
    selected_tool = {"google_search": search_tool}[tool_call["name"].lower()]
    results = selected_tool.invoke(tool_call["args"]["__arg1"])
    
    tool_msg = ToolMessage(tool_call_id=tool_call["id"], content=results)
    
    messages.append(tool_msg)
    messages.append(HumanMessage("Here’s the search results. From these search results, give me only the link to the most relevant search result."))

structured_llm = llm.with_structured_output(Link)
top_result = structured_llm.invoke(messages)
print(top_result.link)

jina_key = os.environ.get("JINA_API_KEY")
new_link = f"https://r.jina.ai/{top_result.link}"
headers = {
    "Authorization": f"Bearer {jina_key}"
}
response = requests.get(new_link, headers=headers)
print(response.text)
messages.append(HumanMessage(response.text))
messages.append(HumanMessage("Here is the content of the most relevant search result. Extract the link to the most relevant recipe in the article provided."))
top_result = structured_llm.invoke(messages)
print(top_result)

new_link = f"https://r.jina.ai/{top_result.link}"
headers = {
    "Authorization": f"Bearer {jina_key}"
}
response = requests.get(new_link, headers=headers)
print(response.text)

messages.append(response.text)
messages.append(HumanMessage("Here is the most relevant recipe found on the web. Use this result as close inspiration for your recipe."))

class Recipe(BaseModel):
    title: str = Field(..., description="The title of the recipe. This title describes briefly what food the user will make by following the recipe.")
    serving_size: int = Field(..., description="The number of people that the cooked meal can feed.")
    prep_time: int = Field(..., description="The amount of time, in minutes, required to prepare the ingredients before cooking this meal. This includes but is not limited to time spent peeling, chopping and washing ingredients.")
    cook_time: int = Field(..., description="The amount of time, in minutes, required to cook this meal. This is the total amount of time to follow the instructions given in the recipe, subtracted by the prep_time")
    ingredients: str = Field(..., description="A detailed description of the required ingredients. Provide the required quantities of each ingredient, in UK measurements such as kg and ml.")
    instructions: str = Field(..., description="Provide detailed instructions that are easy to follow by users regardless of their culinary background. When using heat, specify if the heat is low, medium or high. Illustrate with words how each step should be carried out.")

structured_llm = llm.with_structured_output(Recipe)
response = structured_llm.invoke(messages)
print(response)