// audio-rating.js (modified to add zoom controls & visible-range mapping)
// Class-based widget that encapsulates all logic and can be instantiated multiple times.
// Uses WaveSurfer 7 via dynamic import (cached per session) for convenience.

import TimelinePlugin from 'https://unpkg.com/wavesurfer.js@7.0.0/dist/plugins/timeline.esm.js';

export class AudioRatingWidget {
  static _WaveSurfer = null;

  static async create(options) {
    const widget = new AudioRatingWidget(options);
    await widget._init();
    return widget;
  }

  constructor({
    container,
    audioUrl,
    dimensions = {
      valence:   { num_values: 10 },
      arousal:   { num_values:  5 },
      enjoyment: { num_values: 10 },
      is_cool:   { num_values:  2 },
    },
    height = 140,
    waveColor = '#bfc8d6',
    progressColor = '#6b46c1',
    scrollParent = true,
    with_instructions = true, // whether to show instructions
    with_volume_slider = true, // whether to show volume slider
    with_step_labels_legend = true, // whether to show step labels under rating scales
    show_download_button = true, // whether to show download button
    title = "Please rate this song", // Title for widget, displayed at top.
  } = {}) {
    this.container = (typeof container === 'string')
      ? document.querySelector(container)
      : container;
    if (!this.container) throw new Error('AudioRatingWidget: container not found');

    this.audioUrl = audioUrl;
    this.dimensionDefinition = this._normalizeDimensions(dimensions);
    this.CANVAS_HEIGHT = height;
    this.waveColor = waveColor;
    this.progressColor = progressColor;
    this.scrollParent = scrollParent;
    this.with_instructions = with_instructions;
    this.with_volume_slider = with_volume_slider;
    this.with_step_labels_legend = with_step_labels_legend;
    this.show_download_button = show_download_button;
    this.title = title;

    // State
    this.dimensionData = {};
    this.currentDimension = Object.keys(this.dimensionDefinition)[0];
    this.segments = null;

    // Drawing helpers / runtime
    this.renderLoop = null;
    this.pointerDown = false;
    this.activeSegIndex = null;
    this.activeHandle = null;
    this.lastPointerX = 0;
    this.lastPointerY = 0;
    this.HANDLE_HIT = 8;

    // DOM refs (filled in _buildDOM)
    this.root = null;
    this.dimButtonsWrap = null;
    this.waveformEl = null;
    this.overlay = null;
    this.ctx = null;
    this.stepsLabel = null;
    this.legend = null;
    this.playBtn = null;
    this.stopBtn = null;
    this.statusEl = null;
    this.timeSlider = null;

    // WaveSurfer instance
    this.wavesurfer = null;

    // ZOOM state
    this._zoomFactor = 1.5; // multiplier per zoom click
    this._currentPxPerSec = null; // null means default (unzoomed)
    this._defaultMinPxPerSec = null;
    this.visibleStart = 0; // seconds - start of currently visible window
    this.visibleEnd = null; // seconds - end of currently visible window
  }

  async _init() {
    if (!AudioRatingWidget._WaveSurfer) {
      const mod = await import('https://unpkg.com/wavesurfer.js@7.0.0/dist/wavesurfer.esm.js');
      AudioRatingWidget._WaveSurfer = mod.default;
    }

    this._buildDOM();
    this._initData();
    this._bindUI();
    await this._initWaveSurfer();
    this._updateLegend(this.dimensionDefinition[this.currentDimension].num_values);
    this._updateActiveButton();
    // Initial resize after layout
    setTimeout(() => this._resizeOverlay(), 300);
  }

  _normalizeDimensions(input) {
    // Accept { name: number } or { name: { num_values } }
    const out = {};
    for (const [k, v] of Object.entries(input)) {
      out[k] = (typeof v === 'number') ? { num_values: v } : v;
    }
    return out;
  }

  _buildDOM() {
    // Build widget structure inside container
    this.container.classList.add('arw-host');

    const root = document.createElement('div');
    root.className = 'arw';
    root.tabIndex = 0; // allow focus for spacebar handling

    // Conditionally show instructions based on with_instructions
    const titleHtml = "<div class='arw-title'>" + this.title + "</div>";

    // Create the main HTML structure in one go
    root.innerHTML = `
    ${titleHtml}
    ${this.with_instructions ? '<div class="arw-info"><span class="arw-dimensions-manual">Select the dimension to rate:</span></div>' : ''}

    <div class="arw-dimension-buttons"></div>

    ${this.with_instructions ? '<div class="arw-info"><span class="arw-ratings-manual">Rating Controls: Please split the audio into segments and rate each segment. Double-click on the waveform to split a segment. Drag inside a segment vertically to change its rating. Drag segment boundaries horizontally to move them. Right-click a segment boundary to delete it.</span></div>' : ''}

    <div class="arw-container">
        <div class="arw-waveform"></div>
        <canvas class="arw-overlay"></canvas>
    </div>

    <div class="arw-controls">

        ${this.show_download_button ? '' : '<style>.arw-export { display: none; }</style>'}

        ${this.with_step_labels_legend ?
        '<label>Step levels: <strong class="arw-steps-label"></strong></label><div class="arw-legend"></div>' : ''}
        <button class="arw-export">Download CSV</button>
    </div>

    ${this.with_instructions ? '<div class="arw-info"><span class="arw-audio-manual">Audio Controls: Click the buttons below or press the space key to toggle Play/Pause. Click or drag the slider below to seek.</span></div>' : ''}

    <div class="arw-zoom-controls">
        <button class="arw-zoom-in" type="button">Zoom +</button>
        <button class="arw-zoom-out" type="button">Zoom −</button>
        <button class="arw-zoom-reset" type="button">Reset Zoom</button>
    </div>

    <div class="arw-slider">
        <input type="range" class="arw-time-slider" min="0" max="1" step="0.001" value="0">
    </div>

    <div class="arw-audio-controls">
        <button class="arw-play">Play</button>
        <button class="arw-stop">Stop</button>
        ${this.with_volume_slider ? `
        <div class="arw-volume-control">
            <label>Volume: </label>
            <input type="range" class="arw-volume-slider" min="0" max="1" step="0.01" value="1">
        </div>
        ` : ''}
    </div>

    <div class="arw-info">
        <span class="arw-status">Loading...</span>
    </div>
    `;

    this.container.appendChild(root);

    // Refs
    this.root = root;
    this.dimButtonsWrap = root.querySelector('.arw-dimension-buttons');
    this.waveformEl = root.querySelector('.arw-waveform');
    this.overlay = root.querySelector('.arw-overlay');
    this.ctx = this.overlay.getContext('2d');
    this.stepsLabel = root.querySelector('.arw-steps-label');
    this.legend = root.querySelector('.arw-legend');
    this.playBtn = root.querySelector('.arw-play');
    this.stopBtn = root.querySelector('.arw-stop');
    this.statusEl = root.querySelector('.arw-status');
    this.timeSlider = root.querySelector('.arw-time-slider');

    // Zoom buttons
    this.zoomInBtn = root.querySelector('.arw-zoom-in');
    this.zoomOutBtn = root.querySelector('.arw-zoom-out');
    this.zoomResetBtn = root.querySelector('.arw-zoom-reset');

    // Build dimension buttons
    for (const name of Object.keys(this.dimensionDefinition)) {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = name;
      b.dataset.dim = name;
      this.dimButtonsWrap.appendChild(b);
    }
}


  _initData() {
    const segmentsDefault = (num_values) => [{
      start: 0,
      end: 1e9,
      value: Math.floor(num_values / 2),
    }];

    for (const dim of Object.keys(this.dimensionDefinition)) {
      this.dimensionData[dim] = segmentsDefault(this.dimensionDefinition[dim].num_values);
    }
    this.segments = this.dimensionData[this.currentDimension];
  }

  _updateZoomButtonStates() {
    if (!this.wavesurfer) return;

    const currentZoom = this._currentPxPerSec || this._defaultMinPxPerSec || 100;
    const defaultZoom = this._defaultMinPxPerSec || 100;

    // Disable zoom out if we're at or below default zoom level
    this.zoomOutBtn.disabled = (currentZoom <= defaultZoom * 1.05);
  }

  async _initWaveSurfer() {
    const WaveSurfer = AudioRatingWidget._WaveSurfer;

    const topTimeline = TimelinePlugin.create({
      height: 20,
      insertPosition: 'beforebegin',
      timeInterval: 0.2,
      primaryLabelInterval: 5,
      secondaryLabelInterval: 1,
      style: {
        fontSize: '20px',
        color: '#2D5B88',
      },
    })

    this.wavesurfer = WaveSurfer.create({
      container: this.waveformEl,
      waveColor: this.waveColor,
      progressColor: this.progressColor,
      height: this.CANVAS_HEIGHT,
      scrollParent: this.scrollParent,
      plugins: [topTimeline],
    });

    // Store default minPxPerSec for reset purposes
    this._defaultMinPxPerSec = this.wavesurfer.params?.minPxPerSec ?? null;

    // Volume control
    if (this.with_volume_slider) {
        const volumeSlider = this.root.querySelector('.arw-volume-slider');
        volumeSlider.addEventListener('input', (e) => {
            const volume = parseFloat(e.target.value);
            this.wavesurfer.setVolume(volume);
        });

        // Set initial volume
        this.wavesurfer.setVolume(1);
    }

    if (!this.audioUrl) throw new Error('AudioRatingWidget: audioUrl is required');
    this.wavesurfer.load(this.audioUrl);

    // Keep track of visible window: wavesurfer v7 emits 'scroll' with (visibleStartTime, visibleEndTime, scrollLeft, scrollRight)
    this.wavesurfer.on('scroll', (visibleStartTime, visibleEndTime) => {
      // visibleStartTime and visibleEndTime are in seconds (per docs)
      this.visibleStart = (typeof visibleStartTime === 'number') ? visibleStartTime : 0;
      this.visibleEnd = (typeof visibleEndTime === 'number') ? visibleEndTime : this._durationOrOne();
      this._drawAll();
    });

    this.wavesurfer.on('ready', () => {
        const duration = this.wavesurfer.getDuration();
        for (const dim in this.dimensionData) {
            this.dimensionData[dim].forEach((s) => {
            if (s.end > duration) s.end = duration;
            });
        }

        // At ready, visible window should be full duration unless zoom changes it
        this.visibleStart = 0;
        this.visibleEnd = duration || this._durationOrOne();

        this._resizeOverlay();
        this._updateStatus(); // Update status immediately when ready
        this.wavesurfer.isReady = true;
        this._startRenderLoop();
        this.timeSlider.max = duration;

        // Ensure default px/sec captured after decode/draw
        this._defaultMinPxPerSec = this.wavesurfer.params?.minPxPerSec ?? this._defaultMinPxPerSec;
        this._updateZoomButtonStates();
    });

    this.wavesurfer.on('finish', () => {
      this.playBtn.textContent = 'Play';
    });

    // Button state driven by real events
    this.wavesurfer.on('play', () => { this.playBtn.textContent = 'Pause'; });
    this.wavesurfer.on('pause', () => { this.playBtn.textContent = 'Play'; });

    // Update current time during playback
    this.wavesurfer.on('timeupdate', () => {
      this._updateStatus();
    });

    // Keep UI when zoom changes
    this.wavesurfer.on('zoom', (minPxPerSec) => {
      // update our cached current px/sec
      this._currentPxPerSec = (minPxPerSec || null);
      // wavesurfer will usually emit a 'scroll' event after zooming; ensure we redraw
      this._drawAll();
      this._updateZoomButtonStates();
    });
  }

  _updateStatus() {
    if (this.wavesurfer && this.wavesurfer.isReady) {
        const duration = this.wavesurfer.getDuration();
        const currentTime = this.wavesurfer.getCurrentTime();
        this.statusEl.textContent = `Current: ${currentTime.toFixed(2)}s / Total: ${duration.toFixed(2)}s`;
    } else {
        this.statusEl.textContent = '';
    }
    }

  _bindUI() {
    // Resize
    this._onResize = () => { setTimeout(() => this._resizeOverlay(), 120); };
    window.addEventListener('resize', this._onResize);

    // Play / Stop buttons
    this.playBtn.addEventListener('click', () => { this.wavesurfer.playPause(); });
    this.stopBtn.addEventListener('click', () => { this.wavesurfer.stop(); this.playBtn.textContent = 'Play'; });

    // Spacebar handling (only when widget (root) is focused)
    this._onKeyDown = (ev) => {
      const tag = document.activeElement?.tagName;
      const inTextInput = tag === 'INPUT' || tag === 'TEXTAREA';
      if (inTextInput) return;
      if (ev.code === 'Space' && (document.activeElement === this.root || this.root.contains(document.activeElement))) {
        ev.preventDefault();
        this.wavesurfer.playPause();
      }
    };
    window.addEventListener('keydown', this._onKeyDown);

    // Slider seeking
    this.timeSlider.addEventListener('input', () => {
      const t = parseFloat(this.timeSlider.value);
      this._seekToTime(t);
    });

    // Export CSV
    this.root.querySelector('.arw-export').addEventListener('click', () => this._exportCSV());

    // Dimension buttons
    this.dimButtonsWrap.querySelectorAll('button').forEach((btn) => {
      btn.addEventListener('click', () => {
        this.dimensionData[this.currentDimension] = JSON.parse(JSON.stringify(this.segments));
        this.currentDimension = btn.dataset.dim;
        this.segments = this.dimensionData[this.currentDimension];
        this._updateLegend(this.dimensionDefinition[this.currentDimension].num_values);
        this._updateActiveButton();
        this._drawAll();
      });
    });

    // Zoom buttons
    this.zoomInBtn.addEventListener('click', () => this._zoomIn());
    this.zoomOutBtn.addEventListener('click', () => this._zoomOut());
    this.zoomResetBtn.addEventListener('click', () => this._resetZoom());

    // Overlay pointer interactions
    this.overlay.addEventListener('pointerdown', (ev) => this._onPointerDown(ev));
    this.overlay.addEventListener('pointermove', (ev) => this._onPointerMove(ev));
    this.overlay.addEventListener('pointerup',   (ev) => this._onPointerUp(ev));
    this.overlay.addEventListener('dblclick',    (ev) => this._onDblClick(ev));
    this.overlay.addEventListener('contextmenu', (ev) => this._onContextMenu(ev));
  }

  // ===== Drawing & layout =====

_resizeOverlay() {
  const rect = this.waveformEl.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;

  // Adjust height to leave 16px at the bottom for scrollbar
  const overlayHeight = this.CANVAS_HEIGHT - 16;

  this.overlay.style.width  = `${Math.max(100, rect.width)}px`;
  this.overlay.style.height = `${overlayHeight}px`;

  this.overlay.width  = Math.max(100, Math.round(rect.width * dpr));
  this.overlay.height = Math.round(overlayHeight * dpr);

  this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  this._drawAll();
}

  _startRenderLoop() {
    if (this.renderLoop) cancelAnimationFrame(this.renderLoop);
    const loop = () => { this._drawAll(); this.renderLoop = requestAnimationFrame(loop); };
    this.renderLoop = requestAnimationFrame(loop);
  }

  _stopRenderLoop() {
    if (this.renderLoop) cancelAnimationFrame(this.renderLoop);
    this.renderLoop = null;
  }

  _durationOrOne() {
    const d = this.wavesurfer.getDuration();
    return (d && isFinite(d)) ? d : 1;
  }

  /* ZOOM: time <-> x mapping now uses the current visible start/end window (in seconds).
     This ensures segments (which store absolute seconds) remain correct when zoomed or scrolled. */

     _timeToX(time) {
  if (!this.wavesurfer) return 0;
  const duration = this._durationOrOne();
  const wrapper = this.wavesurfer.getWrapper();
  const scroll = wrapper.scrollLeft || 0;
  const totalWidth = wrapper.scrollWidth || wrapper.clientWidth || this.overlay.width;
  const globalX = (time / duration) * totalWidth;
  const x = globalX - scroll;
  // clamp in case of small floating point drift or transient values
  return Math.max(-10000, Math.min(10000, x));
}

_xToTime(x) {
  if (!this.wavesurfer) return 0;

  const duration = this._durationOrOne();
  const wrapper = this.wavesurfer.getWrapper();
  const scroll = wrapper.scrollLeft;
  const visibleWidth = wrapper.clientWidth;
  const totalWidth = wrapper.scrollWidth;

  const globalX = x + scroll;
  const time = (globalX / totalWidth) * duration;

  return time;
}


  _findSegmentIndexAtTime(time) {
    for (let i = 0; i < this.segments.length; i++) {
      if (this.segments[i].start <= time && time <= this.segments[i].end) return i;
    }
    return -1;
  }

  _colorForRating(r, num_values) {
    const t = r / ((num_values - 1) || 1);
    const hue = 220 - (220 - 10) * t;
    return `hsl(${hue} 80% 50% / 0.45)`;
  }

  _updateLegend(num_values) {
    if(this.legend == null) return;
    this.legend.innerHTML = '';
    for (let r = num_values - 1; r >= 0; r--) {
      const item = document.createElement('div');
      item.className = 'legend-item';
      item.style.background = this._colorForRating(r, num_values).replace('/ 0.45)', '/1)');
      item.textContent = r;
      this.legend.appendChild(item);
    }
    this.stepsLabel.textContent = String(num_values);
  }

  _updateActiveButton() {
    this.dimButtonsWrap.querySelectorAll('button').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.dim === this.currentDimension);
    });
  }

  _drawAll() {
    const ctx = this.ctx;
    const h = this.overlay.height / (window.devicePixelRatio || 1); // CSS pixels
    const w = this.overlay.width / (window.devicePixelRatio || 1);
    const num_steps = this.dimensionDefinition[this.currentDimension].num_values;


    ctx.clearRect(0, 0, w, h);

    // horizontal grid + labels
    for (let s = 0; s < num_steps; s++) {
      const y = h - (s / (num_steps - 1)) * h;
      ctx.beginPath();
      ctx.moveTo(0, y); ctx.lineTo(w, y);
      ctx.lineWidth = (s === Math.floor((num_steps - 1) / 2)) ? 1.2 : 0.7;
      ctx.strokeStyle = 'rgba(0,0,0,0.06)';
      ctx.stroke();
      ctx.fillStyle = 'rgba(0,0,0,0.6)';
      ctx.font = '12px system-ui, Arial';
      ctx.fillText(String(s), 6, Math.max(12, y - 4));
    }

    const marginRight = 0;

    // segments
    this.segments.forEach((seg, idx) => {
      const x1 = this._timeToX(seg.start);
      const x2 = Math.min(this._timeToX(seg.end), w - marginRight);
      const heightFromTop = (1 - (seg.value / (num_steps - 1))) * h;
      const color = this._colorForRating(seg.value, num_steps);
      ctx.fillStyle = color;
      ctx.fillRect(x1, heightFromTop, Math.max(2, x2 - x1), h - heightFromTop);
      ctx.strokeStyle = 'rgba(0,0,0,0.08)';
      ctx.lineWidth = 1;
      ctx.strokeRect(x1 + 0.5, heightFromTop + 0.5, Math.max(1, x2 - x1 - 1), h - heightFromTop - 1);
      ctx.fillStyle = 'rgba(0,0,0,0.85)';
      ctx.font = '12px system-ui, Arial';
      ctx.fillText(`${seg.value}`, x1 + 6, Math.max(12, heightFromTop + 12));

      if (idx > 0) {
        const hx = x1;
        ctx.fillStyle = 'rgba(0,0,0,0.6)';
        ctx.fillRect(hx - 1, 0, 2, h);
      }
    });


    // update slider
    if (this.wavesurfer) this.timeSlider.value = this.wavesurfer.getCurrentTime();
  }

  // ===== Interactions =====

  _hitTestHandle(x) {
    for (let i = 1; i < this.segments.length; i++) {
      const bx = this._timeToX(this.segments[i].start);
      if (Math.abs(bx - x) <= this.HANDLE_HIT) return { i };
    }
    return null;
  }

  _onPointerDown(ev) {
    ev.preventDefault();
    const rect = this.overlay.getBoundingClientRect();
    const x = ev.clientX - rect.left;
    const y = ev.clientY - rect.top;
    this.lastPointerX = x;
    this.lastPointerY = y;
    this.pointerDown = true;

    const handle = this._hitTestHandle(x);
    if (handle) {
      this.activeHandle = { index: handle.i, startSeg: handle.i - 1, endSeg: handle.i };
      this.overlay.setPointerCapture(ev.pointerId);
      return;
    }

    const time = this._xToTime(x);
    const si = this._findSegmentIndexAtTime(time);
    if (si >= 0) {
      this.activeSegIndex = si;
      this.overlay.setPointerCapture(ev.pointerId);
    }
    this._drawAll();
  }

  _onPointerMove(ev) {
    if (!this.pointerDown) return;
    const rect = this.overlay.getBoundingClientRect();
    const x = ev.clientX - rect.left;
    const y = ev.clientY - rect.top;
    this.lastPointerX = x;
    this.lastPointerY = y;

    if (this.activeHandle) {
      const time = this._xToTime(x);
      const leftSeg = this.segments[this.activeHandle.startSeg];
      const rightSeg = this.segments[this.activeHandle.endSeg];
      const epsilon = 0.02;
      const newBoundary = Math.max(leftSeg.start + epsilon, Math.min(rightSeg.end - epsilon, time));
      leftSeg.end = newBoundary;
      rightSeg.start = newBoundary;
      this._drawAll();
      return;
    }

    if (this.activeSegIndex != null) {
      const seg = this.segments[this.activeSegIndex];
      const h = this.overlay.height;
      const ratio = 1 - (y / h);
      let raw = Math.round(ratio * (this.dimensionDefinition[this.currentDimension].num_values - 1));
      raw = Math.max(0, Math.min(this.dimensionDefinition[this.currentDimension].num_values - 1, raw));
      seg.value = raw;
      this._drawAll();
      return;
    }
  }

  _onPointerUp(ev) {
    this.pointerDown = false;
    this.activeSegIndex = null;
    this.activeHandle = null;
    try { this.overlay.releasePointerCapture(ev.pointerId); } catch {}
    this._drawAll();
  }

  _onDblClick(ev) {
    ev.preventDefault();
    const rect = this.overlay.getBoundingClientRect();
    const x = ev.clientX - rect.left;
    const time = this._xToTime(x);
    const si = this._findSegmentIndexAtTime(time);
    if (si === -1) return;
    const seg = this.segments[si];
    const MIN_SEG = 0.08;
    if ((time - seg.start) < MIN_SEG || (seg.end - time) < MIN_SEG) return;
    const right = { start: time, end: seg.end, value: seg.value };
    seg.end = time;
    this.segments.splice(si + 1, 0, right);
    this._drawAll();
  }

  _onContextMenu(ev) {
    ev.preventDefault();
    const rect = this.overlay.getBoundingClientRect();
    const x = ev.clientX - rect.left;
    const handle = this._hitTestHandle(x);
    if (handle) {
      const i = handle.i;
      const left = this.segments[i - 1];
      const right = this.segments[i];
      left.end = right.end;
      this.segments.splice(i, 1);
      this._drawAll();
    }
  }

  // ===== Helpers =====

  _seekToTime(t) {
    // wavesurfer.seekTo expects a percentage of the total duration
    this.wavesurfer.seekTo(t / this._durationOrOne());
  }

  _exportCSV() {
    let csv = 'data:text/csv;charset=utf-8,dimension,start,end,value\n';
    for (const dim in this.dimensionData) {
      this.dimensionData[dim].forEach((seg) => {
        csv += `${dim},${seg.start.toFixed(2)},${seg.end.toFixed(2)},${seg.value}\n`;
      });
    }
    const encoded = encodeURI(csv);
    const link = document.createElement('a');
    link.setAttribute('href', encoded);
    link.setAttribute('download', 'ratings.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  // ===== ZOOM methods =====

  _zoomIn() {
  if (!this.wavesurfer?.zoom) return;

  // Re-enable zoom out button when zooming in
  this.zoomOutBtn.disabled = false;

  // compute next px/sec
  const base = this._currentPxPerSec || this._defaultMinPxPerSec || 100;
  const next = base * this._zoomFactor;
  this._currentPxPerSec = next;
  this.wavesurfer.zoom(next);
  this._updateZoomButtonStates();
  setTimeout(() => this._resizeOverlay(), 50);
}

  _zoomOut() {
    if (!this.wavesurfer?.zoom) return;

    // Get current zoom level and default
    const currentZoom = this._currentPxPerSec || this._defaultMinPxPerSec || 100;
    const defaultZoom = this._defaultMinPxPerSec || 100;

    // Calculate what the next zoom level would be
    const nextZoom = currentZoom / this._zoomFactor;

    // If we're already at or below default zoom, or the next zoom would be too small, don't zoom
    // Add a small threshold to account for floating point precision
    if (currentZoom <= defaultZoom * 1.05) {
      // Already at minimum zoom - disable button visually and do nothing
      this.zoomOutBtn.disabled = true;
      return;
    }

    // If next zoom would be close to or below default, reset to default instead
    if (nextZoom <= defaultZoom * 1.05) {
      this._resetZoom();
      return;
    }

    this._currentPxPerSec = nextZoom;
    this.wavesurfer.zoom(nextZoom);
    this._updateZoomButtonStates();
    setTimeout(() => this._resizeOverlay(), 50);
  }

  _resetZoom() {
  if (!this.wavesurfer?.zoom) return;

  // Reset zoom out button to enabled state
  this.zoomOutBtn.disabled = false;

  // Passing a falsy value resets zoom per wavesurfer API.
  this._currentPxPerSec = null;
  this.wavesurfer.zoom(null);
  // Reset visible window to full duration to sync overlay mapping
  this.visibleStart = 0;
  this.visibleEnd = this._durationOrOne();
  this._drawAll();
  this._updateZoomButtonStates();
  setTimeout(() => this._resizeOverlay(), 50);
}  // ===== Public API =====

  getData() {
    return JSON.parse(JSON.stringify(this.dimensionData));
  }

  setData(data) {
    this.dimensionData = JSON.parse(JSON.stringify(data));
    this.segments = this.dimensionData[this.currentDimension];
    this._drawAll();
  }

  destroy() {
    // Clean up listeners and RAF
    window.removeEventListener('resize', this._onResize);
    window.removeEventListener('keydown', this._onKeyDown);
    this._stopRenderLoop();

    // Destroy WaveSurfer
    try { this.wavesurfer?.destroy(); } catch {}

    // Remove DOM
    this.root?.remove();
  }
}
// End of audio-rating.js
