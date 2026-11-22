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
      background: #f5f7f3;
      font-synthesis: none;
      text-rendering: optimizeLegibility;
      --ink: #17231f;
      --muted: #65736d;
      --green: #19745a;
      --line: #e2e8e1;
      --surface: #fff;
    }
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; }
    button, input, select { font: inherit; }
    .shell { max-width: 1140px; margin: 0 auto; padding: 24px 28px 48px; }
    header { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding-bottom: 17px; border-bottom: 1px solid #e5eae3; }
    .brand { display: flex; align-items: center; gap: 11px; font-size: 15px; font-weight: 750; letter-spacing: -.02em; }
    .brand-mark { display: grid; width: 35px; height: 35px; place-items: center; border-radius: 11px; color: white; background: var(--green); }
    .environment { color: #236449; background: #e1f1e8; border: 1px solid #cce5d6; border-radius: 999px; padding: 7px 11px; font-size: 11px; font-weight: 750; letter-spacing: .08em; text-transform: uppercase; }
    .intro { padding: 48px 0 27px; }
    .eyebrow { color: var(--green); font-size: 12px; font-weight: 750; letter-spacing: .12em; text-transform: uppercase; }
    h1 { margin: 11px 0 9px; font-size: clamp(32px, 5vw, 44px); line-height: 1.08; letter-spacing: -.05em; }
    .intro p { max-width: 620px; margin: 0; color: var(--muted); font-size: 15px; line-height: 1.65; }
    .workflow { display: flex; align-items: center; max-width: 580px; margin: 0 0 22px; }
    .workflow-step { display: flex; flex: 0 0 auto; align-items: center; gap: 8px; color: #89958e; font-size: 11px; font-weight: 700; }
    .workflow-step .number { display: grid; width: 25px; height: 25px; place-items: center; border: 1px solid #dce5dc; border-radius: 50%; color: #77847c; background: #fff; font-size: 11px; }
    .workflow-step.active { color: #245c49; }
    .workflow-step.active .number { border-color: #19745a; color: #fff; background: #19745a; box-shadow: 0 0 0 4px #19745a16; }
    .workflow-step.complete { color: #19745a; }
    .workflow-step.complete .number { border-color: #cce7d7; color: #19745a; background: #e8f5ed; }
    .workflow-step.failed { color: #b54730; }
    .workflow-step.failed .number { border-color: #f2c7be; color: #fff; background: #c74b36; }
    .workflow-line { height: 1px; flex: 1 1 auto; min-width: 22px; margin: 0 11px; background: #dfe6de; }
    .layout { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(260px, .75fr); gap: 20px; align-items: start; }
    .card { border: 1px solid var(--line); border-radius: 17px; background: var(--surface); box-shadow: 0 10px 32px #1f382008; }
    .form-card { padding: 25px; }
    .card-heading { display: flex; justify-content: space-between; align-items: start; gap: 16px; margin-bottom: 23px; }
    h2 { margin: 0; font-size: 18px; letter-spacing: -.025em; }
    .subheading { margin: 6px 0 0; color: var(--muted); font-size: 13px; line-height: 1.5; }
    .step { padding: 6px 9px; border-radius: 7px; color: #65736d; background: #f2f5f1; font-size: 10px; font-weight: 750; letter-spacing: .07em; }
    .fields { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .field { display: flex; flex-direction: column; gap: 7px; }
    .field.full { grid-column: 1 / -1; }
    label { color: #33423b; font-size: 12px; font-weight: 700; }
    input, select { width: 100%; min-height: 43px; padding: 10px 12px; border: 1px solid #dce4dc; border-radius: 9px; color: var(--ink); background: #fff; outline: none; transition: border-color .15s, box-shadow .15s; }
    input:focus, select:focus, button:focus-visible { border-color: #53a181; box-shadow: 0 0 0 3px #19745a1a; outline: none; }
    .file-box { min-height: 154px; padding: 20px; display: grid; place-items: center; text-align: center; border: 1px dashed #b9c9bd; border-radius: 12px; background: #f9fbf8; cursor: pointer; transition: background .15s, border-color .15s, box-shadow .15s; }
    .file-box:hover, .file-box.dragging { border-color: var(--green); background: #f0f8f3; }
    .file-box:focus-within { border-color: var(--green); box-shadow: 0 0 0 3px #19745a1a; }
    .file-icon { display: grid; width: 34px; height: 34px; margin: 0 auto 9px; place-items: center; border-radius: 10px; color: var(--green); background: #e5f2e9; font-size: 19px; }
    .file-title, .file-hint, .file-name { display: block; }
    .file-title { color: #33423b; font-size: 13px; font-weight: 700; }
    .file-hint { margin-top: 6px; color: var(--muted); font-size: 11px; }
    .file-name { margin-top: 9px; color: var(--green); font-size: 12px; font-weight: 700; overflow-wrap: anywhere; }
    .file-box input { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; }
    .actions { display: flex; align-items: center; gap: 13px; margin-top: 20px; }
    .primary, .secondary { min-height: 43px; padding: 0 17px; border: 1px solid transparent; border-radius: 9px; cursor: pointer; font-size: 13px; font-weight: 750; transition: transform .12s, background .12s, box-shadow .12s; }
    .primary { color: #fff; background: var(--green); }
    .primary:hover:not(:disabled) { background: #105e48; transform: translateY(-1px); }
    .secondary { color: #314039; border-color: var(--line); background: #fff; }
    .secondary:hover:not(:disabled) { background: #f6f8f5; }
    button:disabled { opacity: .55; cursor: not-allowed; }
    .message { min-height: 18px; margin: 13px 0 0; color: var(--muted); font-size: 12px; line-height: 1.5; }
    .message.error { color: #b42318; }
    .upload-progress { margin-top: 15px; }
    .upload-progress[hidden] { display: none; }
    .progress-meta { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 7px; color: var(--muted); font-size: 11px; }
    .progress-meta strong { color: #33423b; font-weight: 700; }
    progress { display: block; width: 100%; height: 7px; overflow: hidden; border: 0; border-radius: 99px; appearance: none; background: #e8eee8; }
    progress::-webkit-progress-bar { border-radius: 99px; background: #e8eee8; }
    progress::-webkit-progress-value { border-radius: 99px; background: #19745a; transition: width .18s ease; }
    progress::-moz-progress-bar { border-radius: 99px; background: #19745a; }
    .side { display: grid; gap: 16px; }
    .status-card, .info-card { padding: 22px; }
    .status-top { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
    .status-value { display: inline-flex; align-items: center; gap: 7px; color: #66746d; font-size: 11px; font-weight: 750; letter-spacing: .08em; text-transform: uppercase; }
    .dot { width: 8px; height: 8px; border-radius: 50%; background: #9aa79f; }
    .status-value[data-state="READY"], .status-value[data-state="DUPLICATE"] { color: #16704f; }
    .status-value[data-state="READY"] .dot, .status-value[data-state="DUPLICATE"] .dot { background: #20a36f; }
    .status-value[data-state="REJECTED"], .status-value[data-state="BLOCKED"], .status-value[data-state="FAILED"], .status-value[data-state="EXPIRED"] { color: #b54730; }
    .status-value[data-state="REJECTED"] .dot, .status-value[data-state="BLOCKED"] .dot, .status-value[data-state="FAILED"] .dot, .status-value[data-state="EXPIRED"] .dot { background: #d65b45; }
    .status-empty { padding: 22px 0 17px; color: var(--muted); font-size: 13px; line-height: 1.6; }
    .status-details { display: grid; gap: 12px; margin-top: 20px; }
    .detail { display: flex; justify-content: space-between; gap: 12px; color: var(--muted); font-size: 12px; }
    .detail strong { color: #33423b; text-align: right; overflow-wrap: anywhere; font-weight: 650; }
    .status-actions { display: flex; gap: 8px; margin-top: 19px; }
    .status-actions button { flex: 1; padding: 0 10px; font-size: 12px; }
    .info-card { background: #f0f6ef; border-color: #e0eadf; }
    .info-card h2 { font-size: 14px; }
    .info-card p { margin: 9px 0 0; color: #586a60; font-size: 12px; line-height: 1.65; }
    .limits { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px; }
    .pill { padding: 6px 9px; border-radius: 999px; color: #416351; background: #dcebdd; font-size: 10px; font-weight: 700; }
    footer { margin-top: 27px; color: #87938c; font-size: 11px; text-align: center; }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; }
    }
    @media (max-width: 720px) {
      .shell { padding: 20px 16px 38px; }
      .intro { padding: 42px 0 24px; }
      .layout { grid-template-columns: 1fr; }
      .form-card { padding: 21px; }
      .workflow { max-width: 100%; }
    }
    @media (max-width: 440px) {
      .shell { padding-inline: 14px; }
      .fields { grid-template-columns: 1fr; }
      .field.full { grid-column: auto; }
      .environment { font-size: 9px; }
      .actions { align-items: stretch; flex-direction: column; }
      .workflow-step { gap: 6px; font-size: 10px; }
      .workflow-line { min-width: 13px; margin-inline: 6px; }
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
    <div class="workflow" aria-label="Upload steps">
      <div class="workflow-step" data-workflow="1"><span class="number">1</span><span>Session</span></div>
      <span class="workflow-line" aria-hidden="true"></span>
      <div class="workflow-step" data-workflow="2"><span class="number">2</span><span>Transfer</span></div>
      <span class="workflow-line" aria-hidden="true"></span>
      <div class="workflow-step" data-workflow="3"><span class="number">3</span><span>Security checks</span></div>
    </div>
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
          <div class="upload-progress" id="upload-progress" hidden>
            <div class="progress-meta"><span id="progress-label">Preparing transfer</span><strong id="progress-percent">0%</strong></div>
            <progress id="progress-bar" max="100" value="0" aria-label="Upload progress"></progress>
          </div>
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
    const progressPanel = document.querySelector("#upload-progress");
    const progressLabel = document.querySelector("#progress-label");
    const progressPercent = document.querySelector("#progress-percent");
    const progressBar = document.querySelector("#progress-bar");
    const maxUploadBytes = __MAX_UPLOAD_BYTES__;
    let activeUploadId = null;
    let lastFileName = "";
    document.querySelector("#file-hint").textContent =
      `PDF or DOCX · ${(maxUploadBytes / (1024 * 1024)).toFixed(0)} MB maximum`;

    function setMessage(text, isError = false) {
      message.textContent = text;
      message.classList.toggle("error", isError);
    }

    function setWorkflow(activeStep, failed = false) {
      for (const step of document.querySelectorAll(".workflow-step")) {
        const stepNumber = Number(step.dataset.workflow);
        step.classList.toggle("active", stepNumber === activeStep && !failed);
        step.classList.toggle("complete", stepNumber < activeStep);
        step.classList.toggle("failed", failed && stepNumber === activeStep);
      }
    }

    function setProgress(percent, label) {
      progressPanel.hidden = false;
      progressBar.value = percent;
      progressPercent.textContent = `${percent}%`;
      progressLabel.textContent = label;
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

    function uploadFile(file, uploadId) {
      return new Promise((resolve, reject) => {
        const request = new XMLHttpRequest();
        request.open("PUT", `/uploads/${encodeURIComponent(uploadId)}/content`);
        request.setRequestHeader("Content-Type", "application/octet-stream");
        request.upload.addEventListener("progress", (event) => {
          if (!event.lengthComputable) return;
          const percent = Math.min(99, Math.round((event.loaded / event.total) * 100));
          setProgress(percent, "Sending document");
        });
        request.upload.addEventListener("load", () => {
          setProgress(100, "Transfer complete · checking document");
          setWorkflow(3);
          setMessage("File received. Running document and malware checks…");
        });
        request.addEventListener("load", () => {
          let payload = {};
          try {
            payload = JSON.parse(request.responseText);
          } catch (_error) {
            reject(new Error("The server returned an unreadable response."));
            return;
          }
          if (request.status < 200 || request.status >= 300) {
            const detail = payload.detail;
            const reason = typeof detail === "string" ? detail : detail?.reason_code || detail?.message;
            reject(new Error(reason || `Request failed (${request.status})`));
            return;
          }
          resolve(payload);
        });
        request.addEventListener("error", () => reject(new Error("Network error while uploading the document.")));
        request.addEventListener("abort", () => reject(new Error("Upload was interrupted.")));
        request.send(file);
      });
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
      if (file) {
        const size = file.size < 1024 * 1024
          ? `${(file.size / 1024).toFixed(1)} KB`
          : `${(file.size / (1024 * 1024)).toFixed(2)} MB`;
        fileName.textContent = `${file.name} · ${size}`;
      }
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
      progressPanel.hidden = true;
      progressBar.value = 0;
      setWorkflow(1);
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
        setWorkflow(2);
        setProgress(0, "Starting transfer");
        setStatus(session.status, session);
        setMessage("Uploading and checking your document…");
        const result = await uploadFile(file, activeUploadId);
        setProgress(100, "Document checked");
        setStatus(result.status, result);
        setMessage(result.status === "READY" ? "Upload complete. The document is ready for the next stage." : `Upload complete with status ${result.status}.`);
      } catch (error) {
        const errorMessage = error.message || "The upload could not be completed.";
        if (!progressPanel.hidden) {
          progressLabel.textContent = progressBar.value === 100
            ? "Transfer complete · checks failed"
            : "Transfer interrupted";
        }
        if (activeUploadId) {
          setWorkflow(3, true);
          await refreshStatus(false);
        } else {
          setStatus("");
        }
        setMessage(errorMessage, true);
      } finally {
        submitButton.disabled = false;
      }
    });

    async function refreshStatus(announce = true) {
      if (!activeUploadId) return;
      checkButton.disabled = true;
      try {
        const result = await readResponse(await fetch(`/uploads/${encodeURIComponent(activeUploadId)}`));
        setStatus(result.status, result);
        if (announce) setMessage(`Current upload status: ${result.status}.`);
      } catch (error) {
        if (announce) setMessage(error.message || "Could not read upload status.", true);
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
