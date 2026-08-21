from dotenv import load_dotenv
from youtube.llm import get_client

load_dotenv()
client = get_client()

for m in client.models.list():
    print(m.name)