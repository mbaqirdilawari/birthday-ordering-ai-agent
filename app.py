"""Web chat for the birthday ordering agent.

Terminal:
    python app.py
Then open http://127.0.0.1:5000 in a browser.

With ANTHROPIC_API_KEY set, the Claude agent answers. Without it, demo mode answers.
The right hand panel shows what the agent did behind the scenes (tool calls) and
which teams received the order.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from agent import OrderingSystem, make_agent
from agent.settings import load_env

load_env()  # read ANTHROPIC_API_KEY and AGENT_MODEL from .env if it exists

WEB = Path(__file__).resolve().parent / "agent" / "web"
app = Flask(__name__)
system = OrderingSystem()
sessions: dict[str, object] = {}


def _agent(session_id: str):
    if session_id not in sessions:
        sessions[session_id] = make_agent(system)
    return sessions[session_id]


@app.get("/")
def index():
    return send_from_directory(WEB, "index.html")


@app.post("/api/chat")
def chat():
    body = request.get_json(force=True)
    session_id = body.get("session_id") or str(uuid.uuid4())
    agent = _agent(session_id)
    reply, activity = agent.reply(body.get("message", ""))
    return jsonify({"session_id": session_id, "reply": reply, "activity": activity, "mode": agent.mode})


@app.get("/api/orders")
def orders():
    return jsonify({"bookings": list(system.bookings.values()), "outbox": system.outbox[-30:]})


@app.post("/api/reset")
def reset():
    sessions.pop((request.get_json(force=True) or {}).get("session_id", ""), None)
    return jsonify({"ok": True})


if __name__ == "__main__":
    mode = "Claude" if os.environ.get("ANTHROPIC_API_KEY") else "demo mode (no API key)"
    print(f"Birthday ordering agent running in {mode}: http://127.0.0.1:5000")
    app.run(debug=False, port=int(os.environ.get("PORT", 5000)))
