from openai import OpenAI
import os

print("OPENAI_API_KEY head:", os.getenv("OPENAI_API_KEY", "")[:10])
print("OPENAI_API_KEY tail:", os.getenv("OPENAI_API_KEY", "")[-6:])

client = OpenAI()

resp = client.responses.create(
    model="gpt-4o-mini",
    input="ping"
)

print(resp.output_text)