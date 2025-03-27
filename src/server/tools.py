from langchain_community.tools import GoogleSerperResults
import os

from dotenv import load_dotenv

load_dotenv()

SERPER_API_KEY = os.getenv("SERPER_API_KEY")

serper_tool = GoogleSerperResults(
    max_results=5,
    include_answer=True,
    description=(
        "This is a search tool for accessing the internet using Google Serper API. "
        "When using this tool, retrieve the most recent and accurate information. "
        "Then, synthesize key details (such as discount rates, valid dates, highlighted products, etc.) from the search results "
        "and provide a detailed summary to the user instead of merely redirecting them to a website."       
    ),
)

TOOLS = [serper_tool]

