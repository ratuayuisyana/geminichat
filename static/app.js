
const form = document.getElementById("chatForm");
const input = document.getElementById("messageInput");
const messagesEl = document.getElementById("messages");
const welcome = document.getElementById("welcome");
const sendBtn = document.getElementById("sendBtn");

const ragToggle = document.getElementById("ragToggle");
const fileInput = document.getElementById("fileInput");
const uploadBtn = document.getElementById("uploadBtn");
const kbStatus = document.getElementById("kbStatus");
const docList = document.getElementById("docList");

let history = [];

// ---------------- CHAT ----------------

function addMessage(role, text, sources = []) {
  if (welcome) welcome.style.display = "none";

  const row = document.createElement("div");
  row.className = `message ${
    role === "user" ? "user" : "assistant"
  }`;

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "user" ? "K" : "✦";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;

  if (sources.length) {
    bubble.appendChild(renderSources(sources));
  }

  row.append(avatar, bubble);
  messagesEl.appendChild(row);

  if (messagesEl.parentElement) {
    messagesEl.parentElement.scrollTop =
      messagesEl.parentElement.scrollHeight;
  }

  return row;
}

function renderSources(sources) {
  const details = document.createElement("details");
  details.className = "sources";

  const summary = document.createElement("summary");
  summary.textContent = `Sumber dokumen (${sources.length})`;

  details.appendChild(summary);

  sources.forEach((src, index) => {
    const item = document.createElement("div");
    item.className = "source-item";

    const title = document.createElement("strong");
    const page = src.page ? `, halaman ${src.page}` : "";

    title.textContent =
      `[${src.index || index + 1}] ${src.source || src.filename || "Dokumen"}${page}`;

    const score = document.createElement("span");
    score.className = "source-score";

    score.textContent =
      typeof src.score === "number"
        ? ` Kemiripan ${Math.round(src.score * 100)}%`
        : "";

    const snippet = document.createElement("p");
    snippet.textContent = src.snippet || src.text || "";

    item.append(title, score, snippet);
    details.appendChild(item);
  });

  return details;
}

function setLoading(loading) {
  if (sendBtn) {
    sendBtn.disabled = loading;
    sendBtn.textContent = loading ? "…" : "➤";
  }

  if (input) input.disabled = loading;
}

async function sendMessage(text) {
  const message = text.trim();

  if (!message || sendBtn.disabled) return;

  addMessage("user", message);

  const priorHistory = history.slice();

  history.push({
    role: "user",
    text: message
  });

  input.value = "";
  input.style.height = "auto";

  setLoading(true);

  const typing = addMessage(
    "assistant",
    "Gemini sedang membaca dan memproses pertanyaan..."
  );

  typing.querySelector(".bubble").classList.add("typing");

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        message: message,
        history: priorHistory,
        use_rag: ragToggle ? ragToggle.checked : true
      })
    });

    const data = await readServerResponse(response);

    typing.remove();

    if (!response.ok) {
      throw new Error(data.error || "Terjadi kesalahan pada server.");
    }

    addMessage(
      "model",
      data.reply || "Gemini tidak memberikan jawaban.",
      data.sources || []
    );

    history.push({
      role: "model",
      text: data.reply
    });

  } catch (error) {
    typing.remove();

    addMessage("model", `Maaf, ${error.message}`);

    history.pop();

    console.error("Chat error:", error);

  } finally {
    setLoading(false);
    input.focus();
  }
}

// Membaca respons server
async function readServerResponse(response) {
  const responseText = await response.text();

  try {
    return JSON.parse(responseText);
  } catch {
    console.error("Respons server bukan JSON:", responseText);

    throw new Error(
      `Respons server tidak valid. HTTP ${response.status}. Periksa terminal Flask.`
    );
  }
}

// Kirim pesan
form.addEventListener("submit", event => {
  event.preventDefault();
  sendMessage(input.value);
});

// Tinggi textarea
input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height =
    Math.min(input.scrollHeight, 150) + "px";
});

// Enter untuk mengirim
input.addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

// ---------------- CHAT BARU ----------------

function newChat() {
  history = [];

  messagesEl.innerHTML = "";

  if (welcome) welcome.style.display = "block";

  input.value = "";
  input.style.height = "auto";
  input.focus();
}

document.getElementById("newChatBtn")
  ?.addEventListener("click", newChat);

document.getElementById("mobileNewChat")
  ?.addEventListener("click", newChat);

document.getElementById("clearBtn")
  ?.addEventListener("click", newChat);

// Saran pertanyaan
document.querySelectorAll(".suggestion").forEach(button => {
  button.addEventListener("click", () => {
    sendMessage(button.dataset.prompt || "");
  });
});

// ---------------- BASIS PENGETAHUAN RAG ----------------

function setKbStatus(message, isError = false) {
  if (!kbStatus) return;

  kbStatus.textContent = message;
  kbStatus.classList.toggle("error", isError);
  kbStatus.hidden = false;
}

function renderDocuments(documents) {
  if (!docList) return;

  docList.innerHTML = "";

  if (!documents || documents.length === 0) {
    docList.hidden = true;
    return;
  }

  documents.forEach(doc => {
    const li = document.createElement("li");
    li.className = "doc-item";

    const name = document.createElement("span");
    name.textContent = `📄 ${doc.name}`;

    const info = document.createElement("small");
    info.textContent = `${doc.chunks || 0} bagian`;

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.textContent = "Hapus";
    removeBtn.className = "doc-delete";

    removeBtn.addEventListener("click", () => {
      deleteDocument(doc);
    });

    li.append(name, info, removeBtn);
    docList.appendChild(li);
  });

  docList.hidden = false;
}

// Memuat daftar dokumen
async function loadDocuments() {
  try {
    const response = await fetch("/api/rag/documents");

    const data = await readServerResponse(response);

    if (!response.ok) {
      throw new Error(data.error || "Gagal memuat dokumen.");
    }

    renderDocuments(data.documents || []);

    console.log("Daftar dokumen:", data.documents);

    return data.documents || [];

  } catch (error) {
    console.error("Gagal memuat daftar dokumen:", error);
    throw error;
  }
}

// Upload dokumen
async function uploadDocument(file) {
  if (!file) return;

  const allowedExtensions = [".pdf", ".txt", ".md"];

  const extension = "." + file.name.split(".").pop().toLowerCase();

  if (!allowedExtensions.includes(extension)) {
    alert("Format file harus PDF, TXT, atau MD.");
    fileInput.value = "";
    return;
  }

  const formData = new FormData();
  formData.append("file", file);

  uploadBtn.disabled = true;
  uploadBtn.textContent = "Memproses...";

  setKbStatus(`Sedang membaca ${file.name}...`);

  console.log("Mulai upload:", file.name);

  try {
    const response = await fetch("/api/rag/upload", {
      method: "POST",
      body: formData
    });

    const data = await readServerResponse(response);

    console.log("Respons upload:", data);
    console.log("Status HTTP:", response.status);

    if (!response.ok) {
      throw new Error(
        data.error || "Gagal mengunggah dokumen."
      );
    }

    await loadDocuments();

    setKbStatus(
      `Dokumen ${file.name} berhasil ditambahkan ke basis pengetahuan.`
    );

    console.log("Dokumen berhasil diunggah:", file.name);

  } catch (error) {
    setKbStatus(error.message, true);

    console.error("Upload dokumen gagal:", error);

    alert("Upload gagal: " + error.message);

  } finally {
    uploadBtn.disabled = false;
    uploadBtn.textContent = "＋ Unggah dokumen";
    fileInput.value = "";
  }
}

// Hapus dokumen
async function deleteDocument(doc) {
  const confirmed = confirm(
    `Apakah kamu yakin ingin menghapus ${doc.name}?`
  );

  if (!confirmed) return;

  try {
    const response = await fetch(
      `/api/rag/documents/${encodeURIComponent(doc.id)}`,
      {
        method: "DELETE"
      }
    );

    const data = await readServerResponse(response);

    if (!response.ok) {
      throw new Error(data.error || "Gagal menghapus dokumen.");
    }

    await loadDocuments();

    setKbStatus("Dokumen berhasil dihapus.");

  } catch (error) {
    console.error("Hapus dokumen gagal:", error);
    alert(error.message);
  }
}

// ---------------- EVENT UPLOAD ----------------

if (uploadBtn && fileInput) {
  uploadBtn.addEventListener("click", () => {
    fileInput.click();
  });

  fileInput.addEventListener("change", event => {
    const file = event.target.files?.[0];

    if (file) {
      uploadDocument(file);
    }
  });

} else {
  console.error(
    "Tombol upload atau input file tidak ditemukan. Periksa index.html."
  );
}

// Memuat dokumen saat halaman dibuka
loadDocuments().catch(error => {
  console.error("Inisialisasi daftar dokumen gagal:", error);
});
