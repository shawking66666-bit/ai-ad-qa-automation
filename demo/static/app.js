const form = document.getElementById("evaluation-form");
const typeInput = document.getElementById("asset-type");
const tabs = Array.from(document.querySelectorAll(".type-tab"));
const fields = {
  video: document.getElementById("video-field"),
  image: document.getElementById("image-field"),
  script: document.getElementById("script-field"),
};
const emptyState = document.getElementById("empty-state");
const loadingState = document.getElementById("loading-state");
const errorState = document.getElementById("error-state");
const reportContent = document.getElementById("report-content");
const resultStatus = document.getElementById("result-status");
const submitButton = document.getElementById("submit-button");
const elapsedTime = document.getElementById("elapsed-time");

function selectType(type) {
  typeInput.value = type;
  tabs.forEach((tab) => {
    const selected = tab.dataset.type === type;
    tab.classList.toggle("is-active", selected);
    tab.setAttribute("aria-selected", String(selected));
  });
  Object.entries(fields).forEach(([name, field]) => { field.hidden = name !== type; });
}

tabs.forEach((tab) => tab.addEventListener("click", () => selectType(tab.dataset.type)));
["video", "image"].forEach((type) => {
  document.getElementById(`${type}-input`).addEventListener("change", (event) => {
    const filename = event.target.files[0]?.name || "";
    document.getElementById(`${type}-name`).textContent = filename;
  });
});

function showOnly(state) {
  emptyState.hidden = state !== "empty";
  loadingState.hidden = state !== "loading";
  errorState.hidden = state !== "error";
  reportContent.hidden = state !== "report";
}

function renderReport(markdown) {
  reportContent.replaceChildren();
  const fragment = document.createDocumentFragment();
  let list = null;
  for (const originalLine of markdown.split(/\r?\n/)) {
    const line = originalLine.trim();
    if (!line) { list = null; continue; }
    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      list = null;
      const node = document.createElement(`h${heading[1].length}`);
      node.textContent = heading[2];
      fragment.appendChild(node);
    } else if (line.startsWith("- ")) {
      if (!list) {
        list = document.createElement("ul");
        fragment.appendChild(list);
      }
      const item = document.createElement("li");
      item.textContent = line.slice(2);
      list.appendChild(item);
    } else {
      list = null;
      const paragraph = document.createElement("p");
      paragraph.textContent = line;
      fragment.appendChild(paragraph);
    }
  }
  reportContent.appendChild(fragment);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const type = typeInput.value;
  const data = new FormData(form);
  if (type === "video") {
    data.delete("image");
    if (!document.getElementById("video-input").files.length) {
      errorState.textContent = "请先上传广告视频。";
      showOnly("error");
      return;
    }
  } else if (type === "image") {
    data.delete("video");
    if (!document.getElementById("image-input").files.length) {
      errorState.textContent = "请先上传广告图片。";
      showOnly("error");
      return;
    }
  } else {
    data.delete("video");
    data.delete("image");
    if (!document.getElementById("script-input").value.trim()) {
      errorState.textContent = "请先填写广告脚本。";
      showOnly("error");
      return;
    }
  }

  resultStatus.hidden = true;
  submitButton.disabled = true;
  elapsedTime.textContent = "0";
  showOnly("loading");
  const started = Date.now();
  const timer = window.setInterval(() => {
    elapsedTime.textContent = String(Math.floor((Date.now() - started) / 1000));
  }, 1000);
  try {
    const response = await fetch("/api/evaluate", { method: "POST", body: data });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "质检失败，请稍后重试。");
    renderReport(payload.report_markdown);
    resultStatus.textContent = payload.final_status === "human_review_required" ? "需人工复核" :
      payload.final_status === "completed" ? "已完成" : "部分完成";
    resultStatus.hidden = false;
    showOnly("report");
  } catch (error) {
    errorState.textContent = error instanceof Error ? error.message : "无法连接本地演示服务。";
    showOnly("error");
  } finally {
    window.clearInterval(timer);
    submitButton.disabled = false;
  }
});
