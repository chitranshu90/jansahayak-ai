(() => {
  let schemes = [];
  let activeScheme = null;
  let dashboardSchemes = null;
  const compareSelection = new Set();
  const { api, escapeHtml } = window.App;
  const t = (key) => window.I18n.t(key);
  const ruleLabel = (rule) => window.I18n.current() === "hi"
    ? rule.name_hi || rule.name
    : rule.name;

  function card(scheme) {
    const status = scheme.verification_status === "verified" ? "verified" : "";
    const label = scheme.verification_status === "verified" ? t("verified") : t("partial");
    const saved = readChecklist("jansahayak:saved-schemes").includes(scheme.scheme_slug);
    const selected = compareSelection.has(scheme.scheme_slug);
    return `<article class="scheme-card">
      <div class="scheme-card-top"><span class="scheme-category">${escapeHtml(window.I18n.category(scheme.category))}</span><span class="verification-badge ${status}">${label}</span></div>
      <h3>${escapeHtml(scheme.scheme_name)}</h3>
      <p>${escapeHtml(window.I18n.current() === "hi" ? scheme.description_hi : scheme.description)}</p>
      <div class="scheme-card-bottom"><span class="target-label">${escapeHtml(window.I18n.current() === "hi" ? scheme.target_beneficiaries_hi : scheme.target_beneficiaries)}</span><div class="scheme-card-actions"><label class="scheme-compare"><input type="checkbox" data-compare-scheme="${escapeHtml(scheme.scheme_slug)}" ${selected ? "checked" : ""}>${t("compare")}</label><button class="text-button" type="button" data-save-scheme="${escapeHtml(scheme.scheme_slug)}">${saved ? t("savedScheme") : t("saveScheme")}</button><button class="text-button" type="button" data-open-scheme="${escapeHtml(scheme.scheme_slug)}">${t("viewDetails")}</button></div></div>
    </article>`;
  }

  function updateCompareControls() {
    const count = compareSelection.size;
    document.getElementById("compare-count").textContent =
      `${count} ${t("selectedSchemes")} · ${t("compareHint")}`;
    document.getElementById("compare-button").disabled = count < 2 || count > 3;
  }

  async function refreshDashboard() {
    const savedList = document.getElementById("saved-schemes");
    const recommendedList = document.getElementById("recommended-schemes");
    const recentList = document.getElementById("recent-schemes");
    const summary = document.getElementById("readiness-summary");
    try {
      if (!dashboardSchemes) {
        const { schemes: allSchemes } = await api("/api/schemes");
        dashboardSchemes = allSchemes;
      }
      const bySlug = new Map(dashboardSchemes.map((scheme) => [scheme.scheme_slug, scheme]));
      const saved = readChecklist("jansahayak:saved-schemes");
      const recommended = readChecklist("jansahayak:recommended-schemes");
      const recent = readChecklist("jansahayak:recent-schemes");
      const renderLinks = (container, slugs, emptyText, canRemove) => {
        container.innerHTML = "";
        const found = slugs.map((slug) => bySlug.get(slug)).filter(Boolean);
        if (!found.length) {
          container.textContent = emptyText;
          return;
        }
        found.forEach((scheme) => {
          const item = document.createElement("div");
          item.className = "dashboard-item";
          item.innerHTML = `<strong>${escapeHtml(scheme.scheme_name)}</strong><button class="text-button" type="button" data-open-scheme="${escapeHtml(scheme.scheme_slug)}">${t("viewDetails")}</button>${canRemove ? `<button class="text-button" type="button" data-remove-saved="${escapeHtml(scheme.scheme_slug)}">${t("removeSaved")}</button>` : ""}`;
          container.append(item);
        });
      };
      renderLinks(savedList, saved, t("noSavedSchemes"), true);
      renderLinks(recommendedList, recommended, t("noRecommendedSchemes"), false);
      renderLinks(recentList, recent.slice(0, 5), t("noRecentSchemes"), false);
      const lastCheck = readChecklist("jansahayak:eligibility:last")[0];
      const eligibilitySummary = lastCheck
        ? `${t("lastEligibility")}: ${bySlug.get(lastCheck.slug)?.scheme_name || lastCheck.slug} · ${t(`overall_${lastCheck.status}`)}`
        : t("noEligibilitySummary");
      const missingDocumentCount = dashboardSchemes.filter((scheme) => !scheme.required_documents.length).length;
      summary.textContent = `${eligibilitySummary} · ${missingDocumentCount} ${t("schemesWithoutDocuments")}`;
    } catch (error) {
      savedList.textContent = error.message;
      recommendedList.textContent = error.message;
      recentList.textContent = error.message;
      summary.textContent = error.message;
    }
  }

  async function load(filters = {}) {
    const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value));
    const data = await api(`/api/schemes?${query}`);
    schemes = data.schemes;
    if (!Object.values(filters).some(Boolean)) dashboardSchemes = schemes;
    document.getElementById("scheme-results").innerHTML = schemes.map(card).join("");
    document.getElementById("scheme-empty").hidden = schemes.length > 0;
    document.getElementById("catalogue-count").textContent = window.I18n.current() === "hi"
      ? `${data.count} ${data.count === 1 ? "योजना" : "योजनाएँ"} सूची में`
      : `${data.count} ${data.count === 1 ? "scheme" : "schemes"} in starter catalogue`;
    updateCompareControls();
    refreshDashboard();
  }

  function list(items, fallback) {
    return items.length
      ? `<ul class="detail-list">${items.map((item) => `<li>${escapeHtml(typeof item === "string" ? item : item.label || item.name || JSON.stringify(item))}</li>`).join("")}</ul>`
      : `<p class="detail-copy">${fallback}</p>`;
  }

  function eligibilityMarkup(scheme) {
    if (!scheme.eligibility_rules.length) {
      return `<p class="detail-copy">${t("noEligibility")}</p>`;
    }
    const fields = scheme.eligibility_rules.map((rule) => {
      let control;
      if (rule.operator === "boolean") {
        control = `<select name="${escapeHtml(rule.key)}"><option value="">${t("select")}</option><option value="true">${t("yes")}</option><option value="false">${t("no")}</option></select>`;
      } else if (rule.operator === "one_of") {
        control = `<select name="${escapeHtml(rule.key)}"><option value="">${t("select")}</option>${rule.value.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(window.I18n.current() === "hi" && value === "post-matric" ? "मैट्रिक के बाद" : window.I18n.current() === "hi" && value === "post-secondary" ? "माध्यमिक के बाद" : value)}</option>`).join("")}</select>`;
      } else if (rule.key === "social_category") {
        control = `<select name="${escapeHtml(rule.key)}"><option value="">${t("select")}</option><option value="SC">${t("scheduledCaste")}</option><option value="Other">${t("otherCategory")}</option></select>`;
      } else if (rule.key === "study_country") {
        control = `<select name="${escapeHtml(rule.key)}"><option value="">${t("select")}</option><option value="India">${t("india")}</option><option value="Other">${t("outsideIndia")}</option></select>`;
      } else if (["gte", "lte"].includes(rule.operator)) {
        control = `<input name="${escapeHtml(rule.key)}" type="number" step="any">`;
      } else {
        control = `<input name="${escapeHtml(rule.key)}" type="text" maxlength="80">`;
      }
      return `<label>${escapeHtml(ruleLabel(rule))}${control}</label>`;
    }).join("");
    return `<form id="eligibility-form" class="eligibility-form">${fields}<button class="button button-primary" type="submit">${t("checkConditions")}</button></form><div id="assessment-result" aria-live="polite"></div>`;
  }

  function readChecklist(key) {
    try {
      const value = JSON.parse(localStorage.getItem(key) || "[]");
      return Array.isArray(value) ? value : [];
    } catch (error) {
      if (error instanceof SyntaxError) return [];
      throw error;
    }
  }

  function documentChecklist(scheme) {
    const savedKey = `jansahayak:documents:${scheme.scheme_slug}`;
    const customDocuments = readChecklist(savedKey);
    const requiredDocuments = scheme.required_documents.map((document, index) => {
      const name = typeof document === "string" ? document : document.label || document.name;
      return { id: `official-${index}`, name, source: "official" };
    });
    const documents = [...requiredDocuments, ...customDocuments];
    const list = documents.length
      ? `<div class="readiness-list">${documents.map((document) => {
          const key = `${scheme.scheme_slug}:${document.id}`;
          const ready = localStorage.getItem(key) === "ready";
          return `<label class="readiness-item"><input type="checkbox" data-document-key="${escapeHtml(key)}" ${ready ? "checked" : ""}><span>${escapeHtml(document.name)}</span>${document.source === "custom" ? `<button type="button" class="remove-document" data-remove-document="${escapeHtml(document.id)}" aria-label="${t("removeDocument")}">×</button>` : ""}</label>`;
        }).join("")}</div>`
      : `<p class="detail-copy">${t("noDocuments")}</p>`;
    const readyCount = documents.filter((document) =>
      localStorage.getItem(`${scheme.scheme_slug}:${document.id}`) === "ready"
    ).length;
    return `
      <p class="detail-copy">${t("checklistPrivacy")}</p>
      <p class="checklist-progress" id="document-progress">${readyCount}/${documents.length} ${t("documentsReady")}</p>
      ${list}
      <form id="document-add-form" class="document-add-form">
        <label for="document-name">${t("addDocumentLabel")}</label>
        <div><input id="document-name" name="document_name" type="text" maxlength="80" autocomplete="off" placeholder="${t("documentPlaceholder")}"><button class="button button-secondary" type="submit">${t("addDocument")}</button></div>
        <small>${t("addDocumentHint")}</small>
      </form>`;
  }

  function nextStepChecklist(scheme) {
    const storedKey = `jansahayak:steps:${scheme.scheme_slug}`;
    const checked = new Set(readChecklist(storedKey));
    const preparationSteps = [
      { id: "eligibility", label: t("stepEligibility") },
      { id: "documents", label: t("stepDocuments") },
      { id: "dates", label: t("stepDates") },
      { id: "apply", label: t("stepApply") }
    ];
    const officialSteps = scheme.application_steps.length
      ? list(scheme.application_steps, "")
      : `<p class="detail-copy">${t("noSteps")}</p>`;
    return `
      ${officialSteps}
      <p class="planner-note">${t("plannerDisclaimer")}</p>
      <div class="planner-list">${preparationSteps.map((step) => `
        <label class="readiness-item"><input type="checkbox" data-step-id="${step.id}" ${checked.has(step.id) ? "checked" : ""}><span>${step.label}</span></label>
      `).join("")}</div>`;
  }

  async function open(slug) {
    const data = await api(`/api/schemes/${encodeURIComponent(slug)}`);
    activeScheme = data.scheme;
    const scheme = activeScheme;
    const recent = readChecklist("jansahayak:recent-schemes").filter((item) => item !== slug);
    localStorage.setItem("jansahayak:recent-schemes", JSON.stringify([slug, ...recent].slice(0, 5)));
    refreshDashboard();
    const details = document.getElementById("scheme-detail");
    const verificationLabel = scheme.verification_status === "verified" ? t("verified") : t("partial");
    details.innerHTML = `
      <span class="scheme-category">${escapeHtml(window.I18n.category(scheme.category))} · ${escapeHtml(window.I18n.current() === "hi" && scheme.government_level === "Central" ? t("central") : window.I18n.current() === "hi" && scheme.government_level === "State" ? t("state") : scheme.government_level)}</span>
      <h2 id="dialog-title" class="detail-title">${escapeHtml(scheme.scheme_name)}</h2>
      <p class="detail-copy">${escapeHtml(window.I18n.current() === "hi" ? scheme.description_hi : scheme.description)}</p>
      <p class="detail-meta">${t("infoChecked")}: ${escapeHtml(scheme.last_verified_date)} · ${verificationLabel} ${t("status")}</p>
      <section class="detail-block"><h3>${t("targetGroup")}</h3><p class="detail-copy">${escapeHtml(window.I18n.current() === "hi" ? scheme.target_beneficiaries_hi || scheme.target_beneficiaries : scheme.target_beneficiaries)}</p></section>
      <section class="detail-block"><h3>${t("benefits")}</h3><p class="detail-copy">${escapeHtml(window.I18n.current() === "hi" ? scheme.benefits_hi : scheme.benefits)}</p></section>
      <section class="detail-block"><h3>${t("eligibility")}</h3>${eligibilityMarkup(scheme)}</section>
      <section class="detail-block"><h3>${t("documentReadiness")}</h3>${documentChecklist(scheme)}</section>
      <section class="detail-block"><h3>${t("nextSteps")}</h3>${nextStepChecklist(scheme)}</section>
      <div class="detail-actions"><a class="detail-source" href="${escapeHtml(scheme.official_source_url)}" target="_blank" rel="noopener noreferrer">${t("openSource")}</a><button type="button" class="text-button" data-refresh-source="${escapeHtml(scheme.scheme_slug)}">${t("refreshOfficialSource")}</button>${scheme.official_application_url ? `<a class="detail-source" href="${escapeHtml(scheme.official_application_url)}" target="_blank" rel="noopener noreferrer">${t("openApplication")}</a>` : ""}</div><div id="live-source-result" class="live-source-result" aria-live="polite"></div>`;
    const dialog = document.getElementById("scheme-dialog");
    if (!dialog.open) dialog.showModal();
  }

  async function compareSelected() {
    const output = document.getElementById("comparison-result");
    const query = new URLSearchParams();
    compareSelection.forEach((slug) => query.append("slug", slug));
    output.textContent = t("loadingComparison");
    try {
      const { schemes: selected } = await api(`/api/schemes/compare?${query}`);
      const hindi = window.I18n.current() === "hi";
      const rows = [
        [t("compareName"), (scheme) => scheme.scheme_name],
        [t("benefits"), (scheme) => hindi ? scheme.benefits_hi : scheme.benefits],
        [t("eligibility"), (scheme) => scheme.eligibility_rules.length
          ? scheme.eligibility_rules.map((rule) => hindi ? rule.name_hi || rule.name : rule.name).join(", ")
          : t("noEligibility")],
        [t("documentReadiness"), (scheme) => scheme.required_documents.length
          ? scheme.required_documents.map((item) => typeof item === "string" ? item : item.label || item.name).join(", ")
          : t("noDocuments")],
        [t("applicationStepsLabel"), (scheme) => scheme.application_steps.length
          ? scheme.application_steps.join("; ")
          : t("noSteps")],
        [t("compareVerification"), (scheme) => `${scheme.last_verified_date} · ${scheme.verification_status}`],
        [t("openSource"), (scheme) => `<a href="${escapeHtml(scheme.official_source_url)}" target="_blank" rel="noopener noreferrer">${t("openSource")}</a>`]
      ];
      output.innerHTML = `<div class="table-scroll"><table class="comparison-table"><thead><tr><th></th>${selected.map((scheme) => `<th><h3>${escapeHtml(scheme.scheme_name)}</h3></th>`).join("")}</tr></thead><tbody>${rows.map(([label, value], index) => `<tr><th>${escapeHtml(label)}</th>${selected.map((scheme) => `<td>${index === rows.length - 1 ? value(scheme) : escapeHtml(value(scheme))}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
      document.getElementById("compare-dialog").showModal();
    } catch (error) {
      output.textContent = `${t("requestError")} ${error.message}`;
      document.getElementById("compare-dialog").showModal();
    }
  }

  function setup() {
    document.addEventListener("languagechange", () => {
      load({
        q: document.getElementById("scheme-query").value.trim(),
        target: document.getElementById("target-filter").value.trim(),
        category: document.getElementById("category-filter").value,
        government_level: document.getElementById("level-filter").value
      }).catch((error) => {
        document.getElementById("scheme-results").innerHTML =
          `<p class="empty-state">${escapeHtml(error.message)}</p>`;
      });
      if (activeScheme && document.getElementById("scheme-dialog").open) {
        open(activeScheme.scheme_slug).catch((error) => {
          document.getElementById("scheme-detail").textContent = error.message;
        });
      }
    });
    document.getElementById("scheme-search").addEventListener("submit", async (event) => {
      event.preventDefault();
      await load({
        q: document.getElementById("scheme-query").value.trim(),
        target: document.getElementById("target-filter").value.trim(),
        category: document.getElementById("category-filter").value,
        government_level: document.getElementById("level-filter").value
      });
    });
    document.getElementById("scheme-query").addEventListener("input", async (event) => {
      if (!event.target.value) await load({
        target: document.getElementById("target-filter").value.trim(),
        category: document.getElementById("category-filter").value,
        government_level: document.getElementById("level-filter").value
      });
    });
    document.getElementById("category-grid").addEventListener("click", async (event) => {
      const button = event.target.closest("[data-category]");
      if (!button) return;
      document.getElementById("category-filter").value = button.dataset.category;
      await load({
        target: document.getElementById("target-filter").value.trim(),
        category: button.dataset.category,
        government_level: document.getElementById("level-filter").value
      });
      location.hash = "explore";
    });
    document.getElementById("target-filter").addEventListener("input", async (event) => {
      await load({
        q: document.getElementById("scheme-query").value.trim(),
        target: event.target.value.trim(),
        category: document.getElementById("category-filter").value,
        government_level: document.getElementById("level-filter").value
      });
    });
    document.getElementById("scheme-results").addEventListener("click", async (event) => {
      const button = event.target.closest("[data-open-scheme]");
      if (button) await open(button.dataset.openScheme);
      const saveButton = event.target.closest("[data-save-scheme]");
      if (saveButton) {
        const saved = readChecklist("jansahayak:saved-schemes");
        const slug = saveButton.dataset.saveScheme;
        const updated = saved.includes(slug) ? saved.filter((item) => item !== slug) : [...saved, slug];
        localStorage.setItem("jansahayak:saved-schemes", JSON.stringify(updated));
        await load({
          q: document.getElementById("scheme-query").value.trim(),
          target: document.getElementById("target-filter").value.trim(),
          category: document.getElementById("category-filter").value,
          government_level: document.getElementById("level-filter").value
        });
      }
    });
    document.getElementById("scheme-results").addEventListener("change", (event) => {
      if (!event.target.matches("[data-compare-scheme]")) return;
      const slug = event.target.dataset.compareScheme;
      if (event.target.checked) {
        if (compareSelection.size >= 3) {
          event.target.checked = false;
          return;
        }
        compareSelection.add(slug);
      } else {
        compareSelection.delete(slug);
      }
      updateCompareControls();
    });
    document.getElementById("compare-button").addEventListener("click", compareSelected);
    document.getElementById("close-compare").addEventListener("click", () => document.getElementById("compare-dialog").close());
    document.getElementById("compare-dialog").addEventListener("click", (event) => {
      if (event.target === event.currentTarget) event.currentTarget.close();
    });
    document.getElementById("dashboard").addEventListener("click", async (event) => {
      const openButton = event.target.closest("[data-open-scheme]");
      if (openButton) await open(openButton.dataset.openScheme);
      const removeButton = event.target.closest("[data-remove-saved]");
      if (removeButton) {
        const saved = readChecklist("jansahayak:saved-schemes");
        localStorage.setItem("jansahayak:saved-schemes", JSON.stringify(
          saved.filter((slug) => slug !== removeButton.dataset.removeSaved)
        ));
        refreshDashboard();
        await load({
          q: document.getElementById("scheme-query").value.trim(),
          target: document.getElementById("target-filter").value.trim(),
          category: document.getElementById("category-filter").value,
          government_level: document.getElementById("level-filter").value
        });
      }
    });
    document.getElementById("close-dialog").addEventListener("click", () => document.getElementById("scheme-dialog").close());
    document.getElementById("scheme-dialog").addEventListener("click", (event) => {
      if (event.target === event.currentTarget) event.currentTarget.close();
    });
    document.getElementById("scheme-detail").addEventListener("change", (event) => {
      if (event.target.matches("[data-document-key]")) {
        const key = event.target.dataset.documentKey;
        if (event.target.checked) localStorage.setItem(key, "ready");
        else localStorage.removeItem(key);
        const checkboxes = [...document.querySelectorAll("[data-document-key]")];
        const ready = checkboxes.filter((checkbox) => checkbox.checked).length;
        const progress = document.getElementById("document-progress");
        if (progress) progress.textContent = `${ready}/${checkboxes.length} ${t("documentsReady")}`;
      }
      if (event.target.matches("[data-step-id]")) {
        const storedKey = `jansahayak:steps:${activeScheme.scheme_slug}`;
        const checked = new Set(readChecklist(storedKey));
        if (event.target.checked) checked.add(event.target.dataset.stepId);
        else checked.delete(event.target.dataset.stepId);
        localStorage.setItem(storedKey, JSON.stringify([...checked]));
      }
    });
    document.getElementById("scheme-detail").addEventListener("click", (event) => {
      const sourceButton = event.target.closest("[data-refresh-source]");
      if (sourceButton) {
        const output = document.getElementById("live-source-result");
        sourceButton.disabled = true;
        output.textContent = t("checkingOfficialSource");
        api(`/api/schemes/${encodeURIComponent(sourceButton.dataset.refreshSource)}/source`)
          .then((result) => {
            output.replaceChildren();
            const title = document.createElement("strong");
            title.textContent = result.page_title || t("officialPage");
            const checked = document.createElement("small");
            checked.textContent = `${result.checked_at} · ${result.source_status}`;
            const excerpt = document.createElement("p");
            excerpt.textContent = result.excerpt;
            const notice = document.createElement("p");
            notice.className = "tool-note";
            notice.textContent = result.notice;
            output.append(title, checked, excerpt, notice);
          })
          .catch((error) => {
            output.textContent = `${t("officialSourceUnavailable")} ${error.message}`;
          })
          .finally(() => {
            sourceButton.disabled = false;
          });
        return;
      }
      const button = event.target.closest("[data-remove-document]");
      if (!button || !activeScheme) return;
      const id = button.dataset.removeDocument;
      const key = `jansahayak:documents:${activeScheme.scheme_slug}`;
      const documents = readChecklist(key).filter((document) => document.id !== id);
      localStorage.setItem(key, JSON.stringify(documents));
      localStorage.removeItem(`${activeScheme.scheme_slug}:${id}`);
      open(activeScheme.scheme_slug).catch((error) => {
        document.getElementById("scheme-detail").textContent = error.message;
      });
    });
    document.getElementById("scheme-detail").addEventListener("submit", async (event) => {
      if (event.target.id === "document-add-form") {
        event.preventDefault();
        const field = event.target.elements.document_name;
        const name = field.value.trim();
        if (!name) {
          field.setCustomValidity(t("documentRequired"));
          field.reportValidity();
          return;
        }
        field.setCustomValidity("");
        const key = `jansahayak:documents:${activeScheme.scheme_slug}`;
        const documents = readChecklist(key);
        if (documents.some((document) => document.name.toLocaleLowerCase() === name.toLocaleLowerCase())) {
          field.setCustomValidity(t("documentDuplicate"));
          field.reportValidity();
          return;
        }
        documents.push({ id: `custom-${Date.now()}`, name, source: "custom" });
        localStorage.setItem(key, JSON.stringify(documents));
        await open(activeScheme.scheme_slug);
        return;
      }
      if (event.target.id !== "eligibility-form") return;
      event.preventDefault();
      const answers = Object.fromEntries(new FormData(event.target));
      for (const [key, value] of Object.entries(answers)) {
        if (value === "true") answers[key] = true;
        else if (value === "false") answers[key] = false;
      }
      const output = document.getElementById("assessment-result");
      output.textContent = t("checking");
      try {
        const result = await api("/api/eligibility/check", {
          method: "POST",
          body: JSON.stringify({ scheme_slug: activeScheme.scheme_slug, answers })
        });
        localStorage.setItem("jansahayak:eligibility:last", JSON.stringify([{
          slug: activeScheme.scheme_slug,
          status: result.overall_status
        }]));
        refreshDashboard();
        output.innerHTML = `<div class="assessment-result"><strong>${escapeHtml(t(`overall_${result.overall_status}`))}</strong>${result.conditions.map((condition, index) => {
          const rule = activeScheme.eligibility_rules[index];
          const name = ruleLabel(rule);
          const status = t(condition.status);
          const explanation = window.I18n.current() === "hi"
            ? condition.status === "unknown"
              ? "इस दर्ज शर्त का आकलन करने के लिए अधिक जानकारी चाहिए।"
              : rule[condition.status === "meets" ? "pass_explanation_hi" : "fail_explanation_hi"] || condition.explanation
            : condition.explanation;
          return `<div class="assessment-condition"><strong>${escapeHtml(name)}: ${escapeHtml(status)}</strong><br>${escapeHtml(explanation)}</div>`;
        }).join("")}<p>${escapeHtml(t("assessmentDisclaimer"))}</p></div>`;
      } catch (error) {
        output.innerHTML = `<p class="assessment-result">${escapeHtml(error.message)}</p>`;
      }
    });
  }

  window.Schemes = { load, setup, open, refreshDashboard };
})();
