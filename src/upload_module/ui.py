from fastapi.responses import HTMLResponse

_UPLOAD_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>Upload desk</title>
  <style>
    :root {
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #17231f;
      background: #f3f5ef;
      font-synthesis: none;
      text-rendering: optimizeLegibility;
      --ink: #17231f;
      --muted: #65736d;
      --green: #19745a;
      --line: #e2e8e1;
    }
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; }
    button, input, select { font: inherit; }
    .shell { max-width: 1080px; margin: 0 auto; padding: 28px 24px 56px; }
    header { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
    .brand { display: flex; align-items: center; gap: 11px; font-size: 15px; font-weight: 750; letter-spacing: -.02em; }
    .brand-mark { display: grid; width: 35px; height: 35px; place-items: center; border-radius: 11px; color: white; background: var(--green); }
    .environment { color: #236449; background: #e1f1e8; border: 1px solid #cce5d6; border-radius: 999px; padding: 7px 11px; font-size: 11px; font-weight: 750; letter-spacing: .08em; text-transform: uppercase; }
    .intro { padding: 57px 0 30px; }
    .eyebrow { color: var(--green); font-size: 12px; font-weight: 750; letter-spacing: .12em; text-transform: uppercase; }
    h1 { margin: 12px 0 10px; font-size: clamp(32px, 5vw, 48px); line-height: 1.06; letter-spacing: -.055em; }
    .intro p { max-width: 590px; margin: 0; color: var(--muted); font-size: 16px; line-height: 1.65; }
    .layout { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(260px, .75fr); gap: 20px; align-items: start; }
    .card { border: 1px solid var(--line); border-radius: 18px; background: #fff; box-shadow: 0 12px 38px #1f38200a; }
    .form-card { padding: 26px; }
    .card-heading { display: flex; justify-content: space-between; align-items: start; gap: 16px; margin-bottom: 23px; }
    h2 { margin: 0; font-size: 18px; letter-spacing: -.025em; }
    .subheading { margin: 6px 0 0; color: var(--muted); font-size: 13px; line-height: 1.5; }
    .step { color: #819087; font-size: 12px; font-weight: 700; }
    .fields { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .field { display: flex; flex-direction: column; gap: 7px; }
    .field.full { grid-column: 1 / -1; }
    label { color: #33423b; font-size: 12px; font-weight: 700; }
    input, select { width: 100%; min-height: 43px; padding: 10px 12px; border: 1px solid #dce4dc; border-radius: 9px; color: var(--ink); background: #fff; outline: none; }
    input:focus, select:focus, button:focus-visible { border-color: #53a181; box-shadow: 0 0 0 3px #19745a1a; outline: none; }
    .file-box { min-height: 139px; padding: 22px; display: grid; place-items: center; text-align: center; border: 1px dashed #b9c9bd; border-radius: 12px; background: #f9fbf8; cursor: pointer; transition: background .15s, border-color .15s; }
    .file-box:hover, .file-box.dragging { border-color: var(--green); background: #f0f8f3; }
    .file-icon { display: grid; width: 34px; height: 34px; margin: 0 auto 9px; place-items: center; border-radius: 10px; color: var(--green); background: #e5f2e9; font-size: 19px; }
    .file-title { color: #33423b; font-size: 13px; font-weight: 700; }
    .file-hint { margin-top: 5px; color: var(--muted); font-size: 11px; }
    .file-name { margin-top: 9px; color: var(--green); font-size: 12px; font-weight: 700; overflow-wrap: anywhere; }
    .file-box input { position: absolute; width: 1px; height: 1px; opacity: 0; }
    .actions { display: flex; align-items: center; gap: 12px; margin-top: 21px; }
    .primary, .secondary { min-height: 42px; padding: 0 17px; border: 1px solid transparent; border-radius: 9px; cursor: pointer; font-size: 13px; font-weight: 750; transition: transform .12s, background .12s; }
    .primary { color: #fff; background: var(--green); }
    .primary:hover:not(:disabled) { background: #105e48; transform: translateY(-1px); }
    .secondary { color: #314039; border-color: var(--line); background: #fff; }
    .secondary:hover:not(:disabled) { background: #f6f8f5; }
    button:disabled { opacity: .55; cursor: not-allowed; }
    .message { min-height: 18px; margin: 13px 0 0; color: var(--muted); font-size: 12px; line-height: 1.5; }
    .message.error { color: #b42318; }
    .side { display: grid; gap: 16px; }
    .status-card, .info-card { padding: 22px; }
    .status-top { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
    .status-value { display: inline-flex; align-items: center; gap: 7px; color: #66746d; font-size: 11px; font-weight: 750; letter-spacing: .08em; text-transform: uppercase; }
    .dot { width: 8px; height: 8px; border-radius: 50%; background: #9aa79f; }
    .status-value[data-state="READY"], .status-value[data-state="DUPLICATE"] { color: #16704f; }
    .status-value[data-state="READY"] .dot, .status-value[data-state="DUPLICATE"] .dot { background: #20a36f; }
    .status-value[data-state="REJECTED"], .status-value[data-state="BLOCKED"], .status-value[data-state="FAILED"], .status-value[data-state="EXPIRED"] { color: #b54730; }
    .status-value[data-state="REJECTED"] .dot, .status-value[data-state="BLOCKED"] .dot, .status-value[data-state="FAILED"] .dot, .status-value[data-state="EXPIRED"] .dot { background: #d65b45; }
    .status-empty { padding: 25px 0 11px; color: var(--muted); font-size: 13px; line-height: 1.6; }
    .status-details { display: grid; gap: 12px; margin-top: 20px; }
    .detail { display: flex; justify-content: space-between; gap: 12px; color: var(--muted); font-size: 12px; }
    .detail strong { color: #33423b; text-align: right; overflow-wrap: anywhere; font-weight: 650; }
    .status-actions { display: flex; gap: 8px; margin-top: 19px; }
    .status-actions button { flex: 1; padding: 0 10px; font-size: 12px; }
    .info-card { background: #edf4ed; border-color: #dfebdf; }
    .info-card h2 { font-size: 14px; }
    .info-card p { margin: 9px 0 0; color: #586a60; font-size: 12px; line-height: 1.65; }
    .limits { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px; }
    .pill { padding: 6px 9px; border-radius: 999px; color: #416351; background: #dcebdd; font-size: 10px; font-weight: 700; }
    footer { margin-top: 27px; color: #87938c; font-size: 11px; text-align: center; }
    @media (max-width: 720px) {
      .shell { padding: 20px 16px 38px; }
      .intro { padding: 42px 0 24px; }
      .layout { grid-template-columns: 1fr; }
      .form-card { padding: 21px; }
    }
    @media (max-width: 440px) {
      .fields { grid-template-columns: 1fr; }
      .field.full { grid-column: auto; }
      .environment { font-size: 9px; }
      .actions { align-items: stretch; flex-direction: column; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header>
      <div class="brand"><span class="brand-mark" aria-hidden="true">U</span> Upload desk</div>
      <span class="environment">Local development</span>
    </header>
    <section class="intro">
      <div class="eyebrow">Document intake</div>
      <h1>Upload a document.<br>Track every step.</h1>
      <p>Send a resume or job description through the local upload and quarantine flow. Files are checked before they are marked ready.</p>
    </section>
    <main class="layout">
      <section class="card form-card" aria-labelledby="upload-heading">
        <div class="card-heading">
          <div>
            <h2 id="upload-heading">Start an upload</h2>
            <p class="subheading">Add the record details, then choose a PDF or DOCX.</p>
          </div>
          <span class="step">01 / 02</span>
        </div>
        <form id="upload-form">
          <div class="fields">
            <div class="field">
              <label for="owner-id">Owner ID</label>
              <input id="owner-id" name="owner_id" maxlength="128" value="owner-1" required>
            </div>
            <div class="field">
              <label for="job-id">Job ID</label>
              <input id="job-id" name="job_id" maxlength="128" value="job-1" required>
            </div>
            <div class="field full">
              <label for="track">Document type</label>
              <select id="track" name="track">
                <option value="resume">Resume</option>
                <option value="job_description">Job description</option>
              </select>
            </div>
            <div class="field full">
              <label for="file">Document file</label>
              <label class="file-box" id="file-box" for="file">
                <span>
                  <span class="file-icon" aria-hidden="true">↑</span>
                  <span class="file-title" id="file-title">Choose a file or drop it here</span>
                  <span class="file-hint" id="file-hint"></span>
                  <span class="file-name" id="file-name"></span>
                </span>
                <input id="file" name="file" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" required>
              </label>
            </div>
          </div>
          <div class="actions">
            <button class="primary" id="submit-button" type="submit">Upload document</button>
            <span class="subheading">A fresh retry creates a new upload session.</span>
          </div>
          <p class="message" id="message" role="status" aria-live="polite"></p>
        </form>
      </section>
      <aside class="side">
        <section class="card status-card" aria-labelledby="status-heading">
          <div class="status-top">
            <h2 id="status-heading">Upload status</h2>
            <span class="status-value" id="status-value" data-state="IDLE"><span class="dot"></span><span id="status-label">Waiting</span></span>
          </div>
          <div class="status-empty" id="status-empty">Your upload result and file checks will appear here.</div>
          <div class="status-details" id="status-details" hidden></div>
          <div class="status-actions">
            <button class="secondary" id="check-status" type="button" disabled>Check status</button>
            <button class="secondary" id="copy-id" type="button" disabled>Copy upload ID</button>
          </div>
        </section>
        <section class="card info-card">
          <h2>What happens next?</h2>
          <p>The service streams the file to quarantine, checks the document and scanner result, then records an outcome. A clean file can become ready for the next stage.</p>
          <div class="limits"><span class="pill">PDF / DOCX</span><span class="pill">Local only</span><span class="pill">No public access</span></div>
        </section>
      </aside>
    </main>
    <footer>Development interface · Do not expose this service to a shared or public network.</footer>
  </div>
  <script>
    const form = document.querySelector("#upload-form");
    const fileInput = document.querySelector("#file");
    const fileBox = document.querySelector("#file-box");
    const fileName = document.querySelector("#file-name");
    const fileTitle = document.querySelector("#file-title");
    const submitButton = document.querySelector("#submit-button");
    const message = document.querySelector("#message");
    const statusValue = document.querySelector("#status-value");
    const statusLabel = document.querySelector("#status-label");
    const statusEmpty = document.querySelector("#status-empty");
    const statusDetails = document.querySelector("#status-details");
    const checkButton = document.querySelector("#check-status");
    const copyButton = document.querySelector("#copy-id");
    const maxUploadBytes = __MAX_UPLOAD_BYTES__;
    let activeUploadId = null;
    let lastFileName = "";
    document.querySelector("#file-hint").textContent =
      `PDF or DOCX · ${(maxUploadBytes / (1024 * 1024)).toFixed(0)} MB maximum`;

    function setMessage(text, isError = false) {
      message.textContent = text;
      message.classList.toggle("error", isError);
    }

    function setStatus(state, details = {}) {
      statusValue.dataset.state = state || "IDLE";
      statusLabel.textContent = state || "Waiting";
      statusEmpty.hidden = Boolean(state);
      statusDetails.hidden = !state;
      statusDetails.replaceChildren();
      if (!state) return;
      const entries = [
        ["File", details.filename || lastFileName || "—"],
        ["Upload ID", details.upload_id || activeUploadId || "—"],
        ["Size", Number.isInteger(details.size_bytes) ? `${(details.size_bytes / 1024).toFixed(1)} KB` : "—"],
        ["File type", details.actual_type || "—"],
        ["Reason", details.reason_code || "—"],
        ["SHA-256", details.sha256 ? `${details.sha256.slice(0, 12)}…` : "—"]
      ];
      for (const [label, value] of entries) {
        const row = document.createElement("div");
        row.className = "detail";
        const key = document.createElement("span");
        const content = document.createElement("strong");
        key.textContent = label;
        content.textContent = value;
        row.append(key, content);
        statusDetails.append(row);
      }
    }

    async function readResponse(response) {
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = payload.detail;
        const reason = typeof detail === "string" ? detail : detail?.reason_code || detail?.message;
        throw new Error(reason || `Request failed (${response.status})`);
      }
      return payload;
    }

    fileInput.addEventListener("change", () => {
      const file = fileInput.files[0];
      fileName.textContent = file ? file.name : "";
      fileTitle.textContent = file ? "File selected" : "Choose a file or drop it here";
      lastFileName = file ? file.name : "";
    });

    for (const eventName of ["dragenter", "dragover"]) {
      fileBox.addEventListener(eventName, (event) => {
        event.preventDefault();
        fileBox.classList.add("dragging");
      });
    }
    for (const eventName of ["dragleave", "drop"]) {
      fileBox.addEventListener(eventName, (event) => {
        event.preventDefault();
        fileBox.classList.remove("dragging");
      });
    }
    fileBox.addEventListener("drop", (event) => {
      const file = event.dataTransfer.files[0];
      if (!file) return;
      const transfer = new DataTransfer();
      transfer.items.add(file);
      fileInput.files = transfer.files;
      fileInput.dispatchEvent(new Event("change", { bubbles: true }));
    });

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const file = fileInput.files[0];
      if (!file) return;
      if (file.size === 0) {
        setMessage("The selected file is empty.", true);
        return;
      }
      if (file.size > maxUploadBytes) {
        setMessage("The selected file is larger than the configured local limit.", true);
        return;
      }
      const extension = file.name.toLowerCase().split(".").pop();
      if (!["pdf", "docx"].includes(extension)) {
        setMessage("Choose a PDF or DOCX document.", true);
        return;
      }

      submitButton.disabled = true;
      checkButton.disabled = true;
      copyButton.disabled = true;
      activeUploadId = null;
      setMessage("Creating an upload session…");
      setStatus("CREATED", { filename: file.name });
      lastFileName = file.name;

      try {
        const request = {
          owner_id: form.elements.owner_id.value.trim(),
          job_id: form.elements.job_id.value.trim(),
          track: form.elements.track.value,
          filename: file.name,
          declared_content_type: file.type || null,
          declared_size_bytes: file.size
        };
        const session = await readResponse(await fetch("/uploads", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": crypto.randomUUID()
          },
          body: JSON.stringify(request)
        }));
        activeUploadId = session.upload_id;
        checkButton.disabled = false;
        copyButton.disabled = false;
        setStatus(session.status, session);
        setMessage("Uploading and checking your document…");
        const result = await readResponse(await fetch(`/uploads/${encodeURIComponent(activeUploadId)}/content`, {
          method: "PUT",
          headers: { "Content-Type": "application/octet-stream" },
          body: file
        }));
        setStatus(result.status, result);
        setMessage(result.status === "READY" ? "Upload complete. The document is ready for the next stage." : `Upload complete with status ${result.status}.`);
      } catch (error) {
        setMessage(error.message || "The upload could not be completed.", true);
        if (activeUploadId) await refreshStatus();
        else setStatus("");
      } finally {
        submitButton.disabled = false;
      }
    });

    async function refreshStatus() {
      if (!activeUploadId) return;
      checkButton.disabled = true;
      try {
        const result = await readResponse(await fetch(`/uploads/${encodeURIComponent(activeUploadId)}`));
        setStatus(result.status, result);
        setMessage(`Current upload status: ${result.status}.`);
      } catch (error) {
        setMessage(error.message || "Could not read upload status.", true);
      } finally {
        checkButton.disabled = false;
      }
    }

    checkButton.addEventListener("click", refreshStatus);
    copyButton.addEventListener("click", async () => {
      if (!activeUploadId) return;
      try {
        await navigator.clipboard.writeText(activeUploadId);
        setMessage("Upload ID copied.");
      } catch (_error) {
        setMessage("Clipboard access is unavailable in this browser.", true);
      }
    });
  </script>
</body>
</html>
"""


def upload_page(max_upload_bytes: int) -> HTMLResponse:
    page = _UPLOAD_PAGE.replace("__MAX_UPLOAD_BYTES__", str(max_upload_bytes))
    return HTMLResponse(page)
