from dotenv import load_dotenv
from langchain_groq import ChatGroq
from openai.resources import responses

load_dotenv()
def main():
    llm = ChatGroq(model="llama-3.3-70b-versatile")
    questions = [
        "What is the Future of AI?",
        "As Like I am Python Backend Developer with the 4.3 years of experience and I want add in my skillset Agentic AI after that I want switch Python Backend Developer + Agentic AI. Can you suggest me what should I prefer First?",
        "What is difference b/w Multithreading and Multitasking, MultiProcessing in details explanations with real life example like that I want implement Bank related Projects so will we manage this?",
        "Can you Explain in details django channels architecture Basic to Advance workflow",
        "We can use in my single project at a same time Websocket, Celery, Channel, RabbitMQ, Redis",
    ]

    for q in questions:
        print(f"\n? {q}")
        print("-" * 60)
        response = llm.invoke(q)
        print(f"AI Response: {response.content}")
        print("=" * 60)
    # response = llm.invoke("Hello! Kya tum Hindi mein jawab de sakta ho?")
    # print("AI Response:")
    # print(response.content)

if __name__ == "__main__":
    main()
