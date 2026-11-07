# JanSahayak AI

JanSahayak AI is an independent, student-built prototype for discovering government scheme information, reviewing recorded eligibility conditions, and planning what to verify next. It is **not** an official government portal and does not determine official eligibility or submit applications.

## What works

- Responsive scheme explorer backed by SQLite, with text/category/government-level filters and detail views.
- Typo-tolerant English, Hindi, and Roman-Hindi discovery with ranked related-scheme suggestions; a related central scheme is not presented as a state-specific scheme.
- A source-linked starter catalogue of 12 partial scheme records across education, agriculture, employment, health, housing, business, pension, and social welfare. No unverified details are presented as official eligibility.
- Flask JSON API for scheme search/details and comparison, eligibility, chat, temporary document checks, suspicious-link heuristics, complaint drafts, and a manual application tracker.
- A deterministic eligibility engine that distinguishes matching, failing, and unanswered recorded conditions.
- English/Hindi catalogue-based chat with keyword retrieval and predictable rule-based answers. It does not call an external or local language model.
- Hindi language selection translates the main interface and uses Hindi scheme summaries, eligibility labels, and rule-based answers where the database has reviewed Hindi text.
- Browser speech recognition when supported, Hindi `hi-IN` selection, editable recognized text, speech synthesis, and a stop-speaking control.
- Document readiness UI for documents added to scheme records. No document checklist is fabricated when the source record has none; current seed entries explicitly show this gap.
- Users can add a document name to their own browser-only checklist after checking it against the official source; the app never asks for uploads or identifier values. A separate set of local preparation reminders covers checking eligibility, documents, dates, and official application channels without presenting those reminders as official scheme steps.
- Scheme comparison, saved/recent/recommended schemes, and eligibility summaries are kept in browser local storage.
- The application tracker stores only a scheme and manually entered status history in SQLite, scoped by a random browser profile ID. It does not collect application numbers or query government systems.
- Document uploads accept PDF/PNG/JPEG files up to 5 MB, are checked in memory, and are not saved. OCR and image-quality analysis are explicitly unavailable until configured.
- The fraud helper checks a limited set of government-domain suffixes and suspicious-message patterns without opening links; it is a heuristic, not a verdict. Complaint drafting is local template-based and never submits a complaint.
- Chat is not stored by the application. Checklist, saved schemes, recommendations, and recent views stay in browser local storage. Do not enter Aadhaar numbers, bank details, OTPs, passwords, or other sensitive information.

## Scheme data and verification

The starter database contains 12 records and is deliberately marked `partial`, not `verified`. Official pages were checked on **2026-11-06** for the newly added records; the original PMS-SC and PM-KISAN records were checked on **2026-10-30**. A checked URL or scheme name does not prove that all rules are current: most source pages did not verify complete eligibility, benefit, document, deadline, or application information. Only the three recorded PMS-SC scope conditions are assessed, and the prototype will not show an overall positive assessment for a partial record. Other schemes without recorded conditions cannot be assessed.

Each seed record stores its source URL, date checked, and verification status. Unsupported documents and application steps are left empty. Before changing an entry to `verified`, check the current official guidelines, source every factual field, and have a person review the complete eligibility rules and application instructions. For scheme expansion, update `data/schemes.json`; bundled seed records are synchronized into SQLite on startup.

Official source pages:

- [Ministry of Social Justice and Empowerment — PMS-SC](https://socialjustice.gov.in/schemes/25)
- [PM-KISAN official portal](https://pmkisan.gov.in/)
- [National Scholarship Portal](https://scholarships.gov.in/)
- [PM POSHAN official portal](https://pmposhan.education.gov.in/)
- [PMFBY official portal](https://pmfby.gov.in/)
- [National Health Authority — PM-JAY](https://nha.gov.in/PM-JAY)
- [PMAY-G official portal](https://pmayg.dord.gov.in/netiayHome/Home.aspx)
- [PMAY-U official portal](https://pmay-urban.gov.in/)
- [PM SVANidhi official portal](https://pmsvanidhi.mohua.gov.in/)
- [PFRDA — Atal Pension Yojana](https://www.pfrda.org.in/web/pfrda/schemes/atal-pension-yojana-apy)
- [MGNREGS official portal](https://nrega.dord.gov.in/Nregahome/MGNREGA_new/Nrega_home.aspx)
- [PM Ujjwala Yojana](https://www.pmuy.gov.in/about.html)
- [myScheme official portal](https://www.myscheme.gov.in/)

### Citizen-service API behavior

- `POST /api/documents/analyze` validates PDF/PNG/JPEG magic bytes and size in memory. OCR, document identification, and image-quality analysis are not enabled; the file is not written to disk.
- `POST /api/fraud/check` returns `Verified Official`, `Suspicious`, or `Unable to Verify` from URL structure, a small government-domain allowlist, and text signals. It does not fetch or certify the website.
- `POST /api/complaints/generate` creates an editable Hindi/English draft and asks relevant follow-up questions. It does not submit the complaint; no grievance route is recommended unless a verified source is configured.
- `POST /api/applications` and `GET /api/applications` track only manually entered scheme/status history, keyed by a random browser profile ID. There is no account system or government status integration. The SQLite database is local to this app installation; do not use real or sensitive case information.

### Live official sources

- Each scheme detail has **Fetch live official page text**. It requests the scheme's preconfigured HTTPS source, extracts a short visible-text excerpt, and caches it for five minutes. It does **not** rewrite scheme data or turn the excerpt into verified eligibility, benefit, document, or deadline facts. Many official sites block automated requests or render content in scripts; an unavailable page is shown as an error.
- There is no single verified public government API that exposes complete current scheme details for every central and state scheme. The app therefore keeps incomplete fields marked and links to the official source instead of claiming a live page is a complete scheme database.

## Run locally on Windows

Open PowerShell in this project folder.

```powershell
py -3.12 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

Open <http://127.0.0.1:5000> in Chrome or Edge. On first startup, the app creates `data\jansahayak.db` from `data\schemes.json`. The SQLite database is local and ignored by Git.

The app loads `.env` on startup. Keep it private and ignored by Git; restart Flask after changing it.

### Run the tests

In an activated virtual environment:

```powershell
python -m unittest discover -s tests -v
```

Tests use temporary SQLite databases and do not require internet access.

### Voice and microphone troubleshooting

- Speech recognition support varies by browser. If the microphone is unavailable, type the question instead.
- Allow microphone access for the local site in browser permissions, then reload.
- Select हिन्दी before using voice input to request the browser's `hi-IN` recognition locale. Recognition quality depends on browser and operating-system language support.
- Speech synthesis uses the browser's available voices; an installed Hindi voice may be needed for Hindi playback.
- The typed transcript remains editable before sending. A recognition error is shown instead of pretending it succeeded.

### Common setup errors

- **`python` or `py` not found:** install Python 3.12 from python.org and enable the launcher/PATH options.
- **Activation is blocked:** run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in the same PowerShell window, then activate again.
- **`No module named flask`:** activate `.venv` and run `pip install -r requirements.txt`.
- **Port 5000 is already in use:** close the other app or start with `$env:PORT = "5001"; python app.py`, then open `http://127.0.0.1:5001`.
- **Bundled scheme data changed:** restart Flask; bundled records are synchronized at startup. Back up `data\jansahayak.db` before manual database edits.

## GitHub upload

Create an empty repository on GitHub, then run these commands from the project directory (replace the remote URL):

```powershell
git init
git add .
git status
git commit -m "Build JanSahayak AI prototype"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git push -u origin main
```

Confirm `.env`, `.venv`, and `data\jansahayak.db` are not staged. Do not commit API keys, personal information, or local database contents.

## Free-tier deployment (optional)

Render has offered free web services, but its pricing, limits, and availability can change. Check the provider's current terms before relying on it; free instances may sleep, have limited resources, or lose local files. SQLite on an ephemeral instance is only suitable for a demo, not durable production data.

1. Push the code to a GitHub repository.
2. Create a Python web service with the repository in a provider that currently offers a compatible free tier.
3. Use build command: `pip install -r requirements.txt gunicorn`.
4. Use start command: `gunicorn app:app --bind 0.0.0.0:$PORT`.
5. Configure the database path only if needed; do not use real citizen records.
6. Open the deployed URL and test `/api/health`, scheme search, and the assistant. Do not use real citizen records.

The Flask app serves the frontend and API on the same origin; CORS is not needed. A production deployment should use durable managed storage, HTTPS, monitoring, a reviewed privacy notice, and re-verified scheme data.

## 3–5 minute hackathon demo

1. **0:00–0:30 — Set expectations:** introduce the app as an independent prototype; point out that source links and incomplete-data labels are deliberate.
2. **0:30–1:15 — Explore:** search “UP scholership” to show typo-tolerant related results; clarify that the catalog does not verify a UP-specific scholarship. Open a scheme and visit its linked source.
3. **1:15–2:00 — Compare and check:** compare two schemes. If using PMS-SC, enter SC, post-matric, and India; explain that the result still needs more information because the record is partial.
4. **2:00–3:00 — Hindi assistant:** ask “Mujhe scholarship chahiye.” Show the related-scheme explanation and source links. If available, demonstrate the microphone and speaker controls.
5. **3:00–4:00 — Citizen tools:** create a complaint draft, review the manual application tracker, and run a link-pattern check. Point out that the tracker is manual, no complaint is submitted, and the fraud check is not a verdict.
6. **4:00–4:30 — Wrap up:** point out that OCR and official alerts are not included, and remind viewers to confirm scheme details with the linked official source.

## Limitations and future work

- The 12 partial source records are not a comprehensive national/state directory. The checked material did not establish a women-specific record suitable for inclusion.
- No record currently provides a complete, verified document list or application-step checklist, so those sections explicitly ask the user to verify the official source.
- The document readiness and next-step checklists are user-owned browser-local preparation aids; they are not saved to the server and do not state that a document or application will be accepted.
- Eligibility answers are assessed only against recorded conditions and never imply approval. State-specific rules and exceptions require further verified data.
- Typo-tolerant retrieval helps find related names and keywords, but it is not a complete natural-language understanding system. Chat answers are based on the local catalogue and rules; verify factual claims against linked sources.
- Browser speech recognition may use browser-provided services and its data handling depends on the browser. Text input remains available.
- OCR and image quality checks require additional local tooling and are not available in this build. Uploaded file bytes are received by the local server in memory and discarded after inspection.
- Office search and government alerts are not included because reliable live data sources are not configured. The application tracker is manual; no application submission, accounts, or live government status integration exists.
- This is not a production deployment/storage setup. Add rate controls, reviewed privacy/security policies, durable managed storage, and independent verification before real-world use.
