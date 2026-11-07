(() => {
  const { api } = window.App;
  const t = (key) => window.I18n.t(key);
  const applicationStatuses = [
    "Application Submitted",
    "Under Verification",
    "Approved",
    "Rejected"
  ];

  function showText(container, text, className = "tool-message") {
    container.replaceChildren();
    const paragraph = document.createElement("p");
    paragraph.className = className;
    paragraph.textContent = text;
    container.append(paragraph);
  }

  function addCopyableDraft(container, draft) {
    container.replaceChildren();
    const notice = document.createElement("p");
    notice.className = "tool-note";
    notice.textContent = draft.notice;
    const questions = document.createElement("ul");
    draft.clarifying_questions.forEach((question) => {
      const item = document.createElement("li");
      item.textContent = question;
      questions.append(item);
    });
    const text = document.createElement("textarea");
    text.readOnly = true;
    text.rows = 10;
    text.value = `${draft.subject}\n\n${draft.draft}`;
    const copy = document.createElement("button");
    copy.className = "button button-secondary";
    copy.type = "button";
    copy.textContent = t("copyDraft");
    copy.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(text.value);
        copy.textContent = t("copiedDraft");
      } catch (error) {
        copy.textContent = t("copyFailed");
      }
    });
    container.append(notice, questions, text, copy);
  }

  async function loadApplications(schemeNames) {
    const list = document.getElementById("application-list");
    try {
      const { applications } = await api("/api/applications");
      list.replaceChildren();
      if (!applications.length) {
        showText(list, t("noApplications"));
        return;
      }
      applications.forEach((application) => {
        const item = document.createElement("article");
        item.className = "dashboard-item";
        const title = document.createElement("strong");
        title.textContent = schemeNames.get(application.scheme_slug) || application.scheme_slug;
        const history = document.createElement("small");
        history.textContent = `${application.history.length} ${t("statusUpdates")}`;
        const status = document.createElement("select");
        status.setAttribute("aria-label", t("updateApplicationStatus"));
        applicationStatuses.forEach((value) => {
          const option = document.createElement("option");
          option.value = value;
          option.textContent = t(`applicationStatus${value.replaceAll(" ", "")}`);
          status.append(option);
        });
        status.value = application.status;
        status.addEventListener("change", async () => {
          status.disabled = true;
          try {
            await api("/api/applications", {
              method: "POST",
              body: JSON.stringify({ application_id: application.id, status: status.value })
            });
            await loadApplications(schemeNames);
          } catch (error) {
            showText(list, `${t("requestError")} ${error.message}`);
          } finally {
            status.disabled = false;
          }
        });
        item.append(title, history, status);
        list.append(item);
      });
    } catch (error) {
      showText(list, `${t("requestError")} ${error.message}`);
    }
  }

  async function setup() {
    const schemeNames = new Map();
    const schemeSelect = document.getElementById("application-scheme");
    try {
      const { schemes } = await api("/api/schemes");
      schemeSelect.replaceChildren();
      schemes.forEach((scheme) => {
        schemeNames.set(scheme.scheme_slug, scheme.scheme_name);
        const option = document.createElement("option");
        option.value = scheme.scheme_slug;
        option.textContent = scheme.scheme_name;
        schemeSelect.append(option);
      });
    } catch (error) {
      showText(document.getElementById("application-list"), `${t("requestError")} ${error.message}`);
    }
    await loadApplications(schemeNames);

    document.getElementById("application-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = event.currentTarget.querySelector("button[type=submit]");
      button.disabled = true;
      try {
        await api("/api/applications", {
          method: "POST",
          body: JSON.stringify({
            scheme_slug: schemeSelect.value,
            status: document.getElementById("application-status").value
          })
        });
        await loadApplications(schemeNames);
        event.currentTarget.reset();
      } catch (error) {
        showText(document.getElementById("application-list"), `${t("requestError")} ${error.message}`);
      } finally {
        button.disabled = false;
      }
    });

    document.getElementById("complaint-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const output = document.getElementById("complaint-result");
      showText(output, t("generatingDraft"));
      try {
        const result = await api("/api/complaints/generate", {
          method: "POST",
          body: JSON.stringify({
            topic: form.elements.topic.value,
            message: form.elements.message.value,
            language: window.I18n.current()
          })
        });
        addCopyableDraft(output, result);
      } catch (error) {
        showText(output, `${t("requestError")} ${error.message}`);
      }
    });

    document.getElementById("fraud-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const output = document.getElementById("fraud-result");
      showText(output, t("checkingLink"));
      try {
        const result = await api("/api/fraud/check", {
          method: "POST",
          body: JSON.stringify({ url: form.elements.url.value, message: form.elements.message.value })
        });
        const category = document.createElement("strong");
        category.textContent = t(`fraudCategory${result.category.replaceAll(" ", "")}`);
        const host = document.createElement("p");
        host.textContent = result.host || t("hostUnavailable");
        const signalList = document.createElement("ul");
        result.signals.forEach((signal) => {
          const item = document.createElement("li");
          item.textContent = signal;
          signalList.append(item);
        });
        const notice = document.createElement("p");
        notice.className = "tool-note";
        notice.textContent = result.notice;
        output.replaceChildren(category, host, signalList, notice);
      } catch (error) {
        showText(output, `${t("requestError")} ${error.message}`);
      }
    });

    document.getElementById("document-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const output = document.getElementById("document-result");
      showText(output, t("checkingDocument"));
      try {
        const result = await api("/api/documents/analyze", {
          method: "POST",
          body: new FormData(form)
        });
        const analysis = result.analysis;
        showText(
          output,
          `${analysis.document_type} · ${analysis.size_bytes} bytes. ${analysis.message}`
        );
        form.reset();
      } catch (error) {
        showText(output, `${t("requestError")} ${error.message}`);
      }
    });

    document.addEventListener("languagechange", () => loadApplications(schemeNames));
  }

  window.Tools = { setup };
})();
