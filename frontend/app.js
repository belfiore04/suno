const HOTSPOT_IDS = [
  11, 12, 13, 14, 15,
  21, 22, 23, 24, 25,
  31, 32, 33, 34, 35,
  41, 42, 43, 44, 45,
];

const HOTSPOT_WORDS = {
  11: "浮叶",
  12: "晨钟",
  13: "断句",
  14: "倒刺",
  15: "碎镜",
  21: "暗涌",
  22: "苔原",
  23: "软重",
  24: "沉晖",
  25: "未烬",
  31: "侧临",
  32: "无滞",
  33: "静观",
  34: "返听",
  35: "不沾",
  41: "重频",
  42: "余振",
  43: "伏根",
  44: "地脉",
  45: "底鸣",
};

const state = {
  mode: "edit",
  activeId: 11,
  selectedIds: [],
  hotspots: [],
  drag: null,
  viewHeight: 562.5,
  videoUrl: "",
  generationKey: "",
  generating: false,
};

const els = {
  introScreen: document.querySelector("#introScreen"),
  introVideo: document.querySelector("#introVideo"),
  introVideoInput: document.querySelector("#introVideoInput"),
  introLayer: document.querySelector("#introHotspotLayer"),
  introEmpty: document.querySelector("#introEmpty"),
  enterEditorButton: document.querySelector("#enterEditorButton"),
  generationPanel: document.querySelector("#generationPanel"),
  generatingError: document.querySelector("#generatingError"),
  qrModal: document.querySelector("#qrModal"),
  qrCloseButton: document.querySelector("#qrCloseButton"),
  qrTitle: document.querySelector("#qrTitle"),
  qrImage: document.querySelector("#qrImage"),
  qrDownloadLink: document.querySelector("#qrDownloadLink"),
  referenceAudioLink: document.querySelector("#referenceAudioLink"),
  generatedAudio: document.querySelector("#generatedAudio"),
  video: document.querySelector("#video"),
  videoInput: document.querySelector("#videoInput"),
  playButton: document.querySelector("#playButton"),
  emptyState: document.querySelector("#emptyState"),
  layer: document.querySelector("#hotspotLayer"),
  editModeButton: document.querySelector("#editModeButton"),
  selectModeButton: document.querySelector("#selectModeButton"),
  createButton: document.querySelector("#createButton"),
  clearSelectionButton: document.querySelector("#clearSelectionButton"),
  exportButton: document.querySelector("#exportButton"),
  importInput: document.querySelector("#importInput"),
  selectionCount: document.querySelector("#selectionCount"),
  selectionList: document.querySelector("#selectionList"),
  hotspotList: document.querySelector("#hotspotList"),
  outputBox: document.querySelector("#outputBox"),
  idInput: document.querySelector("#idInput"),
  nameInput: document.querySelector("#nameInput"),
  fileInput: document.querySelector("#fileInput"),
  widthInput: document.querySelector("#widthInput"),
  heightInput: document.querySelector("#heightInput"),
  rotationInput: document.querySelector("#rotationInput"),
};

function defaultHotspot(id, index) {
  const col = index % 5;
  const row = Math.floor(index / 5);
  const group = Math.floor(id / 10);
  const option = id % 10;
  const rowGap = state.viewHeight / 4.45;

  return {
    id,
    name: HOTSPOT_WORDS[id] ?? `音频 ${id}`,
    file: `music/${option}.${group}_1.mp3`,
    x: 140 + col * 180,
    y: 70 + row * rowGap,
    rx: 58,
    ry: 34,
    rotation: 0,
  };
}

function createDefaultHotspots() {
  state.hotspots = HOTSPOT_IDS.map(defaultHotspot);
  state.activeId = state.hotspots[0].id;
  state.selectedIds = [];
  saveHotspots();
  render();
}

function resetDefaultHotspots() {
  state.hotspots = HOTSPOT_IDS.map(defaultHotspot);
  state.activeId = state.hotspots[0].id;
  state.selectedIds = [];
  saveHotspots();
}

function hasCompleteHotspotSet(value) {
  if (!Array.isArray(value) || value.length !== HOTSPOT_IDS.length) {
    return false;
  }

  const ids = new Set(value.map((item) => Number(item.id)));
  return HOTSPOT_IDS.every((id) => ids.has(id));
}

function normalizeHotspots(value) {
  const byId = new Map(value.map((item) => [Number(item.id), item]));
  return HOTSPOT_IDS.map((id, index) => {
    const current = byId.get(id);
    return {
      ...defaultHotspot(id, index),
      ...current,
      id,
      name: HOTSPOT_WORDS[id] ?? current?.name ?? `音频 ${id}`,
    };
  });
}

function saveHotspots() {
  localStorage.setItem("suno-hotspots", JSON.stringify(state.hotspots));
}

function loadHotspots() {
  const saved = localStorage.getItem("suno-hotspots");
  if (!saved) {
    createDefaultHotspots();
    return;
  }

  try {
    const parsed = JSON.parse(saved);
    if (!hasCompleteHotspotSet(parsed)) {
      createDefaultHotspots();
      return;
    }

    state.hotspots = normalizeHotspots(parsed);
    state.activeId = state.hotspots[0]?.id ?? 11;
    saveHotspots();
  } catch {
    createDefaultHotspots();
  }
}

function getActiveHotspot() {
  return state.hotspots.find((item) => item.id === state.activeId) ?? state.hotspots[0];
}

function setMode(mode) {
  state.mode = mode;
  els.editModeButton.classList.toggle("is-active", mode === "edit");
  els.selectModeButton.classList.toggle("is-active", mode === "select");
  render();
}

function svgPoint(event) {
  const point = els.layer.createSVGPoint();
  point.x = event.clientX;
  point.y = event.clientY;
  return point.matrixTransform(els.layer.getScreenCTM().inverse());
}

function selectHotspot(id, forceSelect = false) {
  state.activeId = id;

  if (forceSelect || state.mode === "select") {
    const index = state.selectedIds.indexOf(id);
    if (index >= 0) {
      state.selectedIds.splice(index, 1);
    } else if (state.selectedIds.length < 4) {
      state.selectedIds.push(id);
    }
    syncVideoPlayback();
  }

  render();
}

function startDrag(event, id, kind) {
  if (state.mode !== "edit") return;
  event.preventDefault();
  event.stopPropagation();

  const hotspot = state.hotspots.find((item) => item.id === id);
  const point = svgPoint(event);
  state.activeId = id;
  state.drag = {
    id,
    kind,
    startX: point.x,
    startY: point.y,
    original: { ...hotspot },
  };
  render();
}

function updateDrag(event) {
  if (!state.drag) return;

  const point = svgPoint(event);
  const hotspot = state.hotspots.find((item) => item.id === state.drag.id);
  const dx = point.x - state.drag.startX;
  const dy = point.y - state.drag.startY;

  if (state.drag.kind === "move") {
    hotspot.x = clamp(state.drag.original.x + dx, 0, 1000);
    hotspot.y = clamp(state.drag.original.y + dy, 0, state.viewHeight);
  }

  if (state.drag.kind === "resize") {
    hotspot.rx = clamp(state.drag.original.rx + dx, 15, 180);
    hotspot.ry = clamp(state.drag.original.ry + dy, 12, 140);
  }

  if (state.drag.kind === "rotate") {
    const angle = Math.atan2(point.y - hotspot.y, point.x - hotspot.x) * 180 / Math.PI;
    hotspot.rotation = Math.round(angle);
  }

  saveHotspots();
  render();
}

function stopDrag() {
  state.drag = null;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function outputPayload() {
  return state.selectedIds.map((id) => {
    const hotspot = state.hotspots.find((item) => item.id === id);
    return {
      id: hotspot.id,
      name: hotspot.name,
      file: hotspot.file,
    };
  });
}

function selectionKey() {
  return state.selectedIds.join("-");
}

function renderLayer(layer = els.layer, options = {}) {
  const { editable = false, selectable = false } = options;
  layer.innerHTML = "";
  layer.setAttribute("viewBox", `0 0 1000 ${state.viewHeight}`);

  for (const hotspot of state.hotspots) {
    const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
    group.classList.add("hotspot");
    group.classList.toggle("is-active", hotspot.id === state.activeId);
    group.classList.toggle("is-selected", state.selectedIds.includes(hotspot.id));
    group.setAttribute("transform", `translate(${hotspot.x} ${hotspot.y}) rotate(${hotspot.rotation})`);
    if (editable) {
      group.addEventListener("pointerdown", (event) => startDrag(event, hotspot.id, "move"));
    }
    group.addEventListener("click", (event) => {
      event.stopPropagation();
      selectHotspot(hotspot.id, selectable);
    });

    const ellipse = document.createElementNS("http://www.w3.org/2000/svg", "ellipse");
    ellipse.setAttribute("rx", hotspot.rx);
    ellipse.setAttribute("ry", hotspot.ry);

    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.textContent = hotspot.id;

    group.append(ellipse, label);

    if (editable && state.mode === "edit" && hotspot.id === state.activeId) {
      const resize = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      resize.classList.add("resize-handle");
      resize.setAttribute("cx", hotspot.rx);
      resize.setAttribute("cy", hotspot.ry);
      resize.setAttribute("r", 9);
      resize.addEventListener("pointerdown", (event) => startDrag(event, hotspot.id, "resize"));

      const rotateLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
      rotateLine.setAttribute("x1", 0);
      rotateLine.setAttribute("y1", -hotspot.ry);
      rotateLine.setAttribute("x2", 0);
      rotateLine.setAttribute("y2", -hotspot.ry - 34);
      rotateLine.setAttribute("stroke", "var(--text)");
      rotateLine.setAttribute("stroke-width", "2");

      const rotate = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      rotate.classList.add("rotate-handle");
      rotate.setAttribute("cx", 0);
      rotate.setAttribute("cy", -hotspot.ry - 34);
      rotate.setAttribute("r", 8);
      rotate.addEventListener("pointerdown", (event) => startDrag(event, hotspot.id, "rotate"));

      group.append(rotateLine, resize, rotate);
    }

    layer.append(group);
  }
}

function renderList() {
  els.hotspotList.innerHTML = "";
  for (const hotspot of state.hotspots) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "hotspot-card";
    button.classList.toggle("is-active", hotspot.id === state.activeId);
    button.classList.toggle("is-selected", state.selectedIds.includes(hotspot.id));
    button.textContent = hotspot.id;
    button.title = `${hotspot.name} - ${hotspot.file}`;
    button.addEventListener("click", () => selectHotspot(hotspot.id));
    els.hotspotList.append(button);
  }
}

function renderSelection() {
  const payload = outputPayload();
  els.selectionCount.textContent = `${payload.length} / 4`;
  els.selectionList.innerHTML = "";

  for (const item of payload) {
    const li = document.createElement("li");
    li.textContent = `${item.id} · ${item.name}`;
    els.selectionList.append(li);
  }

  els.outputBox.textContent = JSON.stringify(payload, null, 2);
}

function syncVideoPlayback() {
  if (!els.video.src) {
    els.playButton.disabled = true;
    els.playButton.textContent = "选择视频后可用";
    return;
  }

  if (state.selectedIds.length === 4) {
    els.playButton.disabled = false;
    els.playButton.textContent = "播放/暂停";
    document.body.classList.add("is-generating");
    requestExperienceFullscreen();
    const video = document.body.classList.contains("editor-active") ? els.video : els.introVideo;
    video.play().catch(() => {
      if (document.body.classList.contains("editor-active")) {
        els.playButton.textContent = "点击播放";
      }
    });
    startGenerationIfNeeded();
    return;
  }

  state.generationKey = "";
  state.generating = false;
  document.body.classList.remove("is-generating");
  els.video.pause();
  els.introVideo.pause();
  els.playButton.disabled = true;
  els.playButton.textContent = "选满 4 个后播放";
  if (Number.isFinite(els.video.duration)) {
    els.video.currentTime = 0;
  }
  if (Number.isFinite(els.introVideo.duration)) {
    els.introVideo.currentTime = 0;
  }
}

async function startGenerationIfNeeded() {
  const key = selectionKey();
  if (!key || state.generating || state.generationKey === key) {
    return;
  }

  state.generating = true;
  state.generationKey = key;
  document.body.classList.add("is-generating");
  els.generationPanel.hidden = false;
  els.generatingError.textContent = "";

  try {
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        items: outputPayload(),
        style: "meditative a cappella, serene vocal ensemble, vocal only, slow breathing harmonies",
        skip_oss: true,
      }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || data.error || "生成失败");
    }

    stopVideoAtFirstFrame();
    playGeneratedAudio(data.song_url);
    showQrModal(data);
  } catch (error) {
    document.body.classList.remove("is-generating");
    stopVideoAtFirstFrame();
    els.generationPanel.hidden = false;
    els.generatingError.textContent = String(error.message || error);
  } finally {
    state.generating = false;
  }
}

function stopVideoAtFirstFrame() {
  els.video.pause();
  els.introVideo.pause();
  if (Number.isFinite(els.video.duration)) {
    els.video.currentTime = 0;
  }
  if (Number.isFinite(els.introVideo.duration)) {
    els.introVideo.currentTime = 0;
  }
}

function playGeneratedAudio(songUrl) {
  if (!songUrl) return;
  els.generatedAudio.src = songUrl;
  els.generatedAudio.currentTime = 0;
  els.generatedAudio.play().catch(() => {});
}

function showQrModal(data) {
  els.qrTitle.textContent = data.title || "扫描下载音频";
  els.qrImage.src = data.qr_data_url;
  els.qrDownloadLink.href = data.qr_url || data.song_url;
  els.referenceAudioLink.href = data.mixed_url || "#";
  els.referenceAudioLink.hidden = !data.mixed_url;
  els.qrModal.hidden = false;
}

function closeQrModal() {
  els.qrModal.hidden = true;
  els.generatedAudio.pause();
  els.generatedAudio.removeAttribute("src");
  els.generatedAudio.load();
  els.generationPanel.hidden = true;
  els.generatingError.textContent = "";
  state.selectedIds = [];
  state.generationKey = "";
  state.generating = false;
  document.body.classList.remove("is-generating");
  stopVideoAtFirstFrame();
  render();
}

function requestExperienceFullscreen() {
  const target = document.querySelector("#introVideoShell");
  if (!target || document.fullscreenElement || document.webkitFullscreenElement) {
    return;
  }

  if (target.requestFullscreen) {
    target.requestFullscreen().catch(() => {});
  } else if (target.webkitRequestFullscreen) {
    target.webkitRequestFullscreen();
  }
}

function syncVideoFrame() {
  if (!state.videoUrl) return;

  els.video.pause();
  els.introVideo.pause();
  if (Number.isFinite(els.video.duration)) {
    els.video.currentTime = 0;
  }
  if (Number.isFinite(els.introVideo.duration)) {
    els.introVideo.currentTime = 0;
  }
}

function updateVideoAspect(video) {
  if (!video.videoWidth || !video.videoHeight) return;

  const aspect = video.videoWidth / video.videoHeight;
  state.viewHeight = 1000 / aspect;
  const ratio = `${video.videoWidth} / ${video.videoHeight}`;
  document.querySelector("#videoFrame").style.aspectRatio = ratio;
  syncVideoPlayback();
  render();
}

function setVideoSource(file) {
  if (!file) return;

  if (!hasCompleteHotspotSet(state.hotspots)) {
    state.hotspots = HOTSPOT_IDS.map(defaultHotspot);
    state.activeId = state.hotspots[0].id;
    saveHotspots();
  }

  if (state.videoUrl) {
    URL.revokeObjectURL(state.videoUrl);
  }

  state.videoUrl = URL.createObjectURL(file);
  els.video.src = state.videoUrl;
  els.introVideo.src = state.videoUrl;
  els.video.muted = false;
  els.introVideo.muted = false;
  els.video.volume = 1;
  els.introVideo.volume = 1;
  els.emptyState.style.display = "none";
  els.introEmpty.style.display = "none";
  els.introScreen.classList.add("has-video");
  syncVideoPlayback();
  render();
}

function renderEditor() {
  const hotspot = getActiveHotspot();
  if (!hotspot) return;

  els.idInput.value = hotspot.id;
  els.nameInput.value = hotspot.name;
  els.fileInput.value = hotspot.file;
  els.widthInput.value = (hotspot.rx / 10).toFixed(1);
  els.heightInput.value = (hotspot.ry / (state.viewHeight / 100)).toFixed(1);
  els.rotationInput.value = hotspot.rotation;
}

function render() {
  if (!hasCompleteHotspotSet(state.hotspots)) {
    resetDefaultHotspots();
  }

  renderLayer(els.introLayer, { selectable: true });
  renderLayer(els.layer, { editable: state.mode === "edit", selectable: state.mode === "select" });
  renderList();
  renderSelection();
  renderEditor();
}

function updateActiveHotspot(patch) {
  const hotspot = getActiveHotspot();
  Object.assign(hotspot, patch);
  saveHotspots();
  render();
}

function exportConfig() {
  const blob = new Blob([JSON.stringify(state.hotspots, null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "suno-hotspots.json";
  link.click();
  URL.revokeObjectURL(link.href);
}

els.videoInput.addEventListener("change", () => {
  const file = els.videoInput.files[0];
  setVideoSource(file);
});

els.introVideoInput.addEventListener("change", () => {
  const file = els.introVideoInput.files[0];
  setVideoSource(file);
});

els.enterEditorButton.addEventListener("click", () => {
  document.body.classList.add("editor-active");
  setMode("edit");
  syncVideoFrame();
  render();
});

els.playButton.addEventListener("click", async () => {
  if (!els.video.src || state.selectedIds.length < 4) return;

  if (els.video.paused) {
    await els.video.play();
  } else {
    els.video.pause();
  }
});

els.qrCloseButton.addEventListener("click", closeQrModal);

els.qrModal.addEventListener("click", (event) => {
  if (event.target === els.qrModal) {
    closeQrModal();
  }
});

els.video.addEventListener("loadedmetadata", () => {
  updateVideoAspect(els.video);
  syncVideoFrame();
});

els.introVideo.addEventListener("loadedmetadata", () => {
  updateVideoAspect(els.introVideo);
  syncVideoFrame();
});

els.importInput.addEventListener("change", async () => {
  const file = els.importInput.files[0];
  if (!file) return;

  const text = await file.text();
  state.hotspots = JSON.parse(text);
  state.activeId = state.hotspots[0]?.id ?? 11;
  state.selectedIds = [];
  saveHotspots();
  render();
});

els.editModeButton.addEventListener("click", () => setMode("edit"));
els.selectModeButton.addEventListener("click", () => setMode("select"));
els.createButton.addEventListener("click", createDefaultHotspots);
els.clearSelectionButton.addEventListener("click", () => {
  state.selectedIds = [];
  syncVideoPlayback();
  render();
});
els.exportButton.addEventListener("click", exportConfig);

els.nameInput.addEventListener("input", () => updateActiveHotspot({ name: els.nameInput.value }));
els.fileInput.addEventListener("input", () => updateActiveHotspot({ file: els.fileInput.value }));
els.widthInput.addEventListener("input", () => updateActiveHotspot({ rx: Number(els.widthInput.value) * 10 }));
els.heightInput.addEventListener("input", () => updateActiveHotspot({ ry: Number(els.heightInput.value) * (state.viewHeight / 100) }));
els.rotationInput.addEventListener("input", () => updateActiveHotspot({ rotation: Number(els.rotationInput.value) }));

window.addEventListener("pointermove", updateDrag);
window.addEventListener("pointerup", stopDrag);

loadHotspots();
syncVideoPlayback();
render();
