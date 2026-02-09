from praval import agent, tool, start_agents, get_reef


@tool("add_numbers", owned_by="calculator", category="math")
def add(x: int, y: int) -> int:
    return x + y


@agent("calculator", tools=["add_numbers"], auto_discover_tools=False)
def calc(spore):
    return {"result": add(2, 3)}


if __name__ == "__main__":
    start_agents(calc, initial_data={"type": "run"})
    get_reef().wait_for_completion()
    get_reef().shutdown()
