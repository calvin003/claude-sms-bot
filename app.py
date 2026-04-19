from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import anthropic
import sqlite3
import os

app = Flask(__name__)
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are cslvin's personal AI assistant, accessible via SMS.
You are helpful, smart, and friendly. You remember the conversation history.
Since you're responding over SMS, keep replies concise unless the user asks for something detailed.
If the user asks you to write an essay, draft, or long document, write the full thing — don't truncate.
You can help with anything: questions, scholarship applications, essay writing,
research, advice, planning, reminders, and general tasks.
If the user says 'clear' or 'reset', let them know their history has been cleared."""

DB_PATH = os.path.join(os.path.dirname(__file__), "conversations.db")

def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()
    db.close()

def get_history(phone, limit=20):
    db = sqlite3.connect(DB_PATH)
    rows = db.execute(
        "SELECT role, content FROM messages WHERE phone = ? ORDER BY timestamp DESC LIMIT ?",
        (phone, limit)
    ).fetchall()
    db.close()
    return [{"role": row[0], "content": row[1]} for row in reversed(rows)]

def save_message(phone, role, content):
    db = sqlite3.connect(DB_PATH)
    db.execute(
        "INSERT INTO messages (phone, role, content) VALUES (?, ?, ?)",
        (phone, role, content)
    )
    db.commit()
    db.close()

def clear_history(phone):
    db = sqlite3.connect(DB_PATH)
    db.execute("DELETE FROM messages WHERE phone = ?", (phone,))
    db.commit()
    db.close()

@app.route("/sms", methods=["POST"])
def sms_reply():
    incoming_msg = request.form.get("Body", "").strip()
    from_number = request.form.get("From", "")

    resp = MessagingResponse()

    if incoming_msg.lower() in ["clear", "reset", "/clear", "/reset"]:
        clear_history(from_number)
        resp.message("Chat history cleared. Fresh start!")
        return str(resp)

    save_message(from_number, "user", incoming_msg)
    history = get_history(from_number)

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=history
        )
        reply = response.content[0].text
    except Exception as e:
        reply = f"Sorry, something went wrong: {str(e)}"

    save_message(from_number, "assistant", reply)
    resp.message(reply)
    return str(resp)

@app.route("/", methods=["GET"])
def health():
    return "Claude SMS Bot is running!", 200

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

init_db()
