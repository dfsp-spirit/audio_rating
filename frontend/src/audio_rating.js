// audio-rating.js (modified to add zoom controls & visible-range mapping)
// Class-based widget that encapsulates all logic and can be instantiated multiple times.
// Uses WaveSurfer 7 via dynamic import (cached per session) for convenience.

import TimelinePlugin from './timeline.esm.js';
import i18n from './i18n.js';

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
    rating_dimensions = [],
    //rating_dimensions = [{"dimension_title": "Musical aesthetics", "num_values": 5, "description": "How artistically compelling the music itself is in this section (ideas, harmony, melody, texture, form), independent of minor execution issues."}, {"dimension_title": "Performance quality", "num_values": 5, "description": "How well the music is executed in this section (timing, touch, dynamics, articulation, control/fluency), relative to the performer’s intent."}, {"dimension_title": "Togetherness", "num_values": 5, "description": "The sense of real-time musical connection: mutual responsiveness (give-and-take), shared pulse/phrasing, and a feeling of being with the partner rather than alongside them."}, {"dimension_title": "Flow", "num_values": 5, "description": "Feeling fully absorbed and engaged during this section - deeply focused but positive challenge."}, {"dimension_title": "Lead-follow", "num_values": 5, "description": "Who is currently driving the musical direction (entries, tempo/pulse, phrasing, harmonic turns, density), as perceived in this section."}],
    height = 140,
    waveColor = '#bfc8d6',
    progressColor = '#6b46c1',
    scrollParent = true,
    with_instructions = true, // whether to show instructions
    with_volume_slider = true, // whether to show volume slider
    with_step_labels_legend = true, // whether to show step labels under rating scales
    show_download_button = true, // whether to show download button
    title = 'Please rate this song', // Title for widget, displayed at top.
  } = {}) {
    this.container =
      typeof container === 'string'
        ? document.querySelector(container)
        : container;
    if (!this.container)
      throw new Error('AudioRatingWidget: container not found');

    this.audioUrl = audioUrl;
    this.rating_dimensions = rating_dimensions;
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
    this.currentDimension = rating_dimensions[0]?.dimension_title || null;
    this.segments = null;

    // Drawing helpers / runtime
    this.renderLoop = null;
    this.pointerDown = false;
    this.activeSegIndex = null;
    this.activeHandle = null;
    this.keyboardSegIndex = null;
    this.lastPointerX = 0;
    this.lastPointerY = 0;
    this.HANDLE_HIT = 8;
    this.hoverSegIndex = null;
    this.hoverHandleIndex = null;
    this.hoverPointerX = 0;
    this.hoverPointerY = 0;

    // Long-press-to-delete state (works for both mouse and touch)
    this.LONG_PRESS_DURATION = 1200; // ms to hold on a handle to delete it
    this.LONG_PRESS_VISUAL_DELAY = 400; // ms grace before the red arc appears
    this.LONG_PRESS_MOVE_PX = 6; // px of movement that cancels the press
    this._longPressTimer = null;
    this._longPressHandleI = null;
    this._longPressStartTime = 0;
    this._longPressStartX = 0;
    this._longPressStartY = 0;

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
    this.volumeSlider = null;

    // WaveSurfer instance
    this.wavesurfer = null;

    // ZOOM state
    this._zoomFactor = 1.5; // multiplier per zoom click
    this._currentPxPerSec = null; // null means default (unzoomed)
    this._defaultMinPxPerSec = null;
    this.visibleStart = 0; // seconds - start of currently visible window
    this.visibleEnd = null; // seconds - end of currently visible window
    this._lastTimelineDensityKey = null;

    // Event system
    this._listeners = {
      change: [], // Single 'change' event for any modification
    };
  }

  t(key, params = {}) {
    return i18n.t(key, params);
  }

  _getPlayPauseShortcutHint() {
    return this.t('widget.playPauseShortcutHint');
  }

  _getStopShortcutHint() {
    return this.t('widget.stopShortcutHint');
  }

  _updatePlayButtonA11y() {
    if (!this.playBtn) return;
    const isPlaying = this.wavesurfer && this.wavesurfer.isPlaying();
    const actionLabel = isPlaying
      ? this.t('widget.pause')
      : this.t('widget.play');
    const shortcutHint = this._getPlayPauseShortcutHint();
    const combined = `${actionLabel} — ${shortcutHint}`;
    this.playBtn.removeAttribute('title');
    this.playBtn.setAttribute('aria-label', combined);
    this.playBtn.setAttribute('data-hint', shortcutHint);
  }

  _updateStopButtonA11y() {
    if (!this.stopBtn) return;
    const actionLabel = this.t('widget.stop');
    const shortcutHint = this._getStopShortcutHint();
    const combined = `${actionLabel} — ${shortcutHint}`;
    this.stopBtn.removeAttribute('title');
    this.stopBtn.setAttribute('aria-label', combined);
    this.stopBtn.setAttribute('data-hint', shortcutHint);
  }

  _stopPlaybackToStart() {
    if (!this.wavesurfer) return;
    this.wavesurfer.stop();
    if (this.playBtn) {
      this.playBtn.textContent = this.t('widget.play');
    }
    this._updatePlayButtonA11y();
    this._updateStopButtonA11y();
  }

  _getSelectedSegmentIndex() {
    if (!Array.isArray(this.segments) || this.segments.length === 0)
      return null;
    if (
      this.keyboardSegIndex == null ||
      this.keyboardSegIndex < 0 ||
      this.keyboardSegIndex >= this.segments.length
    ) {
      this.keyboardSegIndex = 0;
    }
    return this.keyboardSegIndex;
  }

  _setSelectedSegmentIndex(index) {
    if (!Array.isArray(this.segments) || this.segments.length === 0) {
      this.keyboardSegIndex = null;
      return;
    }
    this.keyboardSegIndex = Math.max(
      0,
      Math.min(this.segments.length - 1, index)
    );
  }

  _splitSelectedSegmentAtMidpoint() {
    const si = this._getSelectedSegmentIndex();
    if (si == null) return;

    const seg = this.segments[si];
    const midpoint = (seg.start + seg.end) / 2;
    const minSeg = 0.08;
    if (midpoint - seg.start < minSeg || seg.end - midpoint < minSeg) return;

    const right = { start: midpoint, end: seg.end, value: seg.value };
    seg.end = midpoint;
    this.segments.splice(si + 1, 0, right);
    this._drawAll();
    this._emitChange('segment_added');
  }

  _deleteSelectedSegmentRightBoundary() {
    const si = this._getSelectedSegmentIndex();
    if (si == null || si >= this.segments.length - 1) return;

    const left = this.segments[si];
    const right = this.segments[si + 1];
    left.end = right.end;
    left.value = right.value;
    this.segments.splice(si + 1, 1);
    this._setSelectedSegmentIndex(si);
    this._drawAll();
    this._emitChange('segment_deleted');
  }

  _moveSelectedSegmentRightBoundary(direction) {
    const si = this._getSelectedSegmentIndex();
    if (si == null || si >= this.segments.length - 1) return;

    const leftSeg = this.segments[si];
    const rightSeg = this.segments[si + 1];
    const epsilon = 0.02;
    const stepSeconds = 0.1;
    const candidate = leftSeg.end + direction * stepSeconds;
    const newBoundary = Math.max(
      leftSeg.start + epsilon,
      Math.min(rightSeg.end - epsilon, candidate)
    );
    if (Math.abs(newBoundary - leftSeg.end) < 1e-9) return;

    leftSeg.end = newBoundary;
    rightSeg.start = newBoundary;
    this._drawAll();
    this._emitChange('boundary_moved');
  }

  _adjustSelectedSegmentRating(delta) {
    const si = this._getSelectedSegmentIndex();
    if (si == null) return;

    const currentDim = this._getCurrentDimension();
    if (!currentDim) return;
    const { min, max } = this._getValueRange(currentDim);

    const seg = this.segments[si];
    const nextValue = Math.max(min, Math.min(max, seg.value + delta));
    if (nextValue === seg.value) return;

    seg.value = nextValue;
    this._drawAll();
    this._emitChange('rating_changed');
  }

  _selectPreviousSegment() {
    const si = this._getSelectedSegmentIndex();
    if (si == null) return;
    this._setSelectedSegmentIndex(si - 1);
    this._drawAll();
  }

  _selectNextSegment() {
    const si = this._getSelectedSegmentIndex();
    if (si == null) return;
    this._setSelectedSegmentIndex(si + 1);
    this._drawAll();
  }

  setDimensions(rating_dimensions) {
    this.rating_dimensions = rating_dimensions;

    // Rebuild dimension buttons
    if (this.dimButtonsWrap) {
      this.dimButtonsWrap.innerHTML = '';
      for (const dim of this.rating_dimensions) {
        const b = document.createElement('button');
        b.type = 'button';
        b.textContent = dim.display_name || dim.dimension_title;
        b.dataset.dim = dim.dimension_title;
        this.dimButtonsWrap.appendChild(b);
      }

      // Re-bind button events
      this.dimButtonsWrap.querySelectorAll('button').forEach((btn) => {
        btn.addEventListener('click', () => {
          this.dimensionData[this.currentDimension] = JSON.parse(
            JSON.stringify(this.segments)
          );
          this.currentDimension = btn.dataset.dim;
          this.segments = this.dimensionData[this.currentDimension];
          this._setSelectedSegmentIndex(0);
          this._updateLegend();
          this._updateActiveButton();
          this._updateDimensionDescription(); // ADD THIS LINE
          this._drawAll();
          this._emitChange('dimension_changed');
        });
      });
    }

    // Initialize data
    this._initData();

    // Update UI
    if (this.currentDimension) {
      this._updateLegend();
      this._updateDimensionDescription(); // ADD THIS LINE
    }
    this._updateActiveButton();
    this._drawAll();

    return this;
  }

  async _init() {
    if (!AudioRatingWidget._WaveSurfer) {
      const mod = await import('./wavesurfer.esm.js');
      AudioRatingWidget._WaveSurfer = mod.default;
    }

    this._buildDOM();

    if (this._hasDimensions()) {
      this._initData();
    }

    this._bindUI();
    await this._initWaveSurfer();

    if (this.currentDimension) {
      this._updateLegend();
      this._updateDimensionDescription();
    }

    this._updateActiveButton();
    setTimeout(() => this._resizeOverlay(), 300);
  }

  _getValueRange(dimension) {
    const dim =
      typeof dimension === 'string'
        ? this.rating_dimensions.find((d) => d.dimension_title === dimension)
        : dimension;

    if (!dim) return { min: 0, max: 0 };

    const min = dim.minimal_value || 0;
    const max = min + dim.num_values - 1;

    return { min, max };
  }

  _hasDimensions() {
    return this.rating_dimensions && this.rating_dimensions.length > 0;
  }

  _buildDOM() {
    // Build widget structure inside container
    this.container.classList.add('arw-host');

    const root = document.createElement('div');
    root.className = 'arw';
    root.tabIndex = 0; // allow focus for spacebar handling
    root.setAttribute('role', 'region');
    root.setAttribute(
      'aria-label',
      typeof this.title === 'string' && this.title.trim().length > 0
        ? this.title
        : this.t('widget.title')
    );

    // Conditionally show instructions based on with_instructions
    const titleHtml =
      typeof this.title === 'string' && this.title.trim().length > 0
        ? `<div class='arw-title'>${this.title}</div>`
        : '';

    // Create the main HTML structure in one go
    root.innerHTML = `
    ${titleHtml}
    ${
      this.with_instructions
        ? `<div class="arw-info"><span class="arw-dimensions-manual">${this.t(
            'widget.selectDimension'
          )}</span></div>`
        : ''
    }

    <div class="arw-section-box arw-dimension-navigation">
      <h4 class="arw-section-label arw-dimension-select-label">${this.t(
        'widget.selectRatingDimension'
      )}</h4>
      <div class="arw-dimension-buttons"></div>
      <div class="arw-dimension-description"></div>
    </div>

    <div class="arw-section-box arw-visualization-section">
      <h4 class="arw-section-label arw-audio-visualization-label">${this.t(
        'widget.audioVisualization'
      )}</h4>
      ${
        this.with_instructions
          ? `<div class="arw-info"><span class="arw-ratings-manual">${this.t(
              'widget.ratingControls'
            )}</span></div>`
          : ''
      }

      <div class="arw-container">
          <div class="arw-waveform"></div>
          <canvas class="arw-overlay"></canvas>
      </div>

      <div class="arw-controls">

          ${
            this.show_download_button
              ? ''
              : '<style>.arw-export { display: none; }</style>'
          }

          ${
            this.with_step_labels_legend
              ? `<label><span class="arw-step-levels-label">${this.t(
                  'widget.stepLevels'
                )}</span> <strong class="arw-steps-label"></strong></label><div class="arw-legend"></div>`
              : ''
          }
          <button class="arw-export">${this.t('widget.downloadCsv')}</button>
      </div>

      <div class="arw-zoom-controls">
          <button class="arw-zoom-in" type="button">${this.t(
            'widget.zoomIn'
          )}</button>
          <button class="arw-zoom-out" type="button">${this.t(
            'widget.zoomOut'
          )}</button>
          <button class="arw-zoom-reset" type="button">${this.t(
            'widget.zoomReset'
          )}</button>
      </div>
    </div>

    <div class="arw-section-box arw-playback-section">
      <h4 class="arw-section-label arw-playback-controls-label">${this.t(
        'widget.playbackControls'
      )}</h4>
      ${
        this.with_instructions
          ? `<div class="arw-info"><span class="arw-audio-manual">${this.t(
              'widget.audioControls'
            )}</span></div>`
          : ''
      }

      <div class="arw-slider">
          <input type="range" class="arw-time-slider" min="0" max="1" step="0.001" value="0" aria-label="${this.t(
            'widget.seekPosition'
          )}">
      </div>

      <div class="arw-audio-controls">
        <button class="arw-play" type="button">${this.t('widget.play')}</button>
        <button class="arw-stop" type="button" aria-label="${this.t(
          'widget.stop'
        )}">${this.t('widget.stop')}</button>
          ${
            this.with_volume_slider
              ? `
          <div class="arw-volume-control">
          <label class="arw-volume-label">${this.t('widget.volume')} </label>
              <input type="range" class="arw-volume-slider" min="0" max="1" step="0.01" value="1" aria-label="${this.t(
                'widget.volume'
              )}">
          </div>
          `
              : ''
          }
      </div>

      <div class="arw-info">
        <span class="arw-status" role="status" aria-live="polite">${this.t(
          'widget.statusLoading'
        )}</span>
      </div>
    </div>
    `;

    this.container.appendChild(root);

    // Refs
    this.root = root;
    this.dimensionDescriptionEl = root.querySelector(
      '.arw-dimension-description'
    );
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
    this.volumeSlider = root.querySelector('.arw-volume-slider');

    // Zoom buttons
    this.zoomInBtn = root.querySelector('.arw-zoom-in');
    this.zoomOutBtn = root.querySelector('.arw-zoom-out');
    this.zoomResetBtn = root.querySelector('.arw-zoom-reset');

    if (this.overlay) {
      this.overlay.tabIndex = 0;
      this.overlay.setAttribute(
        'aria-label',
        this.t('widget.audioVisualization')
      );
    }

    // Build dimension buttons
    for (const dim of this.rating_dimensions) {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = dim.display_name || dim.dimension_title;
      b.dataset.dim = dim.dimension_title;
      this.dimButtonsWrap.appendChild(b);
    }

    this._updatePlayButtonA11y();
    this._updateStopButtonA11y();
  }

  _getCurrentDimension() {
    if (!this.currentDimension) return null;
    return this.rating_dimensions.find(
      (d) => d.dimension_title === this.currentDimension
    );
  }

  _initData() {
    const segmentsDefault = (dim) => [
      {
        start: 0,
        end: 1e9,
        value:
          dim.default_value !== undefined
            ? dim.default_value
            : (dim.minimal_value || 0) + Math.floor(dim.num_values / 2),
      },
    ];

    this.rating_dimensions.forEach((dim) => {
      this.dimensionData[dim.dimension_title] = segmentsDefault(dim);
    });

    if (this.rating_dimensions.length > 0 && !this.currentDimension) {
      this.currentDimension = this.rating_dimensions[0].dimension_title;
    }

    if (this.currentDimension && this.dimensionData[this.currentDimension]) {
      this.segments = this.dimensionData[this.currentDimension];
      this._setSelectedSegmentIndex(0);
    }
  }

  _updateDimensionDescription() {
    if (!this.dimensionDescriptionEl || !this.currentDimension) return;

    const currentDim = this._getCurrentDimension();
    if (!currentDim) {
      this.dimensionDescriptionEl.textContent = '';
      return;
    }

    this.dimensionDescriptionEl.textContent = currentDim.description || '';
  }

  _updateZoomButtonStates() {
    if (!this.wavesurfer) return;

    const currentZoom =
      this._currentPxPerSec || this._defaultMinPxPerSec || 100;
    const defaultZoom = this._defaultMinPxPerSec || 100;

    // Disable zoom out if we're at or below default zoom level
    this.zoomOutBtn.disabled = currentZoom <= defaultZoom * 1.05;
  }

  _getVisibleDuration() {
    if (!this.wavesurfer) return this._durationOrOne();

    const duration = this._durationOrOne();
    const contentEl = this.wavesurfer.getWrapper?.();
    const scrollEl = contentEl?.parentElement || null;

    if (scrollEl && contentEl) {
      const scrollWidth =
        contentEl.scrollWidth ||
        scrollEl.scrollWidth ||
        scrollEl.clientWidth ||
        1;
      const clientWidth =
        scrollEl.clientWidth || contentEl.clientWidth || scrollWidth;
      const widthRatio = Math.min(1, Math.max(0, clientWidth / scrollWidth));
      const visibleByWidth = duration * widthRatio;
      if (visibleByWidth > 0 && isFinite(visibleByWidth)) {
        return Math.max(0.1, visibleByWidth);
      }
    }

    const visibleRange = (this.visibleEnd ?? 0) - (this.visibleStart ?? 0);
    if (visibleRange > 0 && isFinite(visibleRange)) {
      return visibleRange;
    }

    return duration;
  }

  _timelineTimeInterval(visibleDurationSec) {
    if (visibleDurationSec <= 10) return 1;
    if (visibleDurationSec <= 30) return 2;
    if (visibleDurationSec <= 75) return 5;
    if (visibleDurationSec <= 180) return 10;
    if (visibleDurationSec <= 600) return 30;
    return 60;
  }

  _timelinePrimaryLabelInterval(visibleDurationSec) {
    if (visibleDurationSec <= 30) return 1;
    if (visibleDurationSec <= 180) return 2;
    return 1;
  }

  _timelineSecondaryLabelInterval(visibleDurationSec) {
    // Keep a single visual tier by aligning secondary with primary.
    return this._timelinePrimaryLabelInterval(visibleDurationSec);
  }

  _createTimelinePlugin(
    timeInterval,
    primaryLabelInterval,
    secondaryLabelInterval
  ) {
    return TimelinePlugin.create({
      height: 20,
      insertPosition: 'beforebegin',
      timeInterval,
      primaryLabelInterval,
      secondaryLabelInterval,
      formatTimeCallback: (seconds) => {
        if (Math.abs(seconds) < 0.001) return '';
        if (seconds / 60 > 1) {
          const remainingSeconds = Math.round(seconds % 60);
          return `${Math.floor(seconds / 60)}:${
            remainingSeconds < 10 ? '0' : ''
          }${remainingSeconds}`;
        }
        return `${Math.round(seconds * 1000) / 1000}`;
      },
      style: {
        fontSize: '20px',
        color: '#2D5B88',
      },
    });
  }

  _rebuildTimeline(timeInterval, primaryLabelInterval, secondaryLabelInterval) {
    if (!this.wavesurfer) return;

    try {
      this.topTimeline?.destroy();
    } catch {
      console.log(''); /* ignore */
    }

    this.topTimeline = this._createTimelinePlugin(
      timeInterval,
      primaryLabelInterval,
      secondaryLabelInterval
    );
    this.topTimeline.init(this.wavesurfer);

    const duration = this.wavesurfer.getDuration();
    if (duration && isFinite(duration)) {
      this.topTimeline.initTimeline(duration);
    }
  }

  _applyTimelineDensity() {
    if (!this.wavesurfer) return;
    const visibleDuration = this._getVisibleDuration();
    const timeInterval = this._timelineTimeInterval(visibleDuration);
    const primaryLabelInterval =
      this._timelinePrimaryLabelInterval(visibleDuration);
    const secondaryLabelInterval =
      this._timelineSecondaryLabelInterval(visibleDuration);
    const densityKey = `${timeInterval}|${primaryLabelInterval}|${secondaryLabelInterval}`;

    if (densityKey === this._lastTimelineDensityKey) {
      return;
    }

    this._rebuildTimeline(
      timeInterval,
      primaryLabelInterval,
      secondaryLabelInterval
    );
    this._lastTimelineDensityKey = densityKey;
  }

  async _initWaveSurfer() {
    const WaveSurfer = AudioRatingWidget._WaveSurfer;

    const topTimeline = this._createTimelinePlugin(5, 1, 1);
    this.topTimeline = topTimeline;

    this.wavesurfer = WaveSurfer.create({
      container: this.waveformEl,
      waveColor: this.waveColor,
      progressColor: this.progressColor,
      height: this.CANVAS_HEIGHT,
      scrollParent: this.scrollParent,
      plugins: [topTimeline],
    });

    // Inject scrollbar styles directly into WaveSurfer's shadow DOM.
    // This is the only way to reach the inner .scroll element reliably:
    // CSS ::part(scroll)::-webkit-scrollbar chains are forbidden by spec,
    // so external stylesheets can't switch Chrome from overlay to classic mode.
    // WaveSurfer uses attachShadow({mode:"open"}), so the shadow root is accessible.
    // The ::-webkit-scrollbar rule is what tells Chrome to use a classic scrollbar
    // instead of the OS overlay scrollbar (thin, fading, variable height on hover).
    //
    // We reach the shadow root via getWrapper().getRootNode(): getWrapper() returns
    // the .wrapper element *inside* the shadow root, so getRootNode() reliably walks
    // up to the shadow root regardless of where in the outer DOM WaveSurfer appended itself.
    {
      const shadowRoot = this.wavesurfer.getWrapper()?.getRootNode();
      if (shadowRoot && shadowRoot.nodeType === Node.DOCUMENT_FRAGMENT_NODE) {
        const s = document.createElement('style');
        s.textContent = [
          '.scroll { overflow-x: scroll !important;', // always present; beats WaveSurfer inline style
          '         scrollbar-color: #94a3b8 #e2e8f0; }', // Firefox
          '.scroll::-webkit-scrollbar { height: 8px; }', // classic mode + fixed height
          '.scroll::-webkit-scrollbar-track { background: #e2e8f0; border-radius: 2px; }',
          '.scroll::-webkit-scrollbar-thumb { background: #94a3b8; border-radius: 2px; }',
          '.scroll::-webkit-scrollbar-thumb:hover { background: #64748b; }',
        ].join('\n');
        shadowRoot.appendChild(s);
      }
    }

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

    if (!this.audioUrl)
      throw new Error('AudioRatingWidget: audioUrl is required');
    this.wavesurfer.load(this.audioUrl);

    // Keep track of visible window: wavesurfer v7 emits 'scroll' with (visibleStartTime, visibleEndTime, scrollLeft, scrollRight)
    this.wavesurfer.on('scroll', (visibleStartTime, visibleEndTime) => {
      // visibleStartTime and visibleEndTime are in seconds (per docs)
      this.visibleStart =
        typeof visibleStartTime === 'number' ? visibleStartTime : 0;
      this.visibleEnd =
        typeof visibleEndTime === 'number'
          ? visibleEndTime
          : this._durationOrOne();
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
      this._defaultMinPxPerSec =
        this.wavesurfer.params?.minPxPerSec ?? this._defaultMinPxPerSec;
      this._applyTimelineDensity();
      this._updateZoomButtonStates();

      // Auto-focus widget root so spacebar works immediately
      if (!this.root.contains(document.activeElement)) {
        this.root.focus();
      }
    });

    this.wavesurfer.on('finish', () => {
      this.playBtn.textContent = this.t('widget.play');
      this._updatePlayButtonA11y();
    });

    // Button state driven by real events
    this.wavesurfer.on('play', () => {
      this.playBtn.textContent = this.t('widget.pause');
      this._updatePlayButtonA11y();
    });
    this.wavesurfer.on('pause', () => {
      this.playBtn.textContent = this.t('widget.play');
      this._updatePlayButtonA11y();
    });

    // Update current time during playback
    this.wavesurfer.on('timeupdate', () => {
      this._updateStatus();
    });

    // Keep UI when zoom changes
    this.wavesurfer.on('zoom', (minPxPerSec) => {
      // update our cached current px/sec
      this._currentPxPerSec = minPxPerSec || null;
      requestAnimationFrame(() => this._applyTimelineDensity());
      setTimeout(() => this._applyTimelineDensity(), 80);
      // wavesurfer will usually emit a 'scroll' event after zooming; ensure we redraw
      this._drawAll();
      this._updateZoomButtonStates();
    });
  }

  _updateStatus() {
    if (this.wavesurfer && this.wavesurfer.isReady) {
      const duration = this.wavesurfer.getDuration();
      const currentTime = this.wavesurfer.getCurrentTime();
      this.statusEl.textContent = this.t('widget.statusCurrent', {
        current: currentTime.toFixed(2),
        total: duration.toFixed(2),
      });
    } else {
      this.statusEl.textContent = '';
    }
  }

  _bindUI() {
    // Resize
    this._onResize = () => {
      setTimeout(() => this._resizeOverlay(), 120);
    };
    window.addEventListener('resize', this._onResize);

    // Play / Stop buttons
    this.playBtn.addEventListener('click', () => {
      this.wavesurfer.playPause();
    });
    this.stopBtn.addEventListener('click', () => {
      this._stopPlaybackToStart();
    });

    this._onLanguageChanged = () => {
      this._applyI18nTexts();
      this._updateLegend();
      this._updateStatus();
    };
    window.addEventListener('i18n:languageChanged', this._onLanguageChanged);

    // Keyboard controls (only when widget (root) is focused)
    this._onKeyDown = (ev) => {
      const tag = document.activeElement?.tagName;
      const inTextInput = tag === 'INPUT' || tag === 'TEXTAREA';
      if (inTextInput) return;
      const widgetFocused =
        document.activeElement === this.root ||
        this.root.contains(document.activeElement);
      if (!widgetFocused) return;
      const editingFocused =
        document.activeElement === this.root ||
        document.activeElement === this.overlay;

      if (editingFocused && ev.code === 'Enter') {
        ev.preventDefault();
        this._splitSelectedSegmentAtMidpoint();
        return;
      }

      if (editingFocused && ev.code === 'Delete') {
        ev.preventDefault();
        this._deleteSelectedSegmentRightBoundary();
        return;
      }

      if (editingFocused && ev.code === 'ArrowLeft') {
        ev.preventDefault();
        this._moveSelectedSegmentRightBoundary(-1);
        return;
      }

      if (editingFocused && ev.code === 'ArrowRight') {
        ev.preventDefault();
        this._moveSelectedSegmentRightBoundary(1);
        return;
      }

      if (editingFocused && ev.code === 'ArrowUp') {
        ev.preventDefault();
        this._adjustSelectedSegmentRating(1);
        return;
      }

      if (editingFocused && ev.code === 'ArrowDown') {
        ev.preventDefault();
        this._adjustSelectedSegmentRating(-1);
        return;
      }

      if (editingFocused && ev.code === 'PageUp') {
        ev.preventDefault();
        this._selectPreviousSegment();
        return;
      }

      if (editingFocused && ev.code === 'PageDown') {
        ev.preventDefault();
        this._selectNextSegment();
        return;
      }

      if (ev.code === 'Space') {
        ev.preventDefault();
        this.wavesurfer.playPause();
        return;
      }

      if (ev.code === 'Backspace') {
        ev.preventDefault();
        this._stopPlaybackToStart();
      }
    };
    window.addEventListener('keydown', this._onKeyDown);

    // Slider seeking
    this.timeSlider.addEventListener('input', () => {
      const t = parseFloat(this.timeSlider.value);
      this._seekToTime(t);
    });

    // Export CSV
    this.root
      .querySelector('.arw-export')
      .addEventListener('click', () => this._exportCSV());

    // Dimension buttons
    this.dimButtonsWrap.querySelectorAll('button').forEach((btn) => {
      btn.addEventListener('click', () => {
        this.dimensionData[this.currentDimension] = JSON.parse(
          JSON.stringify(this.segments)
        );
        this.currentDimension = btn.dataset.dim;
        this.segments = this.dimensionData[this.currentDimension];
        this._setSelectedSegmentIndex(0);
        this._updateLegend();
        this._updateActiveButton();
        this._updateDimensionDescription();
        this._drawAll();
        this._emitChange('dimension_changed');
      });
    });

    // Zoom buttons
    this.zoomInBtn.addEventListener('click', () => this._zoomIn());
    this.zoomOutBtn.addEventListener('click', () => this._zoomOut());
    this.zoomResetBtn.addEventListener('click', () => this._resetZoom());

    // Overlay pointer interactions
    this.overlay.addEventListener('pointerdown', (ev) =>
      this._onPointerDown(ev)
    );
    this.overlay.addEventListener('pointermove', (ev) =>
      this._onPointerMove(ev)
    );
    this.overlay.addEventListener('pointerup', (ev) => this._onPointerUp(ev));
    this.overlay.addEventListener('pointerleave', () => this._onPointerLeave());
    this.overlay.addEventListener('dblclick', (ev) => this._onDblClick(ev));
    this.overlay.addEventListener('contextmenu', (ev) =>
      this._onContextMenu(ev)
    );
  }

  // ===== Drawing & layout =====

  _resizeOverlay() {
    const rect = this.waveformEl.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;

    // Leave 8px at the bottom for the WaveSurfer scrollbar (classic 8px scrollbar injected into shadow DOM).
    const overlayHeight = this.CANVAS_HEIGHT - 8;

    this.overlay.style.width = `${Math.max(100, rect.width)}px`;
    this.overlay.style.height = `${overlayHeight}px`;

    this.overlay.width = Math.max(100, Math.round(rect.width * dpr));
    this.overlay.height = Math.round(overlayHeight * dpr);

    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    this._drawAll();
  }

  _startRenderLoop() {
    if (this.renderLoop) cancelAnimationFrame(this.renderLoop);
    const loop = () => {
      this._drawAll();
      this.renderLoop = requestAnimationFrame(loop);
    };
    this.renderLoop = requestAnimationFrame(loop);
  }

  _stopRenderLoop() {
    if (this.renderLoop) cancelAnimationFrame(this.renderLoop);
    this.renderLoop = null;
  }

  _durationOrOne() {
    const d = this.wavesurfer.getDuration();
    return d && isFinite(d) ? d : 1;
  }

  /* ZOOM: time <-> x mapping now uses the current visible start/end window (in seconds).
     This ensures segments (which store absolute seconds) remain correct when zoomed or scrolled. */

  _timeToX(time) {
    if (!this.wavesurfer) return 0;
    const duration = this._durationOrOne();
    const wrapper = this.wavesurfer.getWrapper();
    const scroll = wrapper.scrollLeft || 0;
    const totalWidth =
      wrapper.scrollWidth || wrapper.clientWidth || this.overlay.width;
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
    const totalWidth = wrapper.scrollWidth;

    const globalX = x + scroll;
    const time = (globalX / totalWidth) * duration;

    return time;
  }

  _formatTimeLabel(seconds) {
    const safeSeconds = Math.max(0, Number.isFinite(seconds) ? seconds : 0);
    const whole = Math.round(safeSeconds);
    const minutes = Math.floor(whole / 60);
    const secs = whole % 60;
    return `${minutes}:${String(secs).padStart(2, '0')}`;
  }

  _findSegmentIndexAtTime(time) {
    for (let i = 0; i < this.segments.length; i++) {
      if (this.segments[i].start <= time && time <= this.segments[i].end)
        return i;
    }
    return -1;
  }

  _colorForRating(r, num_values) {
    // Normalize to 0-1 range for coloring
    const normalized = r / (num_values - 1 || 1);
    const hue = 220 - (220 - 10) * normalized;
    return `hsl(${hue} 80% 50% / 0.45)`;
  }

  _updateLegend() {
    if (this.legend == null || !this.currentDimension) return;

    const currentDim = this._getCurrentDimension();
    if (!currentDim) return;

    const num_values = currentDim.num_values;
    const min_value = currentDim.minimal_value || 0;
    const max_value = min_value + num_values - 1;

    this.legend.innerHTML = '';

    // Create legend items from min to max (ascending order)
    for (let i = min_value; i <= max_value; i++) {
      const item = document.createElement('div');
      item.className = 'legend-item';

      // Calculate position in the 0-1 range for coloring
      const normalizedValue = (i - min_value) / (max_value - min_value);
      item.style.background = this._colorForRating(
        normalizedValue * (num_values - 1),
        num_values
      ).replace('/ 0.45)', '/1)');

      item.textContent = i;
      this.legend.appendChild(item);
    }

    if (this.stepsLabel) {
      this.stepsLabel.textContent = this.t('widget.stepsCount', {
        count: num_values,
        min: min_value,
        max: max_value,
      });
    }
  }

  _applyI18nTexts() {
    const root = this.root;
    if (!root) return;

    const dimensionsManual = root.querySelector('.arw-dimensions-manual');
    if (dimensionsManual)
      dimensionsManual.textContent = this.t('widget.selectDimension');

    const ratingsManual = root.querySelector('.arw-ratings-manual');
    if (ratingsManual)
      ratingsManual.textContent = this.t('widget.ratingControls');

    const dimensionSelectLabel = root.querySelector(
      '.arw-dimension-select-label'
    );
    if (dimensionSelectLabel)
      dimensionSelectLabel.textContent = this.t('widget.selectRatingDimension');

    const audioVisualizationLabel = root.querySelector(
      '.arw-audio-visualization-label'
    );
    if (audioVisualizationLabel)
      audioVisualizationLabel.textContent = this.t('widget.audioVisualization');

    const playbackControlsLabel = root.querySelector(
      '.arw-playback-controls-label'
    );
    if (playbackControlsLabel)
      playbackControlsLabel.textContent = this.t('widget.playbackControls');

    const stepLevelsLabel = root.querySelector('.arw-step-levels-label');
    if (stepLevelsLabel)
      stepLevelsLabel.textContent = this.t('widget.stepLevels');

    const exportBtn = root.querySelector('.arw-export');
    if (exportBtn) exportBtn.textContent = this.t('widget.downloadCsv');

    const audioManual = root.querySelector('.arw-audio-manual');
    if (audioManual) audioManual.textContent = this.t('widget.audioControls');

    if (this.zoomInBtn) this.zoomInBtn.textContent = this.t('widget.zoomIn');
    if (this.zoomOutBtn) this.zoomOutBtn.textContent = this.t('widget.zoomOut');
    if (this.zoomResetBtn)
      this.zoomResetBtn.textContent = this.t('widget.zoomReset');

    const volumeLabel = root.querySelector('.arw-volume-label');
    if (volumeLabel) volumeLabel.textContent = `${this.t('widget.volume')} `;

    if (this.stopBtn) this.stopBtn.textContent = this.t('widget.stop');
    this._updateStopButtonA11y();

    if (this.timeSlider)
      this.timeSlider.setAttribute('aria-label', this.t('widget.seekPosition'));
    if (this.volumeSlider)
      this.volumeSlider.setAttribute('aria-label', this.t('widget.volume'));
    if (this.overlay)
      this.overlay.setAttribute(
        'aria-label',
        this.t('widget.audioVisualization')
      );

    if (this.playBtn) {
      this.playBtn.textContent =
        this.wavesurfer && this.wavesurfer.isPlaying()
          ? this.t('widget.pause')
          : this.t('widget.play');
      this._updatePlayButtonA11y();
    }
  }

  _updateActiveButton() {
    this.dimButtonsWrap.querySelectorAll('button').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.dim === this.currentDimension);
    });
  }

  _drawAll() {
    const ctx = this.ctx;
    const h = this.overlay.height / (window.devicePixelRatio || 1);
    const w = this.overlay.width / (window.devicePixelRatio || 1);

    const currentDim = this._getCurrentDimension();
    if (!currentDim) {
      console.warn('No current dimension found');
      return;
    }

    const num_steps = currentDim.num_values;
    const min_value = currentDim.minimal_value || 0;
    const max_value = min_value + num_steps - 1;

    ctx.clearRect(0, 0, w, h);

    // Draw horizontal grid lines with correct labels
    let lastDrawnYAxisLabelY = null;
    const minYAxisLabelDistance = 11;
    for (let i = 0; i < num_steps; i++) {
      const value = min_value + i;
      const y = h - (i / (num_steps - 1)) * h;

      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.lineWidth =
        value === Math.floor((max_value + min_value) / 2) ? 1.2 : 0.7;
      ctx.strokeStyle = 'rgba(0,0,0,0.06)';
      ctx.stroke();

      // Draw value label
      const labelY = Math.max(11, Math.min(h - 2, y - 4));
      if (
        lastDrawnYAxisLabelY == null ||
        Math.abs(lastDrawnYAxisLabelY - labelY) >= minYAxisLabelDistance
      ) {
        ctx.fillStyle = 'rgba(0,0,0,0.6)';
        ctx.font = '12px system-ui, Arial';
        ctx.fillText(String(value), 6, labelY);
        lastDrawnYAxisLabelY = labelY;
      }
    }

    const marginRight = 0;

    // Draw segments
    this.segments.forEach((seg, idx) => {
      const x1 = this._timeToX(seg.start);
      const x2 = Math.min(this._timeToX(seg.end), w - marginRight);

      // Calculate vertical position based on value range
      const normalizedValue = (seg.value - min_value) / (max_value - min_value);
      const heightFromTop = (1 - normalizedValue) * h;

      const color = this._colorForRating(seg.value - min_value, num_steps);
      ctx.fillStyle = color;
      ctx.fillRect(x1, heightFromTop, Math.max(2, x2 - x1), h - heightFromTop);

      ctx.strokeStyle = 'rgba(0,0,0,0.08)';
      ctx.lineWidth = 1;
      ctx.strokeRect(
        x1 + 0.5,
        heightFromTop + 0.5,
        Math.max(1, x2 - x1 - 1),
        h - heightFromTop - 1
      );

      // Draw value text inside segment
      const valueText = `${seg.value}`;
      ctx.font = '600 12px system-ui, Arial';
      const textWidth = Math.ceil(ctx.measureText(valueText).width);
      const labelPaddingX = 4;
      const labelPaddingY = 2;
      let labelX = x2 - textWidth - labelPaddingX - 4;
      labelX = Math.max(x1 + 2, labelX);
      labelX = Math.min(labelX, w - textWidth - labelPaddingX - 2);
      const labelY = Math.max(12, heightFromTop + 12);
      const labelHeight = 14;
      const labelWidth = textWidth + labelPaddingX * 2;

      ctx.fillStyle = 'rgba(250, 252, 255, 0.72)';
      ctx.fillRect(
        labelX - labelPaddingX,
        labelY - labelHeight + labelPaddingY,
        labelWidth,
        labelHeight
      );
      ctx.strokeStyle = 'rgba(43, 76, 117, 0.25)';
      ctx.lineWidth = 1;
      ctx.strokeRect(
        labelX - labelPaddingX + 0.5,
        labelY - labelHeight + labelPaddingY + 0.5,
        Math.max(1, labelWidth - 1),
        Math.max(1, labelHeight - 1)
      );
      ctx.fillStyle = 'rgba(25, 47, 74, 0.95)';
      ctx.fillText(valueText, labelX, labelY - 1);

      // Draw segment boundaries
      if (idx > 0) {
        const hx = x1;
        ctx.fillStyle = 'rgba(0,0,0,0.6)';
        ctx.fillRect(hx - 1, 0, 2, h);
      }
    });

    // Long-press progress arc over the targeted handle.
    // Only drawn after LONG_PRESS_VISUAL_DELAY ms so a quick drag never shows red.
    if (
      this._longPressTimer &&
      this._longPressHandleI != null &&
      this._longPressHandleI < this.segments.length
    ) {
      const elapsed = Date.now() - this._longPressStartTime;
      const visualWindow =
        this.LONG_PRESS_DURATION - this.LONG_PRESS_VISUAL_DELAY;
      const progress = Math.min(
        1,
        (elapsed - this.LONG_PRESS_VISUAL_DELAY) / visualWindow
      );
      if (progress > 0) {
        const hx = this._timeToX(this.segments[this._longPressHandleI].start);
        const cy = h / 2;
        const r = 16;
        ctx.save();
        ctx.beginPath();
        ctx.arc(hx, cy, r, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(220, 38, 38, 0.15)';
        ctx.fill();
        ctx.beginPath();
        ctx.arc(hx, cy, r, -Math.PI / 2, -Math.PI / 2 + progress * Math.PI * 2);
        ctx.strokeStyle = 'rgba(220, 38, 38, 0.9)';
        ctx.lineWidth = 3;
        ctx.stroke();
        ctx.restore();
      }
    }

    const widgetFocused =
      document.activeElement === this.root ||
      this.root.contains(document.activeElement);
    const selectedIndex = this._getSelectedSegmentIndex();
    if (widgetFocused && selectedIndex != null) {
      const selectedSeg = this.segments[selectedIndex];
      const sx1 = this._timeToX(selectedSeg.start);
      const sx2 = Math.min(this._timeToX(selectedSeg.end), w - marginRight);
      ctx.strokeStyle = 'rgba(75, 85, 99, 0.5)';
      ctx.lineWidth = 1;
      ctx.strokeRect(
        sx1 + 0.5,
        0.5,
        Math.max(1, sx2 - sx1 - 1),
        Math.max(1, h - 1)
      );
    }

    if (
      this.hoverSegIndex != null &&
      this.hoverSegIndex >= 0 &&
      this.hoverSegIndex < this.segments.length
    ) {
      let tooltipLines = [];

      if (this.hoverHandleIndex != null) {
        tooltipLines = [
          this.t('widget.segmentBorderTooltipLine1'),
          this.t('widget.segmentBorderTooltipLine2'),
        ];
      } else {
        const seg = this.segments[this.hoverSegIndex];
        const duration = this._durationOrOne();
        const segmentStart = Math.max(0, seg.start);
        const segmentEnd = Math.max(segmentStart, Math.min(seg.end, duration));
        const segmentLengthSec = segmentEnd - segmentStart;

        tooltipLines = [
          `segment #${this.hoverSegIndex + 1}`,
          `${segmentLengthSec.toFixed(1)} seconds length`,
          `from ${this._formatTimeLabel(
            segmentStart
          )} to ${this._formatTimeLabel(segmentEnd)}`,
          `rating ${seg.value}`,
        ];
      }

      ctx.font = '12px system-ui, Arial';
      const tooltipPadding = 7;
      const lineHeight = 16;
      const tooltipWidth =
        Math.max(
          ...tooltipLines.map((line) => Math.ceil(ctx.measureText(line).width))
        ) +
        tooltipPadding * 2;
      const tooltipHeight =
        tooltipLines.length * lineHeight + tooltipPadding * 2 - 2;

      let tooltipX = this.hoverPointerX + 10;
      let tooltipY = this.hoverPointerY + 10;

      if (tooltipX + tooltipWidth > w - 4) {
        tooltipX = this.hoverPointerX - tooltipWidth - 10;
      }
      if (tooltipY + tooltipHeight > h - 4) {
        tooltipY = this.hoverPointerY - tooltipHeight - 10;
      }

      tooltipX = Math.max(4, tooltipX);
      tooltipY = Math.max(4, tooltipY);

      ctx.fillStyle = 'rgba(22, 29, 41, 0.56)';
      ctx.fillRect(tooltipX, tooltipY, tooltipWidth, tooltipHeight);
      ctx.strokeStyle = 'rgba(170, 192, 229, 0.55)';
      ctx.lineWidth = 1;
      ctx.strokeRect(
        tooltipX + 0.5,
        tooltipY + 0.5,
        tooltipWidth - 1,
        tooltipHeight - 1
      );

      ctx.fillStyle = 'rgba(244, 248, 255, 0.98)';
      tooltipLines.forEach((line, index) => {
        ctx.fillText(
          line,
          tooltipX + tooltipPadding,
          tooltipY + tooltipPadding + 11 + index * lineHeight
        );
      });
    }

    // Update slider
    if (this.wavesurfer)
      this.timeSlider.value = this.wavesurfer.getCurrentTime();
  }
  // ===== Interactions =====

  _cancelLongPress() {
    if (this._longPressTimer) {
      clearTimeout(this._longPressTimer);
      this._longPressTimer = null;
      this._longPressHandleI = null;
    }
  }

  _hitTestHandle(x) {
    for (let i = 1; i < this.segments.length; i++) {
      const bx = this._timeToX(this.segments[i].start);
      if (Math.abs(bx - x) <= this.HANDLE_HIT) return { i };
    }
    return null;
  }

  _hitTestRatingLine(x, y) {
    const currentDim = this._getCurrentDimension();
    if (!currentDim) return null;

    const h = this.overlay.getBoundingClientRect().height;
    const minValue = currentDim.minimal_value || 0;
    const maxValue = minValue + currentDim.num_values - 1;
    const ratingLineHit = 5;

    for (let i = 0; i < this.segments.length; i++) {
      const seg = this.segments[i];
      const x1 = this._timeToX(seg.start);
      const x2 = this._timeToX(seg.end);
      if (x < x1 || x > x2) continue;

      const normalizedValue = (seg.value - minValue) / (maxValue - minValue);
      const ratingLineY = (1 - normalizedValue) * h;
      if (Math.abs(y - ratingLineY) <= ratingLineHit) {
        return { i };
      }
    }

    return null;
  }

  _onPointerDown(ev) {
    ev.preventDefault();
    if (document.activeElement !== this.root) {
      try {
        this.root.focus({ preventScroll: true });
      } catch {
        this.root.focus();
      }
    }
    const rect = this.overlay.getBoundingClientRect();
    const x = ev.clientX - rect.left;
    const y = ev.clientY - rect.top;
    this.lastPointerX = x;
    this.lastPointerY = y;
    this.hoverPointerX = x;
    this.hoverPointerY = y;
    this.hoverSegIndex = this._findSegmentIndexAtTime(this._xToTime(x));
    this.hoverHandleIndex = null;
    this.pointerDown = true;

    const handle = this._hitTestHandle(x);
    if (handle) {
      this.activeHandle = {
        index: handle.i,
        startSeg: handle.i - 1,
        endSeg: handle.i,
      };
      this.hoverHandleIndex = handle.i;
      this._setSelectedSegmentIndex(handle.i - 1);
      this.overlay.setPointerCapture(ev.pointerId);

      // Start long-press timer — fires if pointer stays still long enough.
      this._longPressHandleI = handle.i;
      this._longPressStartTime = Date.now();
      this._longPressStartX = x;
      this._longPressStartY = y;
      this._longPressTimer = setTimeout(() => {
        this._longPressTimer = null;
        const i = this._longPressHandleI;
        this._longPressHandleI = null;
        if (i != null && i >= 1 && i < this.segments.length) {
          this.segments[i - 1].end = this.segments[i].end;
          this.segments.splice(i, 1);
          this._setSelectedSegmentIndex(
            Math.min(i - 1, this.segments.length - 1)
          );
          this.activeHandle = null;
          this.pointerDown = false;
          try {
            this.overlay.releasePointerCapture(ev.pointerId);
          } catch {
            console.log(''); /* ignore if already released */
          }
          this._drawAll();
          this._emitChange('segment_deleted');
        }
      }, this.LONG_PRESS_DURATION);

      this._drawAll();
      return;
    }

    const time = this._xToTime(x);
    const si = this._findSegmentIndexAtTime(time);
    if (si >= 0) {
      this.activeSegIndex = si;
      this._setSelectedSegmentIndex(si);
      this.overlay.setPointerCapture(ev.pointerId);
    }
    this._drawAll();
  }

  _onPointerMove(ev) {
    const rect = this.overlay.getBoundingClientRect();
    const x = ev.clientX - rect.left;
    const y = ev.clientY - rect.top;
    this.lastPointerX = x;
    this.lastPointerY = y;
    this.hoverPointerX = x;
    this.hoverPointerY = y;
    this.hoverSegIndex = this._findSegmentIndexAtTime(this._xToTime(x));
    const handle = this._hitTestHandle(x);
    this.hoverHandleIndex = handle ? handle.i : null;
    const ratingLine = this._hitTestRatingLine(x, y);
    if (handle || this.activeHandle) {
      this.overlay.style.cursor = 'ew-resize';
    } else if (ratingLine || this.activeSegIndex != null) {
      this.overlay.style.cursor = 'ns-resize';
    } else {
      this.overlay.style.cursor = 'default';
    }

    if (!this.pointerDown) {
      if (this.hoverSegIndex >= 0) {
        this._setSelectedSegmentIndex(this.hoverSegIndex);
      }
      this._drawAll();
      return;
    }

    if (this.activeHandle) {
      // Cancel long-press if the pointer drifted beyond the movement threshold.
      if (this._longPressTimer) {
        const dx = x - this._longPressStartX;
        const dy = y - this._longPressStartY;
        if (Math.hypot(dx, dy) > this.LONG_PRESS_MOVE_PX) {
          this._cancelLongPress();
        }
      }

      const time = this._xToTime(x);
      const leftSeg = this.segments[this.activeHandle.startSeg];
      const rightSeg = this.segments[this.activeHandle.endSeg];
      const epsilon = 0.02;
      const newBoundary = Math.max(
        leftSeg.start + epsilon,
        Math.min(rightSeg.end - epsilon, time)
      );
      leftSeg.end = newBoundary;
      rightSeg.start = newBoundary;
      this._drawAll();
      this._emitChange('boundary_moved');
      return;
    }

    if (this.activeSegIndex != null) {
      const seg = this.segments[this.activeSegIndex];
      const currentDim = this._getCurrentDimension();
      if (!currentDim) return;

      const { min, __max } = this._getValueRange(currentDim);
      const num_steps = currentDim.num_values;

      const h = this.overlay.height;
      const ratio = 1 - y / h;

      let raw = Math.round(ratio * (num_steps - 1));
      raw = Math.max(0, Math.min(num_steps - 1, raw));

      seg.value = min + raw;

      this._drawAll();
      this._emitChange('rating_changed');
      return;
    }
  }

  _onPointerUp(ev) {
    this._cancelLongPress();
    this.pointerDown = false;
    this.activeSegIndex = null;
    this.activeHandle = null;
    const rect = this.overlay.getBoundingClientRect();
    const x = ev.clientX - rect.left;
    const y = ev.clientY - rect.top;
    this.hoverPointerX = x;
    this.hoverPointerY = y;
    this.hoverSegIndex = this._findSegmentIndexAtTime(this._xToTime(x));
    const handle = this._hitTestHandle(x);
    this.hoverHandleIndex = handle ? handle.i : null;
    const ratingLine = this._hitTestRatingLine(x, y);
    this.overlay.style.cursor = handle
      ? 'ew-resize'
      : ratingLine
        ? 'ns-resize'
        : 'default';
    try {
      this.overlay.releasePointerCapture(ev.pointerId);
    } catch {
      /* ignore if already released */
    }
    this._drawAll();
  }

  _onPointerLeave() {
    this._cancelLongPress();
    if (this.pointerDown) return;
    this.hoverSegIndex = null;
    this.hoverHandleIndex = null;
    this.overlay.style.cursor = 'default';
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
    if (time - seg.start < MIN_SEG || seg.end - time < MIN_SEG) return;
    const right = { start: time, end: seg.end, value: seg.value };
    seg.end = time;
    this.segments.splice(si + 1, 0, right);
    this._setSelectedSegmentIndex(si);
    this._drawAll();
    this._emitChange('segment_added');
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
      this._setSelectedSegmentIndex(i - 1);
      this._drawAll();
      this._emitChange('segment_deleted');
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
        csv += `${dim},${seg.start.toFixed(2)},${seg.end.toFixed(2)},${
          seg.value
        }\n`;
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
    const currentZoom =
      this._currentPxPerSec || this._defaultMinPxPerSec || 100;
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
  } // ===== Public API =====

  // event system
  on(event, callback) {
    if (this._listeners[event]) {
      this._listeners[event].push(callback);
    }
  }

  // event system
  off(event, callback) {
    if (this._listeners[event]) {
      this._listeners[event] = this._listeners[event].filter(
        (cb) => cb !== callback
      );
    }
  }

  // event system
  _emit(event, data) {
    if (this._listeners[event]) {
      this._listeners[event].forEach((callback) => {
        try {
          callback(data);
        } catch (e) {
          console.error('Error in event listener:', e);
        }
      });
    }
  }

  // Helper method to emit change events for event system
  _emitChange(reason) {
    this._emit('change', {
      reason: reason,
      dimension: this.currentDimension,
      data: this.getData(),
    });
  }

  getData() {
    const data = JSON.parse(JSON.stringify(this.dimensionData));
    console.log('getData returning', data);
    return data;
  }

  setData(data) {
    console.log('=== SET DATA DEBUG ===');
    console.log('Received data:', JSON.parse(JSON.stringify(data)));
    console.log('Current rating_dimensions:', this.rating_dimensions);

    // Start with defaults
    const defaults = {};
    this.rating_dimensions.forEach((dim) => {
      defaults[dim.dimension_title] = [
        {
          start: 0,
          end: 1e9,
          value:
            dim.default_value !== undefined
              ? dim.default_value
              : (dim.minimal_value || 0) + Math.floor(dim.num_values / 2),
        },
      ];
    });

    console.log('Defaults:', JSON.parse(JSON.stringify(defaults)));

    // Merge with provided data
    const mergedData = {};

    // First copy all defaults
    Object.keys(defaults).forEach((key) => {
      mergedData[key] = JSON.parse(JSON.stringify(defaults[key]));
    });

    // Then override with provided data if it exists and has content
    if (data) {
      Object.keys(data).forEach((key) => {
        // Check if data[key] exists and has valid segments
        if (data[key] && Array.isArray(data[key]) && data[key].length > 0) {
          // Validate that the segments have the required structure
          const validSegments = data[key].every(
            (seg) =>
              seg &&
              typeof seg.start === 'number' &&
              typeof seg.end === 'number' &&
              typeof seg.value === 'number'
          );

          if (validSegments) {
            console.log(`Overriding ${key} with valid data:`, data[key]);
            mergedData[key] = JSON.parse(JSON.stringify(data[key]));
          } else {
            console.log(
              `Data for ${key} has invalid segment structure, keeping default`
            );
          }
        } else {
          console.log(`Keeping default for ${key} because data is:`, data[key]);
        }
      });
    }

    console.log('Final mergedData:', JSON.parse(JSON.stringify(mergedData)));

    this.dimensionData = mergedData;

    // Ensure segments is set for current dimension
    if (this.currentDimension && this.dimensionData[this.currentDimension]) {
      this.segments = this.dimensionData[this.currentDimension];
      console.log(
        'Set segments for current dimension:',
        this.currentDimension,
        this.segments
      );
    } else if (this.rating_dimensions.length > 0) {
      this.currentDimension = this.rating_dimensions[0].dimension_title;
      this.segments = this.dimensionData[this.currentDimension];
      console.log(
        'Set currentDimension to:',
        this.currentDimension,
        'with segments:',
        this.segments
      );
    }

    this._updateActiveButton();
    this._drawAll();
  }

  destroy() {
    // Clean up listeners and RAF
    window.removeEventListener('resize', this._onResize);
    window.removeEventListener('keydown', this._onKeyDown);
    if (this._onLanguageChanged) {
      window.removeEventListener(
        'i18n:languageChanged',
        this._onLanguageChanged
      );
      this._onLanguageChanged = null;
    }
    this._stopRenderLoop();

    // Destroy WaveSurfer
    try {
      this.wavesurfer?.destroy();
    } catch {
      /* ignore if already released */
    }

    // Remove DOM
    this.root?.remove();
  }
}
// End of audio-rating.js
