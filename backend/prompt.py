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
import time, json
from langchain_tavily import TavilySearch
from helper import UserProfile, sample_user_profile

script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, "keys.env")
write_path = os.path.join(script_dir, "output.txt")
write_file = open(write_path, "w")
load_dotenv(env_path)
if not os.environ.get("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = getpass.getpass("Enter API key for Google Gemini: ")

class State(TypedDict):
    messages: Annotated[list, add_messages]
    sufficient_info: str
    feedback: str
    satisfactory: str
    final_recipe: dict
    user_profile: UserProfile
    search_results: dict
    loop_count: int = 0
    urls: list

llm = init_chat_model(
    model="gemini-2.0-flash", 
    model_provider="google_genai",
    temperature="0.2"
)

class Links(BaseModel):
    queries: List[str] = Field(..., description="A list of search queries for a search engine.")

def research(state: State):
    print("Researching... ")
    system_msg = "You are a helpful assistant that will come up with relevant search queries " \
        "for a search engine. These search queries must be for recipes that another llm " \
        "will reference in the creation of a recipe that meets the user's needs. "
    research_llm = llm.with_structured_output(Links)
    if state.get("feedback"):
        print(state["feedback"])
        result = research_llm.invoke(state["messages"] + 
                                     [SystemMessage(system_msg), 
                                      HumanMessage(state.get("feedback"))])
    else:
        result = research_llm.invoke(state["messages"] + [SystemMessage(system_msg)])
    search_tool = TavilySearch(max_results=3)
    search_results = []
    acc_urls = []
    print("query result: ", file=write_file)
    print(result.queries, file=write_file)
    for q in result.queries:
        search_result = search_tool.invoke({"query": q})
        acc_urls.append(search_result["results"][0]["url"])
        search_results.append(search_result)
    print("urls", state["urls"])
    print("acc urls", acc_urls)
    print("done searching!")
    print("search_results", search_results[0]["results"][0])
    print("search results", file=write_file)
    print(search_results, file=write_file)
    acc_urls.extend(state["urls"])
    return {"search_results": search_results[0]["results"][0],
            "urls": acc_urls}

class Feedback(BaseModel):
    grade: Literal["Sufficient", "Insufficient"] = Field(
        description="Decide if the current researched recipes are sufficient. The recipes are sufficient if they contain " \
        "measurements and quantities of ingredients and specific instructions on how to cook the food at each step."
    )
    feedback: str = Field(
        description="If the recipes are insufficient, suggest what search queries to use.",
    )
    # urls: list[str] = Field(..., description="A list of urls to visit.")

def research_evaluator(state: State):
    print("evaluating...")
    if state["loop_count"] > 2:
        state["loop_count"] = 0
        return {"sufficient_info": "Sufficient",
            "feedback": ""}
    system_msg = "You are a helpful assistant that will evaluate if the current recipes provide sufficient information to help another " \
        "large language model to create a recipe. The recipe should be detailed, containing measurements and descriptions of the food " \
        "at each instruction step whereever possible. "
    evaluator_llm = llm.with_structured_output(Feedback)
    search_results_message = SystemMessage(
        content=f"Here are the search results: {json.dumps(state["search_results"], indent=2)}")
    print("Search_results_message: ", search_results_message)
    print("search results message: ", file=write_file)
    print(search_results_message, file=write_file)
    result = evaluator_llm.invoke(state["messages"] + [search_results_message] + 
                                  [SystemMessage(system_msg)])
    print("result", file=write_file)
    print(result, file=write_file)
    return {"sufficient_info": result.grade,
            "feedback": result.feedback,
            "loop_count": 0 if result.grade == "Sufficient" else state["loop_count"] + 1}

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
        "regarding how the user should handle the food. Include weight, time or size quantities as much as possible." \
        "In the referenced context, extract the urls."
    )
    if state.get("feedback"):
        full_context = state["messages"] + [system_msg] + [HumanMessage(f"Take into account this feedback: {state["feedback"]}")]
    else:
        full_context = state["messages"] + [system_msg]
    response = structured_llm.invoke(full_context)
    print("Recipe resopnse: ", response)
    print(state["messages"] + [response], file=write_file)
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
    if state["loop_count"] > 2:
        state["loop_count"] = 0
        return {"satisfactory": "satisfactory",
            "feedback": ""}
    system_msg = SystemMessage(
        "You are a helpful assistant that evaluates if the current recipe is satisfactory. A recipe is satisfactory if it: "\
        "1. Avoids user's allergies "\
        "2. Is detailed about the quantities and measurements of ingredients "\
        "3. Is detailed in the instructions on how to prepare the food."\
        "4. Meets the user's nutritional needs"
    )
    input = f"The current recipe is {state["final_recipe"]}"\
        f"The user's allergies are {','.join(state["user_profile"].allergies)}"\
        f"The user's nutritional needs are {','.join(state["user_profile"].nutrition)}"
    evaluator_llm = llm.with_structured_output(RecipeFeedback)
    response = evaluator_llm.invoke([system_msg, HumanMessage(input)])
    print(response, file=write_file)
    return {"satisfactory": response.grade,
            "feedback": response.feedback,
            "loop_count": 0 if response.grade == "satisfactory" else state["loop_count"] + 1}

def creation_router(state: State):
    """Route back to creation agent or to end based on the feedback from the evaluator."""
    print("Routing from creation evaluator...")
    print(state["satisfactory"] + "!")
    return state["satisfactory"]

def build_recipe_graph():
    graph_builder = StateGraph(State)
    graph_builder.add_node("research", research)
    graph_builder.add_edge(START, "research")
    graph_builder.add_node("research evaluator", research_evaluator)
    graph_builder.add_edge("research", "research evaluator")
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
    # try:
    #     with open("graph.png", "wb") as f:
    #         f.write(graph.get_graph().draw_mermaid_png())
    # except Exception:
    #     print("exception")
    #     pass
    return graph


def stream_graph_updates(user_input: str):
    graph = build_recipe_graph()
    for event in graph.stream({"messages": [{"role": "user", "content": user_input}]}):
        if "messages" in event:
            # print(event["messages"])
            event["messages"][-1].pretty_print()
            # for value in event.values():
            #     print("Assistant:", value["messages"][-1].content)  
    
def get_recipe(recipe: str) -> Recipe:
    retries = 2
    delay = 3
    for attempt in range(retries):
        print(f"this is attempt {attempt}")
        try:
            graph = build_recipe_graph()
            user_input = f"Give me the recipe for {recipe}"
            final_state = graph.invoke({
                "messages": [{"role": "user", "content": user_input}],
                "user_profile": sample_user_profile,
                "loop_count": 0,
                "urls": []
            })
            print("final urls", final_state.get("urls"))
            final_state.get("final_recipe", "no recipe found.").url.extend(final_state.get("urls"))
            return final_state.get("final_recipe", "no recipe found.")
        except Exception as e:
            print(e)
            time.sleep(delay)
    return Recipe(title="dummy", serving_size=0, prep_time=0, cook_time=0, ingredients="dummy", instructions="dummy", url=[])

if __name__ == "__main__":
    r = input("Key in recipe: ")
    result = get_recipe(r)
    print(result)