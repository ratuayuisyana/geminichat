const form = document.getElementById("chatForm");
const input = document.getElementById("messageInput");
const messagesEl = document.getElementById("messages");
const welcome = document.getElementById("welcome");
const sendBtn = document.getElementById("sendBtn");
let history = [];

function addMessage(role, text) {
  welcome.style.display = "none";
  const row = document.createElement("div");
  row.className = `message ${role === "user" ? "user" : "assistant"}`;
  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "user" ? "K" : "✦";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text; // textContent mencegah HTML dari jawaban dieksekusi.
  row.append(avatar, bubble);
  messagesEl.appendChild(row);
  messagesEl.parentElement.scrollTop = messagesEl.parentElement.scrollHeight;
  return row;
}

function setLoading(loading) {
  sendBtn.disabled = loading;
  input.disabled = loading;
  sendBtn.textContent = loading ? "…" : "➤";
}

async function sendMessage(text) {
  const message = text.trim();
  if (!message || sendBtn.disabled) return;
  addMessage("user", message);
  const priorHistory = history.slice();
  history.push({role: "user", text: message});
  input.value = "";
  input.style.height = "auto";
  setLoading(true);
  const typing = addMessage("assistant", "Gemini sedang berpikir...");
  typing.querySelector(".bubble").classList.add("typing");

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({message, history: priorHistory})
    });
    const data = await response.json();
    typing.remove();
    if (!response.ok) throw new Error(data.error || "Terjadi kesalahan.");
    addMessage("model", data.reply);
    history.push({role: "model", text: data.reply});
  } catch (error) {
    typing.remove();
    addMessage("model", `Maaf, ${error.message}`);
    // Pertahankan percakapan sebelumnya; pesan gagal tidak dimasukkan ke riwayat API.
    history.pop();
  } finally {
    setLoading(false);
    input.focus();
  }
}

form.addEventListener("submit", event => {
  event.preventDefault();
  sendMessage(input.value);
});

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 150) + "px";
});
input.addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

function newChat() {
  history = [];
  messagesEl.innerHTML = "";
  welcome.style.display = "block";
  input.value = "";
  input.focus();
}
document.getElementById("newChatBtn").addEventListener("click", newChat);
document.getElementById("mobileNewChat").addEventListener("click", newChat);
document.getElementById("clearBtn").addEventListener("click", newChat);
document.querySelectorAll(".suggestion").forEach(button => {
  button.addEventListener("click", () => sendMessage(button.dataset.prompt));
});
