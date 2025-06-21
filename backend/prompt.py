import os
import getpass
import requests
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage, SystemMessage
from langchain_community.tools import JinaSearch
from pydantic import BaseModel, Field
from typing import Annotated, Literal, List
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command, interrupt
import asyncio

file = open("output.txt", "w")

# Get the directory where this script resides
script_dir = os.path.dirname(os.path.abspath(__file__))

# Construct full path to keys.env
env_path = os.path.join(script_dir, "keys.env")

# Load the .env file from that path
load_dotenv(env_path)

if not os.environ.get("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = getpass.getpass("Enter API key for Google Gemini: ")

class State(TypedDict):
    messages: Annotated[list, add_messages]
    sufficient_info: str
    feedback: str
    satisfactory: str
    final_recipe: dict

llm = init_chat_model(
    model="gemini-2.0-flash", 
    model_provider="google_genai",
    temperature="0.2"
)

search_tool = JinaSearch()

@tool
def get_article(url: str) -> str:
    """Read the full recipe by visiting the webpage using the url.
    Args: 
        url: One url to an article you are interested in reading.
    """
    print("getting article...")
    jina_key = os.environ.get("JINA_API_KEY")
    new_link = f"https://r.jina.ai/{url}"
    headers = {
        "Authorization": f"Bearer {jina_key}"
    }
    response = requests.get(new_link, headers=headers)
    return response.text

research_tools = [search_tool, get_article]
research_llm = llm.bind_tools(research_tools)

def research(state: State):
    print("Researching... ")
    system_msg = "You are a helpful assistant that will search the web for recipes using the tools provided. " \
        "Use relevant search queries to search for recipes using the search tool. " \
        "After using the search tool, you may read the full recipe by visiting the webpage using the url. " \
        "If there are links in the article, you can visit those links as well. "
    if state.get("feedback"):
        print("Feedback: " + state["feedback"])
        result = research_llm.invoke(state["messages"] + [SystemMessage(system_msg), HumanMessage("Take into account this feedback: " + state["feedback"])])
    else:
        print("Researching without feedback...")
        result = research_llm.invoke(state["messages"] + [SystemMessage(system_msg)])
    print(result)
    return {"messages": [result]}

class Feedback(BaseModel):
    grade: Literal["Sufficient", "Insufficient"] = Field(
        description="Decide if the current researched recipes are sufficient. The recipes are sufficient if they contain detailed " \
        "measurements and quantities of ingredients and specific instructions on how to cook the food at each step."
    )
    feedback: str = Field(
        description="If the recipes are insufficient, suggest what search queries to use.",
    )

def tools_router(state: State):
    """
    Use in the conditional_edge to route to the ToolNode if the last message
    has tool calls. Otherwise, route to the recipe evaluator node.
    """
    if isinstance(state, list):
        ai_message = state[-1]
    elif messages := state.get("messages", []):
        ai_message = messages[-1]
    else:
        raise ValueError(f"No messages found in input state to tool_edge: {state}")
    if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
        return "research tools"
    return "research evaluator"

def research_evaluator(state: State):
    print("evaluating...")
    system_msg = "You are a helpful assistant that will evaluate if the current recipes provide sufficient information to help another " \
        "large language model to create a recipe. The recipe should be detailed, containing measurements and descriptions of the food at each instruction step " \
        "whereever possible."
    evaluator_llm = llm.with_structured_output(Feedback)
    result = evaluator_llm.invoke(state["messages"] + [SystemMessage(system_msg)])
    print(result, file=file)
    return {"sufficient_info": result.grade,
            "feedback": result.feedback}

def route_research(state: State):
    """Route back to research agent or to summarise agent based on the feedback from the evaluator."""
    print("Routing from evaluator...")
    print(state["sufficient_info"] + "!")
    return state["sufficient_info"]

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
    instructions: str = Field(..., description="Provide detailed instructions that are easy to follow by users regardless of their culinary background. When using heat, specify if the heat is low, medium or high. Illustrate with words how each step should be carried out."\
                              "Each step should begin with an integer followed by a period, indicating the step number.")
    url: List[str] = Field(..., description="Referenced urls in the creation of the recipe.")

structured_llm = recipe_llm.with_structured_output(Recipe)

def create_recipe(state: State):
    """
    Creates a structured recipe. Utilises detailed recipes found on the web as references for the created recipe.
    Args:
        state: The entire message history stored in a State object.
    """
    print("creating recipe... ")
    system_msg = SystemMessage(
        "You are a helpful assistant that creates a recipe by closely referencing the online recipes provided, "
        "using your creativity whenever necessary to fit user requirements. You will maintain as much detail as possible "
        "regarding how the user should handle the food. Include weight, time or size quantities as much as possible."
    )
    if state.get("satisfactory"):
        full_context = state["messages"] + [system_msg] + [HumanMessage(f"Take into account this feedback: {state["feedback"]}")]
    else:
        full_context = state["messages"] + [system_msg]
    response = structured_llm.invoke(full_context)
    print(state["messages"] + [response], file=file)
    return {"final_recipe": response}

class RecipeFeedback(BaseModel):
    grade: Literal["satisfactory", "unsatisfactory"] = Field(
        description="Decide if the current recipe is satisfactory."
    )
    feedback: str = Field(description="Provide feedback on how to create a more satisfactory recipe.")

def recipe_evaluator(state: State):
    """
    Evaluates if the recipe
    1. Fits user's requirements
    2. Is detailed about the quantities and measurements of ingredients
    3. Is detailed in the instructions on how to prepare the food.
    """
    print("evaluating recipe...")
    system_msg = SystemMessage(
        "You are a helpful assistant that evaluates if the current recipe is satisfactory. A recipe is satisfactory if it: "\
        "1. Fits user's requirements "\
        "2. Is detailed about the quantities and measurements of ingredients "\
        "3. Is detailed in the instructions on how to prepare the food."
    )
    input = f"The current recipe is {state["final_recipe"]}"
    evaluator_llm = llm.with_structured_output(RecipeFeedback)
    response = evaluator_llm.invoke([system_msg, HumanMessage(input)])
    print(response, file=file)
    return {"satisfactory": response.grade,
            "feedback": response.feedback}

def creation_router(state: State):
    """Route back to creation agent or to end based on the feedback from the evaluator."""
    print("Routing from creation evaluator...")
    print(state["satisfactory"] + "!")
    return state["satisfactory"]

def build_recipe_graph():
    graph_builder = StateGraph(State)
    graph_builder.add_node("research", research)
    graph_builder.add_edge(START, "research")
    tool_node = ToolNode(tools=research_tools)
    graph_builder.add_node("research tools", tool_node)
    graph_builder.add_node("research evaluator", research_evaluator)
    graph_builder.add_conditional_edges(
        "research",
        tools_router,
        {"research tools": "research tools",
        "research evaluator": "research evaluator"}
    )
    graph_builder.add_edge("research tools", "research")
    graph_builder.add_node("create recipe",  create_recipe)
    graph_builder.add_conditional_edges("research evaluator", 
                                        route_research,
                                        {"Sufficient": "create recipe",
                                        "Insufficient": "research"})
    graph_builder.add_node("recipe evaluator", recipe_evaluator)
    graph_builder.add_conditional_edges("recipe evaluator",
                                        creation_router,
                                        {"satisfactory": END,
                                        "unsatisfactory": "create recipe"})
    graph_builder.add_edge("create recipe", "recipe evaluator")
    graph = graph_builder.compile()
    return graph

# try:
#     with open("graph.png", "wb") as f:
#         f.write(graph.get_graph().draw_mermaid_png())
# except Exception:
#     print("exception")
#     pass

def stream_graph_updates(user_input: str):
    graph = build_recipe_graph()
    for event in graph.stream({"messages": [{"role": "user", "content": user_input}]}):
        if "messages" in event:
            # print(event["messages"])
            event["messages"][-1].pretty_print()
            # for value in event.values():
            #     print("Assistant:", value["messages"][-1].content)  
    
async def get_recipe(recipe: str):
    try:
        graph = build_recipe_graph()
        user_input = f"Give me the recipe for {recipe}"
        final_state = await graph.ainvoke({
            "messages": [{"role": "user", "content": user_input}]
        })
        return final_state.get("final_recipe", "no recipe found.")
    except:
        return Recipe(title="dummy", serving_size=0, prep_time=0, cook_time=0, ingredients="dummy", instructions="dummy", url=[])

# recipe = input("recipe: ")

if __name__ == "__main__":
    r = input("Key in recipe: ")
    result = asyncio.run(get_recipe(r))
    print(result)