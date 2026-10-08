"""Chat with the birthday ordering agent in the terminal.

Terminal:
    python run_chat.py
Type your messages. Type "quit" to stop.
Uses Claude if ANTHROPIC_API_KEY is set, otherwise demo mode.
"""
from agent import OrderingSystem, make_agent
from agent.settings import load_env


GOODBYE = "Agent: Thank you for chatting. Goodbye!"


def main(read=input) -> None:
    load_env()  # read ANTHROPIC_API_KEY and AGENT_MODEL from .env if it exists
    system = OrderingSystem()
    agent = make_agent(system)
    print(f"Birthday ordering agent ({agent.mode}). Type 'quit' or press Ctrl+C to stop.\n")
    print("Agent: Hello! Planning a birthday? Our ice cream trike can visit your party. How many children are coming?")
    while True:
        try:
            text = read("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            # Ctrl+C, or the end of piped input: stop cleanly instead of showing an error
            print()
            break
        if text.lower() in {"quit", "exit"}:
            break
        if not text:
            continue
        reply, activity = agent.reply(text)
        for a in activity:
            print(f"   [tool] {a['tool']}({a['input']})")
        print(f"Agent: {reply}\n")
    print(GOODBYE)


if __name__ == "__main__":
    main()
