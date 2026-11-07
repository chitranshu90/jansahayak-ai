(() => {
  const { api, escapeHtml } = window.App;
  let pending = false;

  function appendMessage(text, role, schemes = [], mode = null) {
    const container = document.getElementById("chat-messages");
    const message = document.createElement("div");
    message.className = `message ${role === "user" ? "user-message" : "assistant-message"}`;
    const paragraph = document.createElement("p");
    paragraph.textContent = text;
    message.append(paragraph);
    if (role === "assistant") {
      const speaker = document.createElement("button");
      speaker.className = "text-button speaker-button";
      speaker.type = "button";
      speaker.setAttribute("aria-label", "Read this answer aloud");
      speaker.textContent = window.I18n.t("readAloud");
      message.append(speaker);
    }
    if (mode) {
      const source = document.createElement("small");
      source.className = "response-mode";
      source.textContent = window.I18n.t("catalogueReply");
      message.append(source);
    }
    schemes.forEach((scheme) => {
      const button = document.createElement("button");
      button.className = "text-button";
      button.type = "button";
      button.dataset.openScheme = scheme.scheme_slug;
      button.textContent = `${window.I18n.t("viewScheme")} ${scheme.scheme_name} →`;
      message.append(button);
    });
    container.append(message);
    container.scrollTop = container.scrollHeight;
  }

  async function send(text) {
    if (pending || !text.trim()) return;
    pending = true;
    const input = document.getElementById("chat-input");
    const sendButton = document.getElementById("send-button");
    appendMessage(text.trim(), "user");
    input.value = "";
    sendButton.disabled = true;
    const messages = document.getElementById("chat-messages");
    const loading = document.createElement("div");
    loading.className = "message assistant-message typing";
    loading.innerHTML = `<span class="typing-label">${escapeHtml(window.I18n.t("thinking"))}</span><span class="typing-dots"><i></i><i></i><i></i></span>`;
    messages.append(loading);
    messages.scrollTop = messages.scrollHeight;
    try {
      const result = await api("/api/chat", {
        method: "POST",
        body: JSON.stringify({ message: text.trim(), language: document.getElementById("language").value })
      });
      loading.remove();
      localStorage.setItem(
        "jansahayak:recommended-schemes",
        JSON.stringify(result.schemes.map((scheme) => scheme.scheme_slug).slice(0, 5))
      );
      window.Schemes.refreshDashboard();
      appendMessage(result.answer, "assistant", result.schemes, result.mode);
    } catch (error) {
      loading.remove();
      appendMessage(`${window.I18n.t("requestError")} ${error.message}`, "assistant");
    } finally {
      pending = false;
      sendButton.disabled = false;
      input.focus();
    }
  }

  function setup() {
    document.getElementById("chat-form").addEventListener("submit", (event) => {
      event.preventDefault();
      send(document.getElementById("chat-input").value);
    });
    document.querySelector(".suggestions").addEventListener("click", (event) => {
      const button = event.target.closest("[data-prompt]");
      if (button) send(button.dataset.prompt);
    });
    document.getElementById("clear-chat").addEventListener("click", () => {
      document.getElementById("chat-messages").innerHTML =
        `<div class="message assistant-message"><p>${escapeHtml(window.I18n.t("cleared"))}</p></div>`;
    });
    document.getElementById("chat-messages").addEventListener("click", async (event) => {
      const button = event.target.closest("[data-open-scheme]");
      if (!button) return;
      try {
        await window.Schemes.open(button.dataset.openScheme);
      } catch (error) {
        appendMessage(error.message, "assistant");
      }
    });
  }

  window.Chat = { setup };
})();
