import { AudioRatingWidget } from './audio_rating.js';
import i18n from './i18n.js';

// DEFAULT CONFIG - Updated to match backend format
const INTERNAL_FALLBACK_STUDY_CONFIG = {
  name: 'Default Study',
  name_short: 'default',
  description: 'Default study for music aesthetics research',
  songs_to_rate: [
    {
      media_url: 'audo_files/default/demo.wav',
      display_name: 'Demo Song',
      description:
        'This is a demo song for testing the audio rating widget. Please listen to the entire clip and provide your ratings based on your experience.',
    },
    {
      media_url: 'audo_files/default/demo2.wav',
      display_name: 'Demo Song 2',
      description:
        'This is a second demo song for testing the audio rating widget. Please listen to the entire clip and provide your ratings based on your experience.',
    },
  ],
  rating_dimensions: [
    {
      dimension_title: 'valence',
      num_values: 8,
      minimal_value: 0,
      default_value: 4,
      description: 'The valence of the song section',
    },
    {
      dimension_title: 'arousal',
      num_values: 5,
      minimal_value: -2,
      default_value: 0,
      description: 'The arousal level of the song section',
    },
    {
      dimension_title: 'enjoyment',
      num_values: 10,
      minimal_value: 0,
      default_value: 5,
      description: 'The enjoyment level of the song section',
    },
    {
      dimension_title: 'is_cool',
      num_values: 2,
      minimal_value: 0,
      default_value: 0,
      description: 'Whether the song section is cool or not',
    },
  ],
  study_participant_ids: [],
  allow_unlisted_participants: true,
  data_collection_start: '2024-01-01T00:00:00Z',
  data_collection_end: '2026-12-31T23:59:59Z',
};

export class StudyCoordinator {
  constructor() {
    this.studyConfig = INTERNAL_FALLBACK_STUDY_CONFIG;
    this.rawStudyConfig = INTERNAL_FALLBACK_STUDY_CONFIG;
    this.currentSongIndex = 0;
    this.uid = this.getOrCreateUID();
    this.studyName = this.getStudyName();
    this.widget = null;
    this.isLoading = false;
    this.backendAvailable = false;
    this.backendChecked = false;
    this.isLikelyMobileDevice = this.detectLikelyMobileDevice();
    this.studyAccessBlocked = false;
    this.studyAccessBlockedStatusCode = null;
    this.studyAccessBlockedMessage = null;

    // Track which songs are synced with server
    this.songSyncStatus = {}; // 'unsaved', 'synced', or 'modified'

    this.localStorageKey = `audio_rating_study_${this.studyName}_${this.uid}`;
    this.uiStateStorageKey = `audio_rating_ui_state_${this.studyName}_${this.uid}`;
    this.localRatings = this.loadLocalRatings();
    this.autoSaveTimer = null;

    this.init();
  }

  t(key, params = {}) {
    return i18n.t(key, params);
  }

  getCurrentLanguage() {
    return i18n.currentLanguage || 'en';
  }

  localizeTextValue(value, defaultLanguage = 'en', fallback = '') {
    if (value === null || value === undefined) {
      return fallback;
    }

    if (typeof value === 'string') {
      return value;
    }

    if (typeof value === 'object') {
      const currentLanguage = this.getCurrentLanguage();
      return (
        value[currentLanguage] ||
        value[defaultLanguage] ||
        value.en ||
        Object.values(value).find(
          (v) => typeof v === 'string' && v.length > 0
        ) ||
        fallback
      );
    }

    return String(value);
  }

  localizeStudyConfig(rawStudyConfig) {
    if (!rawStudyConfig) {
      return rawStudyConfig;
    }

    const defaultLanguage = rawStudyConfig.default_language || 'en';

    return {
      ...rawStudyConfig,
      description: this.localizeTextValue(
        rawStudyConfig.description,
        defaultLanguage,
        ''
      ),
      custom_text_instructions: this.localizeTextValue(
        rawStudyConfig.custom_text_instructions,
        defaultLanguage,
        ''
      ),
      custom_text_thank_you: this.localizeTextValue(
        rawStudyConfig.custom_text_thank_you,
        defaultLanguage,
        ''
      ),
      songs_to_rate: (rawStudyConfig.songs_to_rate || []).map((song) => ({
        ...song,
        display_name: this.localizeTextValue(
          song.display_name,
          defaultLanguage,
          song.media_url || ''
        ),
        description: this.localizeTextValue(
          song.description,
          defaultLanguage,
          ''
        ),
      })),
      rating_dimensions: (rawStudyConfig.rating_dimensions || []).map(
        (dim) => ({
          ...dim,
          display_name: this.localizeTextValue(
            dim.display_name,
            defaultLanguage,
            dim.dimension_title
          ),
          description: this.localizeTextValue(
            dim.description,
            defaultLanguage,
            this.localizeTextValue(
              dim.display_name,
              defaultLanguage,
              dim.dimension_title
            )
          ),
        })
      ),
    };
  }

  getDimensionDisplayName(dimensionTitle) {
    const dim = this.studyConfig.rating_dimensions.find(
      (d) => d.dimension_title === dimensionTitle
    );
    return dim?.display_name || dimensionTitle;
  }

  updateDynamicStudyTranslations() {
    const customInstructions = this.studyConfig?.custom_text_instructions || '';
    const customThankYou = this.studyConfig?.custom_text_thank_you || '';

    i18n.setRuntimeTranslation(
      'study.dynamic.customTextInstructions',
      customInstructions
    );
    i18n.setRuntimeTranslation(
      'study.dynamic.customTextThankYou',
      customThankYou
    );

    const customInstructionsEl = document.getElementById(
      'custom-study-instructions'
    );
    if (customInstructionsEl) {
      customInstructionsEl.style.display = customInstructions
        ? 'block'
        : 'none';
    }

    const customThankYouEl = document.getElementById('custom-thank-you-text');
    if (customThankYouEl) {
      customThankYouEl.style.display = customThankYou ? 'block' : 'none';
    }
  }

  async loadLocalStudyConfig() {
    const study_config_file = './settings/studies_config.json';
    try {
      // Try to load from JSON file
      const response = await fetch(study_config_file);
      if (response.ok) {
        const config = await response.json();
        console.log(
          'Loaded study config from local JSON file "',
          study_config_file,
          '".'
        );

        // The file contains an array of study configs, find the one matching studyName
        // Extract the specific study config based on study_name from URL
        const urlParams = new URLSearchParams(window.location.search);
        const studyName = urlParams.get('study_name');
        this.studyConfig =
          config.studies.find((c) => c.name_short === studyName) ||
          config.studies[0]; // Default to first if not found
        return this.studyConfig;
      }
    } catch (error) {
      console.warn(
        'Could not load local study config from JSON file "',
        study_config_file,
        '", using internal fallback:',
        error
      );
    }

    // Fallback to embedded default config
    return INTERNAL_FALLBACK_STUDY_CONFIG;
  }

  destroy() {
    if (this.widget) {
      this.widget.destroy();
      this.widget = null;
    }
  }

  getDefaultValueForDimension(dimensionName) {
    const dim = this.studyConfig.rating_dimensions.find(
      (d) => d.dimension_title === dimensionName
    );

    if (!dim) {
      console.warn(`Dimension ${dimensionName} not found`);
      return 0;
    }

    if (dim.default_value !== undefined) {
      return dim.default_value;
    }

    // Calculate default if not specified
    const min_value = dim.minimal_value || 0;
    return min_value + Math.floor(dim.num_values / 2);
  }

  getOrCreateUID() {
    const urlParams = new URLSearchParams(window.location.search);
    let uid = urlParams.get('uid');

    if (!uid) {
      uid = 'uid_' + Math.random().toString(36).substr(2, 9);
      const newUrl = `${
        window.location.pathname
      }?uid=${uid}&study_name=${this.getStudyName()}`;
      window.history.replaceState({}, '', newUrl);
    }

    return uid;
  }

  isSongCompletelyRated(songIndex) {
    // For current song being edited, check widget data
    if (songIndex === this.currentSongIndex && this.widget) {
      const currentData = this.widget.getData();
      return this.checkRatingDataComplete(currentData).isComplete;
    }

    // Otherwise check localStorage
    const songKey = `${this.studyName}_song_${songIndex}`;
    const songData = this.localRatings[songKey];

    if (!songData || !songData.data) {
      return false;
    }

    return this.checkRatingDataComplete(songData.data).isComplete;
  }

  checkRatingDataComplete(ratingData) {
    if (!ratingData || Object.keys(ratingData).length === 0) {
      return {
        isComplete: false,
        missingDimensions: this.studyConfig.rating_dimensions.map(
          (dim) => dim.dimension_title
        ), // FIX THIS LINE
      };
    }

    const requiredDimensions = this.studyConfig.rating_dimensions.map(
      (dim) => dim.dimension_title
    ); // AND THIS LINE
    const missingDimensions = [];

    requiredDimensions.forEach((dimName) => {
      // Change from dim to dimName
      if (
        !ratingData[dimName] ||
        !Array.isArray(ratingData[dimName]) ||
        ratingData[dimName].length === 0
      ) {
        missingDimensions.push(dimName);
        return;
      }

      const defaultValue = this.getDefaultValueForDimension(dimName); // Use dimName
      const segments = ratingData[dimName];

      // If user added segments (more than 1), it's modified
      if (segments.length > 1) {
        return;
      }

      // Check the single segment
      const segment = segments[0];
      if (!segment || segment.value === undefined || segment.value === null) {
        missingDimensions.push(dimName);
        return;
      }

      // If value differs from default, it's modified
      if (segment.value !== defaultValue) {
        return;
      }

      // If we get here, dimension still has default value
      missingDimensions.push(dimName);
    });

    const isComplete = missingDimensions.length === 0;

    if (!isComplete) {
      console.log(
        'Incomplete rating data, missing dimensions:',
        missingDimensions
      );
    }

    return {
      isComplete: isComplete,
      missingDimensions: missingDimensions,
    };
  }

  updateAllUI() {
    this.updateSubmitButtonState();
    this.updateSongNavigationUI();
    this.updateSubmitStudyButton();
  }

  getCurrentSongName() {
    const song = this.studyConfig?.songs_to_rate?.[this.currentSongIndex];
    if (song?.display_name) {
      return song.display_name;
    }
    return `Song ${this.currentSongIndex + 1}`;
  }

  getSaveCurrentSongActionLabel() {
    const song = this.getCurrentSongName();
    if (this.backendAvailable) {
      return this.t('study.submit.saveToServerSong', { song });
    }
    return this.t('study.submit.saveLocallySong', { song });
  }

  // In study_coordinator.js, update the updateSubmitButtonState method:

  updateSubmitButtonState() {
    const submitBtn = document.getElementById('submit-rating');
    if (!submitBtn) return;

    const saveActionText = this.getSaveCurrentSongActionLabel();

    if (!this.backendAvailable) {
      submitBtn.disabled = true;
      submitBtn.textContent = this.t('study.submit.serverUnavailable');
      return;
    }

    if (!this.widget) {
      submitBtn.disabled = true;
      submitBtn.textContent = this.t('study.submit.loading');
      return;
    }

    const ratingData = this.widget.getData();
    const result = this.checkRatingDataComplete(ratingData);

    // First check if the song is completely rated
    if (!result.isComplete) {
      submitBtn.disabled = true;
      if (result.missingDimensions.length > 0) {
        const missingDimensionNames = result.missingDimensions.map((dim) =>
          this.getDimensionDisplayName(dim)
        );
        submitBtn.textContent = `${saveActionText} — ${this.t(
          'study.submit.stillToRate',
          {
            dimensions: missingDimensionNames.join(', '),
          }
        )}`;
      } else {
        submitBtn.textContent = `${saveActionText} — ${this.t(
          'study.submit.completeAll'
        )}`;
      }
      return;
    }

    // Only if song is complete, check sync status
    if (this.songSyncStatus[this.currentSongIndex] === 'synced') {
      submitBtn.disabled = true;
      submitBtn.textContent = this.t('study.submit.alreadySaved');
    } else {
      submitBtn.disabled = false;
      submitBtn.textContent = saveActionText;
    }
  }

  getSongStatus(songIndex) {
    const isComplete = this.isSongCompletelyRated(songIndex);

    if (!isComplete) {
      return {
        status: 'incomplete',
        icon: '○',
        color: '#ef4444',
        label: this.t('study.syncStatus.incomplete'),
      };
    } else if (this.songSyncStatus[songIndex] === 'synced') {
      return {
        status: 'saved',
        icon: '✓',
        color: '#10b981',
        label: this.t('study.syncStatus.saved'),
      };
    } else {
      return {
        status: 'ready',
        icon: '!',
        color: '#facc15',
        label: this.t('study.syncStatus.ready'),
      };
    }
  }

  updateSongNavigationUI() {
    const songListDiv = document.getElementById('song-list');
    songListDiv.innerHTML = '';

    const currentSongDescription = document.getElementById(
      'current-song-description'
    );
    if (
      this.currentSongIndex !== undefined &&
      this.currentSongIndex < this.studyConfig.songs_to_rate.length
    ) {
      currentSongDescription.textContent =
        this.studyConfig.songs_to_rate[this.currentSongIndex].description ||
        this.t('study.songDescriptionMissing');
    }

    this.studyConfig.songs_to_rate.forEach((song, index) => {
      const status = this.getSongStatus(index);

      const buttonContainer = document.createElement('div');
      buttonContainer.className = 'song-nav-container';

      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'song-nav';
      button.textContent = `${index + 1}. ${song.display_name}`;
      button.dataset.index = index;

      if (index === this.currentSongIndex) {
        button.classList.add('active');
      }

      button.addEventListener('click', () => {
        this.loadSong(index);
      });

      const indicator = document.createElement('span');
      indicator.className = `completion-indicator ${status.status}`;
      indicator.title = status.label;
      indicator.textContent = status.icon;
      indicator.style.cssText = `
        position: absolute;
        top: -5px;
        right: -5px;
        width: 16px;
        height: 16px;
        border-radius: 50%;
        font-size: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: ${status.color};
        color: white;
        border: 1px solid white;
        box-shadow: 0 1px 3px rgba(0,0,0,0.2);
        pointer-events: none;
      `;

      buttonContainer.appendChild(button);
      buttonContainer.appendChild(indicator);
      songListDiv.appendChild(buttonContainer);
    });
  }

  getStudyName() {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('study_name') || 'default';
  }

  async init() {
    this.rawStudyConfig = await this.loadLocalStudyConfig();
    this.studyConfig = this.localizeStudyConfig(this.rawStudyConfig);

    await this.checkBackendAvailability();

    if (this.backendAvailable) {
      const configLoaded = await this.loadStudyConfigFromBackend();
      if (!configLoaded) {
        console.warn(
          'Failed to load study config from backend, using local config.'
        );
      } else {
        console.log(
          'Successfully loaded study config from backend. Replaced local default config with backend config.'
        );
        // No need to set this.studyConfig here since loadStudyConfigFromBackend already sets it.
      }
    } else {
      this.showOfflineNotice();
      console.warn('Backend not available. Using local fallback config.');
      // Initialize localRatings for all songs with empty data structures
      for (let i = 0; i < this.studyConfig.songs_to_rate.length; i++) {
        const songKey = `${this.studyName}_song_${i}`;

        // Only initialize if not already in localStorage
        if (!this.localRatings[songKey]) {
          const emptyRatings = {};
          this.studyConfig.rating_dimensions.forEach((dim) => {
            emptyRatings[dim.dimension_title] = [];
          });

          this.localRatings[songKey] = {
            data: emptyRatings,
            source: 'local',
            timestamp: new Date().toISOString(),
          };
        }

        this.songSyncStatus[i] = 'unsaved';
      }

      this.saveLocalRatings();
    }

    document.getElementById('song-count').textContent =
      this.studyConfig.songs_to_rate.length; // in introduction phase
    document.getElementById('song-count-thanks').textContent =
      this.studyConfig.songs_to_rate.length; // in thanks phase
    document.getElementById('rating-dimensions-count').textContent =
      this.studyConfig.rating_dimensions.length; // in introduction phase
    document.getElementById('rating-dimensions-count-thanks').textContent =
      this.studyConfig.rating_dimensions.length; // in thanks phase

    const ratePromptEl = document.getElementById('study-rate-prompt');
    if (ratePromptEl) {
      ratePromptEl.textContent = this.t('study.ratePrompt', {
        songs: this.studyConfig.songs_to_rate.length,
        dimensions: this.studyConfig.rating_dimensions.length,
      });
    }

    const completionMessageEl = document.getElementById('completion-message');
    if (completionMessageEl) {
      completionMessageEl.textContent = this.t('study.completionMessage', {
        songs: this.studyConfig.songs_to_rate.length,
        dimensions: this.studyConfig.rating_dimensions.length,
      });
    }

    // Fill song-list-intro and rating-dimensions-list-intro in introduction phase
    const songListIntro = document.getElementById('song-list-intro');
    for (
      let song_index = 0;
      song_index < this.studyConfig.songs_to_rate.length;
      song_index++
    ) {
      const song = this.studyConfig.songs_to_rate[song_index];
      const li = document.createElement('li');
      li.textContent = `${song.display_name}: ${
        song.description || this.t('study.songIntroDescriptionMissing')
      }`;
      songListIntro.appendChild(li);

      try {
        const songResponse = await fetch(song.media_url, { method: 'HEAD' });
        if (!songResponse.ok) {
          console.error(
            'Song with index ',
            song_index,
            ' is not accessible at URL ',
            song.media_url,
            ' with status code ',
            songResponse.status
          );
          this.showStatusMessage(
            this.t('study.messages.warningSongNotAccessible', {
              song: song.display_name,
              url: song.media_url,
            }),
            'warning'
          );
        }
      } catch (error) {
        console.error(
          'Failed to access song with index ',
          song_index,
          ' at URL ',
          song.media_url,
          ' with error: ',
          error
        );
        this.showStatusMessage(
          this.t('study.messages.warningSongFetchFailed', {
            song: song.display_name,
            url: song.media_url,
          }),
          'warning'
        );
      }
    }

    const ratingDimensionsListIntro = document.getElementById(
      'rating-dimensions-list-intro'
    );
    this.studyConfig.rating_dimensions.forEach((dim) => {
      const li = document.createElement('li');
      li.textContent = `${dim.display_name || dim.dimension_title}: ${
        dim.description || this.t('study.songIntroDescriptionMissing')
      }`;
      ratingDimensionsListIntro.appendChild(li);
    });

    // Fill study-name-title and study-name-welcome
    document.getElementById('study-name-title').textContent =
      this.studyConfig.name; // title in instructions phase
    document.getElementById('study-name-thanks').textContent =
      this.studyConfig.name; // thanks phase
    // This is the name and the description of the study that participants see in the welcome message. It can be more friendly and descriptive than the title.
    document.getElementById('study-name-welcome').textContent =
      this.studyConfig.name +
      (this.studyConfig.description
        ? ` - ${this.studyConfig.description}`
        : '');

    // Update the page title from "Audio Rating Study" to the specific study name for better user experience
    document.title = `${this.t('study.pageTitlePrefix')}: ${
      this.studyConfig.name
    }`;
    this.updateDynamicStudyTranslations();
    i18n.applyTranslations(document);

    if (this.studyAccessBlocked) {
      this.applyBlockedStudyUI();
    }

    document.getElementById('total-songs').textContent =
      this.studyConfig.songs_to_rate.length;

    this.updateSongNavigationUI();

    document
      .getElementById('begin-study')
      .addEventListener('click', () => this.startRating());
    document
      .getElementById('submit-rating')
      .addEventListener('click', () => this.submitRating());
    document
      .getElementById('download-data')
      .addEventListener('click', () => this.downloadAllRatings());

    // Add event listener for the submit study button - show confirmation modal first
    document.getElementById('submit-study').addEventListener('click', () => {
      this.showSubmitConfirmationModal();
    });

    // Wire up modal buttons
    document
      .getElementById('modal-confirm-btn')
      .addEventListener('click', () => {
        this.hideSubmitConfirmationModal();
        if (this.areAllSongsSavedToServer()) {
          this.completeStudy();
        }
      });
    document
      .getElementById('modal-cancel-btn')
      .addEventListener('click', () => {
        this.hideSubmitConfirmationModal();
      });

    // Close modal when clicking the overlay (outside the modal box)
    document.querySelector('.modal-overlay')?.addEventListener('click', () => {
      this.hideSubmitConfirmationModal();
    });

    // Close modal on Escape key
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        const modal = document.getElementById('submit-confirmation-modal');
        if (modal && modal.classList.contains('show')) {
          this.hideSubmitConfirmationModal();
        }
      }
    });

    const restoredPhase = await this.restoreProgressAfterInit();
    if (!restoredPhase) {
      this.showPhase('instructions-phase');
    }
    this.updateBackendStatus();

    this._onBeforeUnload = () => {
      this.flushCurrentSongToLocalStorage();
      this.saveUIState();
    };
    window.addEventListener('beforeunload', this._onBeforeUnload);

    window.addEventListener('i18n:languageChanged', () => {
      this.onLanguageChanged().catch((error) => {
        console.error(
          'Failed to refresh study UI after language change:',
          error
        );
      });
    });
  }

  async onLanguageChanged() {
    this.studyConfig = this.localizeStudyConfig(this.rawStudyConfig);

    document.title = `${this.t('study.pageTitlePrefix')}: ${
      this.studyConfig.name
    }`;
    document.getElementById('study-name-title').textContent =
      this.studyConfig.name;
    document.getElementById('study-name-thanks').textContent =
      this.studyConfig.name;
    document.getElementById('study-name-welcome').textContent =
      this.studyConfig.name +
      (this.studyConfig.description
        ? ` - ${this.studyConfig.description}`
        : '');

    const ratePromptEl = document.getElementById('study-rate-prompt');
    if (ratePromptEl) {
      ratePromptEl.textContent = this.t('study.ratePrompt', {
        songs: this.studyConfig.songs_to_rate.length,
        dimensions: this.studyConfig.rating_dimensions.length,
      });
    }

    const completionMessageEl = document.getElementById('completion-message');
    if (completionMessageEl) {
      completionMessageEl.textContent = this.t('study.completionMessage', {
        songs: this.studyConfig.songs_to_rate.length,
        dimensions: this.studyConfig.rating_dimensions.length,
      });
    }

    const songListIntro = document.getElementById('song-list-intro');
    if (songListIntro) {
      songListIntro.innerHTML = '';
      for (
        let song_index = 0;
        song_index < this.studyConfig.songs_to_rate.length;
        song_index++
      ) {
        const song = this.studyConfig.songs_to_rate[song_index];
        const li = document.createElement('li');
        li.textContent = `${song.display_name}: ${
          song.description || this.t('study.songIntroDescriptionMissing')
        }`;
        songListIntro.appendChild(li);
      }
    }

    const ratingDimensionsListIntro = document.getElementById(
      'rating-dimensions-list-intro'
    );
    if (ratingDimensionsListIntro) {
      ratingDimensionsListIntro.innerHTML = '';
      this.studyConfig.rating_dimensions.forEach((dim) => {
        const li = document.createElement('li');
        li.textContent = `${dim.display_name || dim.dimension_title}: ${
          dim.description || this.t('study.songIntroDescriptionMissing')
        }`;
        ratingDimensionsListIntro.appendChild(li);
      });
    }
    this.updateDynamicStudyTranslations();
    i18n.applyTranslations(document);

    if (this.studyAccessBlocked) {
      this.studyAccessBlockedMessage = this.getBlockedStudyMessage();
      this.applyBlockedStudyUI();
    }

    this.updateBackendStatus();
    this.updateAllUI();

    // If rating widget is currently active, reload current song so widget title/
    // dimension display names/descriptions switch language as well.
    if (this.widget && this.showingPhase('rating-phase')) {
      await this.loadSong(this.currentSongIndex);
    }
  }

  showingPhase(phaseId) {
    const phaseEl = document.getElementById(phaseId);
    return Boolean(phaseEl && phaseEl.classList.contains('active'));
  }

  detectLikelyMobileDevice() {
    const userAgent = navigator.userAgent || '';
    const userAgentMatchesMobile =
      /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini|Mobile/i.test(
        userAgent
      );
    const userAgentDataMatchesMobile = Boolean(
      navigator.userAgentData && navigator.userAgentData.mobile
    );

    const hasCoarsePointer = Boolean(
      window.matchMedia && window.matchMedia('(pointer: coarse)').matches
    );
    const hasTouch =
      (navigator.maxTouchPoints || 0) > 1 || 'ontouchstart' in window;
    const minViewportEdge = Math.min(
      window.screen?.width || window.innerWidth,
      window.screen?.height || window.innerHeight
    );
    const smallViewport = minViewportEdge <= 820;

    return (
      userAgentDataMatchesMobile ||
      userAgentMatchesMobile ||
      (hasCoarsePointer && hasTouch && smallViewport)
    );
  }

  async checkBackendAvailability() {
    try {
      const response = await fetch(`${AR_SETTINGS.API_BASE_URL}`, {
        method: 'GET',
        headers: { Accept: 'application/json' },
      });

      this.backendAvailable = response.ok;
      this.backendChecked = true;

      if (!response.ok) {
        this.showBackendError(
          new Error(`Backend returned ${response.status}`),
          response.status,
          this.t('study.errors.backendUnexpectedStatus')
        );
      }
    } catch (error) {
      this.backendAvailable = false;
      this.backendChecked = true;
      this.showBackendError(
        error,
        null,
        this.t('study.errors.backendRequestFailed')
      );
    }
  }

  async loadStudyConfigFromBackend() {
    let ratingLoadFailed = false;

    try {
      const response = await this.fetchWithRetry(
        `${AR_SETTINGS.API_BASE_URL}/participants/${this.uid}/studies/${this.studyName}/config`
      );

      if (response.ok) {
        const studyConfig = await response.json();
        this.rawStudyConfig = studyConfig;
        this.studyConfig = this.localizeStudyConfig(studyConfig);

        for (let i = 0; i < this.studyConfig.songs_to_rate.length; i++) {
          try {
            const ratingsResponse = await this.fetchWithRetry(
              `${AR_SETTINGS.API_BASE_URL}/participants/${this.uid}/studies/${this.studyName}/songs/${i}/ratings`
            );

            if (ratingsResponse.ok) {
              const data = await ratingsResponse.json();
              const songKey = `${this.studyName}_song_${i}`;
              const existingLocalEntry = this.localRatings[songKey];
              const keepLocal =
                this.shouldKeepLocalSongData(existingLocalEntry);

              if (data.has_ratings) {
                const backendRatings = {};
                if (data.ratings) {
                  Object.keys(data.ratings).forEach((ratingName) => {
                    backendRatings[ratingName] =
                      data.ratings[ratingName].segments || [];
                  });
                }

                if (keepLocal) {
                  this.songSyncStatus[i] = 'modified';
                } else {
                  this.localRatings[songKey] = {
                    data: backendRatings,
                    source: 'backend',
                    timestamp: new Date().toISOString(),
                  };
                  this.songSyncStatus[i] = 'synced';
                }
              } else {
                if (keepLocal) {
                  this.songSyncStatus[i] = 'modified';
                } else {
                  this.initializeEmptySongRatings(i);
                }
              }
            } else {
              ratingLoadFailed = true;
              console.error(
                `Failed to load backend ratings for song ${i}: HTTP ${ratingsResponse.status}`
              );
              const songKey = `${this.studyName}_song_${i}`;
              if (this.shouldKeepLocalSongData(this.localRatings[songKey])) {
                this.songSyncStatus[i] = 'modified';
              } else {
                this.initializeEmptySongRatings(i);
              }
            }
          } catch (error) {
            ratingLoadFailed = true;
            console.error(
              `Failed to load backend ratings for song ${i}`,
              error
            );
            const songKey = `${this.studyName}_song_${i}`;
            if (this.shouldKeepLocalSongData(this.localRatings[songKey])) {
              this.songSyncStatus[i] = 'modified';
            } else {
              this.initializeEmptySongRatings(i);
            }
          }

          // Verify that the song media URL is accessible
          try {
            const songResponse = await fetch(
              this.studyConfig.songs_to_rate[i].media_url,
              { method: 'HEAD' }
            );
            if (!songResponse.ok) {
              this.showStatusMessage(
                this.t('study.messages.warningSongNotAccessible', {
                  song: this.studyConfig.songs_to_rate[i].display_name,
                  url: this.studyConfig.songs_to_rate[i].media_url,
                }),
                'warning'
              );
            }
          } catch (error) {
            this.showStatusMessage(
              this.t('study.messages.warningSongFetchFailed', {
                song: this.studyConfig.songs_to_rate[i].display_name,
                url: this.studyConfig.songs_to_rate[i].media_url,
              }),
              'warning'
            );
          }
        }

        this.saveLocalRatings();
        this.updateSubmitStudyButton();
        this.updateSongNavigationUI();

        if (ratingLoadFailed) {
          this.showStatusMessage(
            this.t('study.messages.genericTechnicalDifficulties'),
            'error'
          );
        }

        return true;
      } else {
        console.log(
          'Failed to load config from backend with backend status code:',
          response.status
        );
        if (response.status === 403) {
          this.showBackendError(
            null,
            403,
            this.t('study.errors.accessDeniedConfig')
          );
        } else if (response.status === 404) {
          this.showBackendError(
            null,
            404,
            this.t('study.errors.configNotFound')
          );
        } else {
          this.showBackendError(
            new Error(`HTTP ${response.status}`),
            response.status
          );
        }
        return false;
      }
    } catch (error) {
      console.warn('Failed to load config from backend due to error:', error);
      return false;
    }
  }

  async startRating() {
    this.showPhase('rating-phase');
    this.saveUIState();
    await this.loadSong(this.currentSongIndex);
  }

  async loadSong(songIndex) {
    // Auto-save current song before switching
    console.log('=== LOAD SONG DEBUG ===');
    console.log('songIndex:', songIndex);
    console.log('song:', this.studyConfig.songs_to_rate[songIndex]);
    console.log('rating_dimensions:', this.studyConfig.rating_dimensions);
    console.log(
      'rating_dimensions length:',
      this.studyConfig.rating_dimensions.length
    );

    if (this.widget) {
      await this.autoSaveCurrentSong();

      // If current song was synced, check if data changed
      if (this.songSyncStatus[this.currentSongIndex] === 'synced') {
        const currentData = this.widget.getData();
        const songKey = `${this.studyName}_song_${this.currentSongIndex}`;
        const savedData = this.localRatings[songKey];

        if (
          savedData &&
          JSON.stringify(currentData) !== JSON.stringify(savedData.data)
        ) {
          this.songSyncStatus[this.currentSongIndex] = 'modified';
          this.updateAllUI();
        }
      }

      this.widget.destroy();
      this.widget = null;
    }

    this.currentSongIndex = songIndex;
    this.saveUIState();
    const song = this.studyConfig.songs_to_rate[songIndex];

    document.getElementById('current-song-number').textContent = songIndex + 1;

    this.updateSongNavigationUI();
    this.clearStatusMessages();
    this.setLoading(true, true);

    try {
      const widgetContainer = document.getElementById(
        'rating-widget-container'
      );
      widgetContainer.innerHTML = '';

      this.widget = await AudioRatingWidget.create({
        container: '#rating-widget-container',
        audioUrl: song.media_url,
        rating_dimensions: this.studyConfig.rating_dimensions,
        height: 140,
        waveColor: '#bfc8d6',
        progressColor: '#6b46c1',
        with_instructions: false,
        with_volume_slider: true,
        with_step_labels_legend: true,
        show_download_button: false,
        show_timeline: true,
        title: '',
      });

      const songKey = `${this.studyName}_song_${songIndex}`;
      if (this.localRatings[songKey]) {
        this.widget.setData(this.localRatings[songKey].data);
      }

      this.updateSubmitButtonState();

      this.widget.on('change', () => {
        // If song was synced but user makes changes, mark as modified
        if (this.songSyncStatus[this.currentSongIndex] === 'synced') {
          this.songSyncStatus[this.currentSongIndex] = 'modified';
        }
        this.scheduleAutoSaveCurrentSong();
        this.updateAllUI();
      });

      this.updateAllUI();

      setTimeout(() => {
        this.updateSubmitButtonState();
      }, 10);
    } catch (error) {
      console.error('Error loading song:', error);
      this.showStatusMessage(
        this.t('study.ratingLoadingError', {
          song: song.display_name,
          url: song.media_url,
        }),
        'error'
      );
    } finally {
      this.setLoading(false, true);
    }
  }

  async autoSaveCurrentSong() {
    if (!this.widget) return;

    const ratingData = this.widget.getData();
    if (Object.keys(ratingData).length === 0) {
      return;
    }

    const songKey = this.getSongKey();
    const song = this.studyConfig.songs_to_rate[this.currentSongIndex];

    this.localRatings[songKey] = {
      data: ratingData,
      timestamp: new Date().toISOString(),
      study: this.studyName,
      songIndex: this.currentSongIndex,
      songName: song.display_name,
      songUrl: song.media_url,
      source: 'local',
    };

    try {
      this.saveLocalRatings();
      this.saveUIState();
    } catch (error) {
      console.error('Auto-save failed:', error);
    }
  }

  scheduleAutoSaveCurrentSong(delayMs = 400) {
    if (this.autoSaveTimer) {
      clearTimeout(this.autoSaveTimer);
    }
    this.autoSaveTimer = setTimeout(async () => {
      this.autoSaveTimer = null;
      await this.autoSaveCurrentSong();
    }, delayMs);
  }

  flushCurrentSongToLocalStorage() {
    if (this.autoSaveTimer) {
      clearTimeout(this.autoSaveTimer);
      this.autoSaveTimer = null;
    }

    if (!this.widget) return;

    const ratingData = this.widget.getData();
    if (!ratingData || Object.keys(ratingData).length === 0) return;

    const songKey = this.getSongKey();
    const song = this.studyConfig.songs_to_rate[this.currentSongIndex];

    this.localRatings[songKey] = {
      data: ratingData,
      timestamp: new Date().toISOString(),
      study: this.studyName,
      songIndex: this.currentSongIndex,
      songName: song?.display_name,
      songUrl: song?.media_url,
      source: 'local',
    };

    this.saveLocalRatings();
  }

  loadUIState() {
    try {
      const raw = localStorage.getItem(this.uiStateStorageKey);
      return raw ? JSON.parse(raw) : null;
    } catch (error) {
      console.warn('Error loading UI state:', error);
      return null;
    }
  }

  saveUIState() {
    try {
      const activePhase = document.querySelector('.study-phase.active');
      const phaseId = activePhase?.id || 'instructions-phase';
      const state = {
        phaseId,
        currentSongIndex: this.currentSongIndex,
        updatedAt: new Date().toISOString(),
      };
      localStorage.setItem(this.uiStateStorageKey, JSON.stringify(state));
      return true;
    } catch (error) {
      console.warn('Error saving UI state:', error);
      return false;
    }
  }

  async restoreProgressAfterInit() {
    if (this.studyAccessBlocked) return false;

    const savedState = this.loadUIState();
    if (!savedState || !savedState.phaseId) return false;

    if (savedState.phaseId === 'rating-phase') {
      const maxSongIndex = Math.max(
        0,
        this.studyConfig.songs_to_rate.length - 1
      );
      const restoredSongIndex = Math.max(
        0,
        Math.min(maxSongIndex, Number(savedState.currentSongIndex) || 0)
      );
      this.showPhase('rating-phase');
      await this.loadSong(restoredSongIndex);
      return true;
    }

    if (savedState.phaseId === 'completion-phase') {
      this.showPhase('completion-phase');
      return true;
    }

    return false;
  }

  getSongKey() {
    return `${this.studyName}_song_${this.currentSongIndex}`;
  }

  loadLocalRatings() {
    try {
      const stored = localStorage.getItem(this.localStorageKey);
      return stored ? JSON.parse(stored) : {};
    } catch (error) {
      console.error('Error loading local ratings:', error);
      return {};
    }
  }

  saveLocalRatings() {
    try {
      localStorage.setItem(
        this.localStorageKey,
        JSON.stringify(this.localRatings)
      );
      return true;
    } catch (error) {
      console.error('Error saving local ratings:', error);
      return false;
    }
  }

  createEmptyRatings() {
    const emptyRatings = {};
    this.studyConfig.rating_dimensions.forEach((dim) => {
      emptyRatings[dim.dimension_title] = [];
    });
    return emptyRatings;
  }

  initializeEmptySongRatings(songIndex) {
    const songKey = `${this.studyName}_song_${songIndex}`;

    this.localRatings[songKey] = {
      data: this.createEmptyRatings(),
      source: 'local',
      timestamp: new Date().toISOString(),
    };
    this.songSyncStatus[songIndex] = 'unsaved';
  }

  hasAnyRatingSegments(ratingData) {
    if (!ratingData || typeof ratingData !== 'object') return false;
    return Object.values(ratingData).some(
      (segments) => Array.isArray(segments) && segments.length > 0
    );
  }

  shouldKeepLocalSongData(localEntry) {
    if (!localEntry || typeof localEntry !== 'object') return false;
    if (localEntry.source !== 'local') return false;
    return this.hasAnyRatingSegments(localEntry.data);
  }

  wait(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  async fetchWithRetry(url, options = {}, retryDelay = 2000) {
    let lastError = null;

    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        const response = await fetch(url, options);
        if (response.ok || attempt === 1) {
          return response;
        }
      } catch (error) {
        lastError = error;
        if (attempt === 1) {
          throw error;
        }
      }

      await this.wait(retryDelay);
    }

    throw lastError || new Error('Request failed');
  }

  async submitRating() {
    if (this.isLoading || !this.widget) return;

    const ratingData = this.widget.getData();
    if (Object.keys(ratingData).length === 0) {
      this.showStatusMessage(this.t('study.messages.noRatingsToSave'), 'error');
      return;
    }

    const result = this.checkRatingDataComplete(ratingData);
    if (!result.isComplete) {
      this.showStatusMessage(
        this.t('study.messages.completeBeforeSubmit'),
        'error'
      );
      return;
    }

    this.setLoading(true, false);
    this.clearStatusMessages();

    const songKey = this.getSongKey();
    const song = this.studyConfig.songs_to_rate[this.currentSongIndex];
    const submissionTimestamp = new Date().toISOString();

    // Save locally
    this.localRatings[songKey] = {
      data: ratingData,
      timestamp: submissionTimestamp,
      study: this.studyName,
      songIndex: this.currentSongIndex,
      songName: song.display_name,
      songUrl: song.media_url,
      source: 'local',
    };

    this.saveLocalRatings();
    this.updateAllUI();

    try {
      if (this.backendAvailable) {
        const backendUrl = `${AR_SETTINGS.API_BASE_URL}/participants/${this.uid}/studies/${this.studyName}/songs/${this.currentSongIndex}/ratings`;

        const response = await this.fetchWithRetry(backendUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            timestamp: submissionTimestamp,
            ratings: ratingData,
          }),
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        // Update sync status
        this.songSyncStatus[this.currentSongIndex] = 'synced';

        // Update source to backend
        this.localRatings[songKey].source = 'backend';
        this.saveLocalRatings();

        this.showStatusMessage(
          this.t('study.messages.savedToServer'),
          'success'
        );
      }
    } catch (error) {
      console.error('Failed to save ratings to backend:', error);
      this.showStatusMessage(
        this.t('study.messages.genericTechnicalDifficulties'),
        'error'
      );
    } finally {
      this.setLoading(false, false);
      this.updateAllUI();
    }
  }

  updateBackendStatus() {
    const statusEl = document.getElementById('backend-status');
    const storageEl = document.getElementById('storage-status');

    if (!this.backendChecked) {
      statusEl.className = 'backend-status connecting';
      statusEl.textContent = this.t('study.backendStatus.checking');
      if (storageEl) {
        storageEl.textContent = '';
        storageEl.style.display = 'none';
      }
      return;
    }

    if (this.backendAvailable) {
      statusEl.className = 'backend-status online';
      statusEl.textContent = this.t('study.backendStatus.connected');
      if (storageEl) {
        storageEl.textContent = '';
        storageEl.style.display = 'none';
      }
    } else {
      statusEl.className = 'backend-status offline';
      statusEl.textContent = this.t('study.backendStatus.offline');
      if (storageEl) {
        storageEl.style.display = 'block';
        storageEl.textContent = this.t('study.backendStatus.saveLocalOnly');
      }
    }
  }

  showOfflineNotice() {
    document.getElementById('backend-notice').style.display = 'block';

    const submitBtn = document.getElementById('submit-rating');
    if (submitBtn) {
      submitBtn.textContent = this.getSaveCurrentSongActionLabel();
    }
  }

  showStatusMessage(message, type = 'info') {
    // Use the new user message system
    this.showUserMessage(
      message,
      type,
      type === 'success' || type === 'warning' ? 10000 : 0
    );
  }

  clearStatusMessages() {
    const statusDiv = document.getElementById('status-messages');
    statusDiv.innerHTML = '';
  }

  setLoading(loading, isSongLoading = false) {
    this.isLoading = loading;
    const submitBtn = document.getElementById('submit-rating');
    const loadingOverlay = document.getElementById('loading-overlay');

    if (submitBtn) {
      submitBtn.disabled = loading;
      submitBtn.textContent = loading
        ? this.t('study.submit.saving')
        : this.getSaveCurrentSongActionLabel();
    }

    if (loadingOverlay) {
      if (loading && isSongLoading) {
        loadingOverlay.classList.add('active');
      } else {
        loadingOverlay.classList.remove('active');
      }
    }
  }

  areAllSongsSavedToServer() {
    for (let i = 0; i < this.studyConfig.songs_to_rate.length; i++) {
      // Check if song is both complete AND synced with server
      const isComplete = this.isSongCompletelyRated(i);
      const isSynced = this.songSyncStatus[i] === 'synced';

      if (!isComplete || !isSynced) {
        return false;
      }
    }
    return true;
  }

  updateSubmitStudyButton() {
    const submitStudyBtn = document.getElementById('submit-study');
    const statusEl = document.getElementById('study-completion-status');

    if (!submitStudyBtn || !statusEl) return;

    const allSaved = this.areAllSongsSavedToServer();

    if (allSaved) {
      submitStudyBtn.disabled = false;
      submitStudyBtn.textContent = this.t('study.submitStudy');
      statusEl.textContent = this.t('study.studyStatus.allSaved');
      statusEl.className = 'study-complete-message';
    } else {
      submitStudyBtn.disabled = true;
      submitStudyBtn.textContent = this.t('study.submitStudy');

      // Count how many songs are saved
      let savedCount = 0;

      for (let i = 0; i < this.studyConfig.songs_to_rate.length; i++) {
        if (this.songSyncStatus[i] === 'synced') savedCount++;
      }

      statusEl.textContent = this.t('study.studyStatus.savedCount', {
        saved: savedCount,
        total: this.studyConfig.songs_to_rate.length,
      });
      statusEl.className = 'study-incomplete-message';
    }
  }

  completeStudy() {
    const hasLocalData = Object.keys(this.localRatings).length > 0;

    if (!this.backendAvailable && hasLocalData) {
      document.getElementById('completion-message').innerHTML = this.t(
        'study.offlineCompletion'
      );
      document.getElementById('download-section').style.display = 'block';
    }

    this.showPhase('completion-phase');
    this.saveUIState();
  }

  downloadAllRatings() {
    const dataStr = JSON.stringify(this.localRatings, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);

    const link = document.createElement('a');
    link.href = url;
    link.download = `audio_ratings_${this.studyName}_${this.uid}_${
      new Date().toISOString().split('T')[0]
    }.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    setTimeout(() => URL.revokeObjectURL(url), 100);
  }

  showPhase(phaseId) {
    document.querySelectorAll('.study-phase').forEach((phase) => {
      phase.classList.remove('active');
    });

    document.getElementById(phaseId).classList.add('active');

    const instructionsBanner = document.getElementById('instructions-banner');
    const mobileWarningBanner = document.getElementById(
      'mobile-warning-banner'
    );

    let hasVisibleTopBanner = false;

    if (instructionsBanner) {
      const showInstructionsBanner =
        phaseId === 'rating-phase' && !instructionsBanner.dataset.userDismissed;
      instructionsBanner.classList.toggle('hidden', !showInstructionsBanner);
      hasVisibleTopBanner = hasVisibleTopBanner || showInstructionsBanner;
    }

    if (mobileWarningBanner) {
      const showMobileBanner =
        phaseId === 'instructions-phase' &&
        this.isLikelyMobileDevice &&
        !mobileWarningBanner.dataset.userDismissed;
      mobileWarningBanner.classList.toggle('hidden', !showMobileBanner);
      hasVisibleTopBanner = hasVisibleTopBanner || showMobileBanner;
    }

    document.body.classList.toggle('top-banner-visible', hasVisibleTopBanner);
    this.saveUIState();
  }

  // Add these methods to the StudyCoordinator class (put them after the constructor)

  showUserMessage(message, type = 'info', duration = 5000) {
    // Remove existing messages of same type
    this.clearUserMessages(type);

    const messageDiv = document.createElement('div');
    messageDiv.className = `user-message ${type}-message`;
    messageDiv.innerHTML = `
    <div class="message-content">
      ${
        type === 'error'
          ? '⚠️ '
          : type === 'success'
            ? '✓ '
            : type === 'warning'
              ? '⚠️ '
              : ''
      }
      ${message}
    </div>
    <button class="dismiss-message">×</button>
  `;

    // Add to messages container
    const container = document.getElementById('user-messages');
    if (container) {
      container.appendChild(messageDiv);
    } else {
      console.error('Messages container not found');
      return;
    }

    // Auto-dismiss for non-error messages
    if (type !== 'error' && duration > 0) {
      setTimeout(() => {
        if (messageDiv.parentNode) messageDiv.remove();
      }, duration);
    }

    // Add dismiss button functionality
    const dismissBtn = messageDiv.querySelector('.dismiss-message');
    if (dismissBtn) {
      dismissBtn.addEventListener('click', () => {
        messageDiv.remove();
      });
    }
  }

  disableBeginStudyButton(reason = null) {
    const resolvedReason = reason || this.t('study.errors.beginStudyDisabled');
    const beginBtn = document.getElementById('begin-study');
    if (!beginBtn) return;

    beginBtn.disabled = true;
    beginBtn.textContent = resolvedReason;
    beginBtn.style.opacity = '0.6';
    beginBtn.style.cursor = 'not-allowed';

    // Store the original state so we can restore it if needed
    if (!beginBtn.dataset.originalText) {
      beginBtn.dataset.originalText = this.t('study.beginButton');
    }
  }

  clearUserMessages(type = null) {
    const container = document.getElementById('user-messages');
    if (!container) return;

    if (type) {
      // Remove only messages of specific type
      const messages = container.querySelectorAll(`.${type}-message`);
      messages.forEach((msg) => {
        if (msg.parentNode) msg.remove();
      });
    } else {
      // Remove all messages
      container.innerHTML = '';
    }
  }

  getBlockedStudyMessage() {
    if (this.studyAccessBlockedStatusCode === 403) {
      return this.t('study.errors.accessDeniedConfig');
    }

    if (this.studyAccessBlockedStatusCode === 404) {
      return this.t('study.errors.configNotFound');
    }

    if (this.studyAccessBlockedStatusCode === 500) {
      return this.t('study.errors.backend500');
    }

    return (
      this.studyAccessBlockedMessage ||
      this.t('study.errors.beginStudyDisabled')
    );
  }

  applyBlockedStudyUI(message = null) {
    const blockedMessage = message || this.getBlockedStudyMessage();

    const titleEl = document.getElementById('study-name-title');
    if (titleEl) {
      titleEl.textContent = '';
    }

    const customInstructionsEl = document.getElementById(
      'custom-study-instructions'
    );
    if (customInstructionsEl) {
      customInstructionsEl.style.display = 'none';
    }

    const introContent = document.getElementById('study-intro-content');
    if (introContent) {
      introContent.style.display = 'none';
    }

    const blockedMessageEl = document.getElementById('study-blocked-message');
    if (blockedMessageEl) {
      blockedMessageEl.textContent = '';
      const messageParagraphs = String(blockedMessage)
        .split(/\n\s*\n/)
        .map((paragraph) => paragraph.trim())
        .filter(Boolean);

      if (messageParagraphs.length === 0) {
        blockedMessageEl.textContent = blockedMessage;
      } else {
        messageParagraphs.forEach((paragraph) => {
          const paragraphEl = document.createElement('p');
          paragraphEl.textContent = paragraph;
          blockedMessageEl.appendChild(paragraphEl);
        });
      }

      blockedMessageEl.style.display = '';
    }
  }

  // Helper method to show backend errors
  showBackendError(error, statusCode = null, ui_message = null) {
    let message;
    let shouldDisableStudy = false;

    if (statusCode === 403) {
      message = ui_message || this.t('study.errors.backend403');
      shouldDisableStudy = true;
    } else if (statusCode === 404) {
      message = ui_message || this.t('study.errors.backend404');
      shouldDisableStudy = true;
    } else if (statusCode === 500) {
      message = ui_message || this.t('study.errors.backend500');
      shouldDisableStudy = true;
    } else if (
      error instanceof TypeError &&
      error.message.includes('Failed to fetch')
    ) {
      message = ui_message || this.t('study.errors.backendFetch');
    } else {
      message = ui_message || this.t('study.errors.backendUnknown');
    }

    this.showUserMessage(message, 'error');

    if (shouldDisableStudy) {
      this.studyAccessBlocked = true;
      this.studyAccessBlockedStatusCode = statusCode;
      this.studyAccessBlockedMessage = message;
      this.applyBlockedStudyUI(message);
    } else {
      this.studyAccessBlocked = false;
      this.studyAccessBlockedStatusCode = null;
      this.studyAccessBlockedMessage = null;
    }

    // Also log for debugging
    console.error('Backend error:', {
      statusCode: statusCode,
      error: error,
      message: message,
      shouldDisableStudy: shouldDisableStudy,
    });
  }

  showSubmitConfirmationModal() {
    const modal = document.getElementById('submit-confirmation-modal');
    const songsList = document.getElementById('modal-songs-list');

    // Clear and populate the songs list
    songsList.innerHTML = '';

    this.studyConfig.songs_to_rate.forEach((song) => {
      const li = document.createElement('li');
      const isSynced = this.songSyncStatus[song.display_name] === 'synced';
      li.className = isSynced ? 'synced' : 'unsaved';
      li.textContent = song.display_name;
      songsList.appendChild(li);
    });

    // Show modal with fade-in
    modal.classList.add('show');
    document.body.style.overflow = 'hidden'; // Prevent scrolling
  }

  hideSubmitConfirmationModal() {
    const modal = document.getElementById('submit-confirmation-modal');
    modal.classList.remove('show');
    document.body.style.overflow = ''; // Restore scrolling

    // Return focus to submit button
    const submitBtn = document.getElementById('submit-study');
    if (submitBtn) {
      submitBtn.focus();
    }
  }
}
