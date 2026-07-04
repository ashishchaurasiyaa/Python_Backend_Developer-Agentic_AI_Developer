// Minimal chat client. Talks to the FastAPI backend at /api/chat.

const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("composer");
const inputEl = document.getElementById("input");
const sendBtn = formEl.querySelector("button");
const statusEl = document.getElementById("status");

// Conversation history sent to the backend each turn (API is stateless).
const history = [];

// Show whether the backend has a real API key configured.
fetch("/api/health")
  .then((r) => r.json())
  .then((d) => {
    statusEl.textContent = d.live ? `live · ${d.model}` : "demo mode (no key)";
  })
  .catch(() => (statusEl.textContent = "offline"));

function addMessage(text, who) {
  const div = document.createElement("div");
  div.className = `msg msg--${who}`;
  const p = document.createElement("p");
  p.textContent = text;
  div.appendChild(p);
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

formEl.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = inputEl.value.trim();
  if (!message) return;

  addMessage(message, "user");
  inputEl.value = "";
  sendBtn.disabled = true;

  const typing = addMessage("…", "bot");
  typing.classList.add("msg--typing");

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history }),
    });
    const data = await res.json();
    typing.remove();
    addMessage(data.reply, "bot");

    // Keep the running history for the next turn.
    history.push({ role: "user", content: message });
    history.push({ role: "assistant", content: data.reply });
  } catch (err) {
    typing.remove();
    addMessage("Error talking to the server. Is it running?", "bot");
  } finally {
    sendBtn.disabled = false;
    inputEl.focus();
  }
});
