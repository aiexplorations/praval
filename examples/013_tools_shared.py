from praval import agent, tool, start_agents, get_reef


@tool("logger", shared=True, category="utility")
def log(level: str, message: str) -> str:
    import logging
    logging.getLogger("praval.tools").info(f"[{level}] {message}")
    return "ok"


@agent("writer")
def writer(spore):
    log("info", "writing started")
    return {"status": "done"}


if __name__ == "__main__":
    start_agents(writer, initial_data={"type": "run"})
    get_reef().wait_for_completion()
    get_reef().shutdown()
