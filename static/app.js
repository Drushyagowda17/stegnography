const $ = (id) => document.getElementById(id);

const loader = $("loader");
const loaderText = $("loaderText");
const globalStatus = $("globalStatus");

const tabs = document.querySelectorAll(".tab");
const panels = document.querySelectorAll(".panel");

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    tabs.forEach((t) => t.classList.remove("active"));
    panels.forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    const target = document.querySelector(`#tab-${tab.dataset.tab}`);
    if (target) target.classList.add("active");
    
    if (tab.dataset.tab === "history") {
      fetchHistory();
    }
  });
});

const setStatus = (message) => {
  globalStatus.textContent = message;
};

const toggleLoader = (active, message = "Processing") => {
  if (active) {
    loader.classList.add("active");
    loaderText.textContent = message;
  } else {
    loader.classList.remove("active");
  }
};

const previewImage = (file, imgElement) => {
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    imgElement.src = reader.result;
  };
  reader.readAsDataURL(file);
};

$("embedImage").addEventListener("change", (e) => {
  previewImage(e.target.files[0], $("embedOriginalPreview"));
});

$("detectImage").addEventListener("change", (e) => {
  previewImage(e.target.files[0], $("detectPreview"));
});

$("embedBtn").addEventListener("click", async () => {
  const image = $("embedImage").files[0];
  const file = $("embedFile").files[0];
  const text = $("embedText").value;
  const key = $("embedKey").value.trim();
  const message = $("embedMessage");
  message.textContent = "";

  if (!image || !key) {
    message.textContent = "Cover image and key are required.";
    return;
  }
  if (!file && !text.trim()) {
    message.textContent = "Provide secret text or a secret file.";
    return;
  }

  const form = new FormData();
  form.append("image", image);
  form.append("key", key);
  if (file) {
    form.append("secret_file", file);
  } else {
    form.append("secret_text", text);
  }

  toggleLoader(true, "Embedding");
  setStatus("Embedding data...");
  try {
    const res = await fetch("/api/embed", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Embedding failed.");
    const stegoUrl = `data:image/png;base64,${data.stego_image_base64}`;
    $("embedStegoPreview").src = stegoUrl;
    $("downloadStego").href = stegoUrl;
    $("mse").textContent = data.metrics.mse.toFixed(4);
    $("psnr").textContent =
      data.metrics.psnr === Infinity ? "Infinity" : data.metrics.psnr.toFixed(2);
    $("capacity").textContent = `${data.metrics.capacity_bytes} bytes`;
    $("used").textContent = `${data.metrics.used_bytes} bytes`;
    message.textContent = "Stego image generated successfully.";
    setStatus("Ready");
  } catch (err) {
    message.textContent = err.message;
    setStatus("Error");
  } finally {
    toggleLoader(false);
  }
});

$("extractBtn").addEventListener("click", async () => {
  const image = $("extractImage").files[0];
  const key = $("extractKey").value.trim();
  const message = $("extractMessage");
  message.textContent = "";

  if (!image || !key) {
    message.textContent = "Stego image and key are required.";
    return;
  }

  const form = new FormData();
  form.append("image", image);
  form.append("key", key);

  toggleLoader(true, "Extracting");
  setStatus("Extracting data...");
  try {
    const res = await fetch("/api/extract", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Extraction failed.");
    $("extractFilename").textContent = data.filename;
    $("extractHash").textContent = data.sha256;
    $("extractIntegrity").textContent = data.verified ? "Verified" : "Mismatch";
    const raw = atob(data.data_base64);
    const blob = new Blob([new Uint8Array([...raw].map((c) => c.charCodeAt(0)))]);
    const url = URL.createObjectURL(blob);
    $("downloadExtract").href = url;
    $("downloadExtract").download = data.filename;
    $("extractPreview").value = raw.slice(0, 5000);
    message.textContent = "Extraction completed.";
    setStatus("Ready");
  } catch (err) {
    message.textContent = err.message;
    setStatus("Error");
  } finally {
    toggleLoader(false);
  }
});

$("detectBtn").addEventListener("click", async () => {
  const image = $("detectImage").files[0];
  const message = $("detectMessage");
  message.textContent = "";

  if (!image) {
    message.textContent = "Select an image to analyze.";
    return;
  }

  const form = new FormData();
  form.append("image", image);

  toggleLoader(true, "Analyzing");
  setStatus("Analyzing image...");
  try {
    const res = await fetch("/api/detect", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Detection failed.");
    $("detectScore").textContent = data.score.toFixed(3);
    $("detectVerdict").textContent = data.label;
    message.textContent = "Analysis completed.";
    setStatus("Ready");
  } catch (err) {
    message.textContent = err.message;
    setStatus("Error");
  } finally {
    toggleLoader(false);
  }
});

const fetchHistory = async () => {
  const message = $("historyMessage");
  if (!message) return;
  message.textContent = "";
  setStatus("Fetching history...");
  toggleLoader(true, "Loading History");
  
  try {
    const res = await fetch("/api/history");
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to fetch history.");
    
    const tbody = $("historyTableBody");
    tbody.innerHTML = "";
    
    if (data.length === 0) {
      tbody.innerHTML = "<tr><td colspan='5' style='text-align: center; padding: 1rem; color: var(--text-muted);'>No history found</td></tr>";
    } else {
      data.forEach(row => {
        const tr = document.createElement("tr");
        tr.style.borderBottom = "1px solid var(--border)";
        tr.innerHTML = `
          <td style="padding: 0.75rem 0.5rem; color: var(--primary);">${row.id}</td>
          <td style="padding: 0.75rem 0.5rem;">${row.timestamp}</td>
          <td style="padding: 0.75rem 0.5rem;">
            <span style="background: rgba(255,255,255,0.1); padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.8rem;">
              ${row.action}
            </span>
          </td>
          <td style="padding: 0.75rem 0.5rem; word-break: break-all;">${row.filename}</td>
          <td style="padding: 0.75rem 0.5rem;">${row.details}</td>
        `;
        tbody.appendChild(tr);
      });
    }
    setStatus("Ready");
  } catch (err) {
    message.textContent = err.message;
    setStatus("Error");
  } finally {
    toggleLoader(false);
  }
};

$("refreshHistoryBtn")?.addEventListener("click", fetchHistory);

if (window.location.protocol === 'file:') {
  setTimeout(() => {
    alert("Warning: You have opened this file using the 'file://' protocol. API requests will fail with 'failed to fetch'. Please run the server using 'python -m uvicorn main:app' and open http://127.0.0.1:8000 in your browser.");
  }, 1000);
}
