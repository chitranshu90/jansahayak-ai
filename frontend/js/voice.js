(() => {
  let recognition = null;
  let speaking = false;

  function setup() {
    const button = document.getElementById("mic-button");
    const status = document.getElementById("voice-status");
    const stopButton = document.getElementById("stop-speech");
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      button.disabled = true;
      status.textContent = window.I18n.current() === "hi"
        ? "इस ब्राउज़र में बोलकर पूछने की सुविधा नहीं है। कृपया सवाल लिखें।"
        : "Voice input is not supported here. You can type your question instead.";
    } else {
      recognition = new SpeechRecognition();
      recognition.lang = document.getElementById("language").value === "hi" ? "hi-IN" : "en-IN";
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;
      recognition.onstart = () => {
        button.classList.add("listening");
        status.textContent = window.I18n.current() === "hi"
          ? "सुन रहे हैं… बोलें, फिर पहचाने गए शब्द जाँचें।"
          : "Listening… speak now, then review the recognized text.";
      };
      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        document.getElementById("chat-input").value = transcript;
        status.textContent = window.I18n.current() === "hi"
          ? "आवाज़ से शब्द पहचाने गए। भेजने से पहले उन्हें जाँचें या बदलें।"
          : "Voice recognized. Review or edit the text before sending.";
      };
      recognition.onerror = (event) => {
        status.textContent = event.error === "not-allowed"
          ? (window.I18n.current() === "hi"
            ? "माइक्रोफ़ोन की अनुमति नहीं मिली। ब्राउज़र सेटिंग में अनुमति दें या सवाल लिखें।"
            : "Microphone permission was denied. Allow it in your browser settings or type your question.")
          : window.I18n.current() === "hi"
            ? `आवाज़ पहचान में समस्या हुई (${event.error})। कृपया सवाल लिखकर फिर कोशिश करें।`
            : `Voice recognition failed (${event.error}). Please type your question and try again.`;
      };
      recognition.onend = () => button.classList.remove("listening");
      button.addEventListener("click", () => {
        if (button.classList.contains("listening")) {
          recognition.stop();
          return;
        }
        recognition.lang = document.getElementById("language").value === "hi" ? "hi-IN" : "en-IN";
        try {
          recognition.start();
        } catch (_error) {
          status.textContent = window.I18n.current() === "hi"
            ? "आवाज़ पहचान शुरू नहीं हो सकी। कृपया सवाल लिखें।"
            : "Voice recognition could not start. Please type your question.";
        }
      });
    }

    document.getElementById("language").addEventListener("change", (event) => {
      if (recognition) recognition.lang = event.target.value === "hi" ? "hi-IN" : "en-IN";
    });
    document.addEventListener("languagechange", () => {
      if (recognition) recognition.lang = window.I18n.current() === "hi" ? "hi-IN" : "en-IN";
      if (!button.classList.contains("listening")) {
        status.textContent = window.I18n.current() === "hi"
          ? SpeechRecognition
            ? "माइक्रोफ़ोन बटन दबाकर हिंदी में बोलें; भेजने से पहले लिखे शब्द जाँचें।"
            : "इस ब्राउज़र में बोलकर पूछने की सुविधा नहीं है। कृपया सवाल लिखें।"
          : SpeechRecognition
            ? "Voice input depends on browser support and microphone permission."
            : "Voice input is not supported here. You can type your question instead.";
      }
    });
    document.getElementById("chat-messages").addEventListener("click", (event) => {
      if (!event.target.closest(".speaker-button")) return;
      const message = event.target.closest(".assistant-message");
      if (!message || !("speechSynthesis" in window)) return;
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(message.innerText);
      utterance.lang = document.getElementById("language").value === "hi" ? "hi-IN" : "en-IN";
      utterance.onstart = () => {
        speaking = true;
        stopButton.disabled = false;
      };
      utterance.onend = utterance.onerror = () => {
        speaking = false;
        stopButton.disabled = true;
      };
      window.speechSynthesis.speak(utterance);
    });
    stopButton.addEventListener("click", () => {
      if (speaking) window.speechSynthesis.cancel();
      speaking = false;
      stopButton.disabled = true;
    });
  }

  window.Voice = { setup };
})();
