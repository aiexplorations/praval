from praval import agent, tool, Agent


@tool("weather", category="external", shared=True)
def get_weather(city: str) -> str:
    return f"Sunny in {city}"


@agent("assistant", tool_categories=["external"], auto_discover_tools=False)
def assistant(spore):
    return {"answer": "Ask me the weather."}


if __name__ == "__main__":
    llm = Agent("assistant")
    llm.tools["weather"] = {
        "function": get_weather,
        "description": "Get weather",
        "parameters": {"city": {"type": "str", "required": True}}
    }
    try:
        print(llm.chat("What's the weather in Paris?"))
    except Exception as exc:
        # Keep this example runnable in offline/test environments.
        print(f"LLM unavailable, tool fallback: {exc}")
        print(get_weather("Paris"))
