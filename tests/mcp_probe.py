# A small MCP client for trying the front door by hand.   (data/POLICY.md, section 7)
#
# An AI app such as Claude Desktop starts the server as a program, sends it messages and shows you the
# replies. This file does the same in plain code, so that you can WATCH the messages go back and forth.
# It is a visitor to the front door and is not part of it.
#
# Usage:
#     python -m tests.mcp_probe Premkumar "How many casual leave days do I get?"
#     python -m tests.mcp_probe Dhanesh "How many casual leave days do I get?" --show
#
#     --show   also print every message, in both directions
#
# What it does:
#     1. makes a sign-in token for that person (src/issue_token.py, valid for 15 minutes)
#     2. starts the server with the token in its environment, and nowhere else
#     3. says hello (initialize), asks for the tool list, asks the question
#     4. closes the server's input, which is how an AI app says goodbye, and waits for it to stop
# Like src/ask.py, it needs Ollama running and the Qdrant data built (python -m src.ingest).

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOKEN_VARIABLE = "PERMITRAG_TOKEN"
ANSWER_WAIT_SECONDS = 600   # a small model on a plain computer can need a minute or more


def say(*parts):
    # print() that cannot fail on a console that does not know some letter
    text = " ".join(str(part) for part in parts)
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode("ascii"))


class ServerProcess:
    # The server, started the way an AI app starts it: as its own program, talking over its standard input and output.
    def __init__(self, token=None, show=False, script=None, folder=None):
        environment = dict(os.environ)
        environment.pop(TOKEN_VARIABLE, None)
        # An AI app does not ask for unbuffered output. Without this line, a server that forgets to flush its
        # replies would still seem to work on a computer where Python is set to be unbuffered.
        environment.pop("PYTHONUNBUFFERED", None)
        if token is not None:
            environment[TOKEN_VARIABLE] = token
        self.show = show
        self.process = subprocess.Popen(
            [sys.executable, str(script or PROJECT_ROOT / "run_mcp_server.py")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment, cwd=folder,
        )
        self.replies = queue.Queue()   # lines from the server's standard output
        self.notes = []                # lines from its standard error
        threading.Thread(target=self.collect_replies, daemon=True).start()
        threading.Thread(target=self.collect_notes, daemon=True).start()

    def collect_replies(self):
        for line in self.process.stdout:
            self.replies.put(line)
        self.replies.put(None)   # None means: the server's output has ended

    def collect_notes(self):
        for line in self.process.stderr:
            self.notes.append(line.decode("utf-8", "replace").rstrip())

    def send(self, message):
        line = json.dumps(message, separators=(",", ":"))
        if self.show:
            say("  to server  :", line)
        self.process.stdin.write(line.encode("utf-8") + b"\n")
        self.process.stdin.flush()

    def receive(self, wait_seconds=60):
        try:
            line = self.replies.get(timeout=wait_seconds)
        except queue.Empty:
            raise RuntimeError("no reply within " + str(wait_seconds) + " seconds")
        if line is None:
            raise RuntimeError("the server stopped without answering")
        if self.show:
            say("  from server:", line.decode("utf-8").rstrip())
        return json.loads(line)

    def request(self, message, wait_seconds=60):
        self.send(message)
        return self.receive(wait_seconds)

    def close(self, wait_seconds=30):
        # Closing the server's input is how an AI app says goodbye. The server then stops by itself.
        try:
            self.process.stdin.close()
        except OSError:
            pass
        try:
            return self.process.wait(timeout=wait_seconds)
        except subprocess.TimeoutExpired:
            self.process.kill()
            return self.process.wait()


def main(arguments):
    show = "--show" in arguments
    arguments = [argument for argument in arguments if argument != "--show"]
    if len(arguments) != 2:
        say('Usage: python -m tests.mcp_probe <user_id> "<question>" [--show]')
        return 2
    user_id, question = arguments

    sys.path.insert(0, str(PROJECT_ROOT))
    from src.issue_token import issue_token   # imported here so that "usage" works without the project's packages

    try:
        token = issue_token(user_id, 900)
    except (ValueError, RuntimeError) as error:
        say("Could not make a token:", error)
        return 1

    server = ServerProcess(token, show)
    try:
        hello = server.request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "mcp_probe", "version": "1"}}})
        server.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        details = hello["result"]["serverInfo"]
        say("Server       :", details["title"], details["version"], "(protocol", hello["result"]["protocolVersion"] + ")")

        listing = server.request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tool = listing["result"]["tools"][0]
        say("Tool offered :", tool["name"], "-", tool["description"].split(". ")[0] + ".")

        say("Asking as    :", user_id, "(the person comes from the token, not from the question)")
        say("Question     :", question)
        say("Waiting for the answer. A small model can need a minute or more.")
        started = time.time()
        reply = server.request({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
            "name": "ask_documents", "arguments": {"question": question}}}, ANSWER_WAIT_SECONDS)
        seconds = time.time() - started
        if "error" in reply:
            say("Protocol error:", reply["error"])
        else:
            result = reply["result"]
            say("Marked as    :", "an error" if result["isError"] else "an ordinary result")
            say("Answer       :")
            for line in result["content"][0]["text"].splitlines():
                say("    " + line)
        say("Took         :", round(seconds, 1), "seconds")
        if seconds > 50:
            say("Note: some AI apps give up on a tool after about a minute. This one took longer.")
    except RuntimeError as error:
        say("Problem:", error)
    finally:
        code = server.close()
    if server.notes:
        say("Server notes (standard error):")
        for note in server.notes:
            say("    " + note)
    say("Server stopped with exit code", code)
    return 0 if code == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
