
import { AudioRatingWidget } from './audio_rating.js';

// DEFAULT CONFIG - Updated to match backend format
const INTERNAL_FALLBACK_STUDY_CONFIG = {
      "name": "Default Study",
      "name_short": "default",
      "description": "Default study for music aesthetics research",
      "songs_to_rate": [
        { "media_url": "audo_files/default/demo.wav", "display_name": "Demo Song", "description": "This is a demo song for testing the audio rating widget. Please listen to the entire clip and provide your ratings based on your experience." },
        { "media_url": "audo_files/default/demo2.wav", "display_name": "Demo Song 2", "description": "This is a second demo song for testing the audio rating widget. Please listen to the entire clip and provide your ratings based on your experience." }
      ],
      rating_dimensions: [
        { dimension_title: "valence", num_values: 8, minimal_value: 0, default_value: 4, description: "The valence of the song section" },
        { dimension_title: "arousal", num_values: 5, minimal_value: -2, default_value: 0, description: "The arousal level of the song section" },
        { dimension_title: "enjoyment", num_values: 10, minimal_value: 0, default_value: 5, description: "The enjoyment level of the song section" },
        { dimension_title: "is_cool", num_values: 2, minimal_value: 0, default_value: 0, description: "Whether the song section is cool or not" }
      ],
      study_participant_ids: [],
      allow_unlisted_participants: true,
      data_collection_start: "2024-01-01T00:00:00Z",
      data_collection_end: "2026-12-31T23:59:59Z"

};



export class StudyCoordinator {
  constructor() {
    this.studyConfig = INTERNAL_FALLBACK_STUDY_CONFIG;
    this.currentSongIndex = 0;
    this.uid = this.getOrCreateUID();
    this.studyName = this.getStudyName();
    this.widget = null;
    this.isLoading = false;
    this.backendAvailable = false;
    this.backendChecked = false;

    // Track which songs are synced with server
    this.songSyncStatus = {}; // 'unsaved', 'synced', or 'modified'

    this.localStorageKey = `audio_rating_study_${this.studyName}_${this.uid}`;
    this.localRatings = this.loadLocalRatings();

    this.init();
  }

  async loadLocalStudyConfig() {
    const study_config_file = './settings/studies_config.json'
    try {
      // Try to load from JSON file
      const response = await fetch(study_config_file);
      if (response.ok) {
        const config = await response.json();
        console.log('Loaded study config from local JSON file "', study_config_file, '".');

        // The file contains an array of study configs, find the one matching studyName
        // Extract the specific study config based on study_name from URL
        const urlParams = new URLSearchParams(window.location.search);
        const studyName = urlParams.get('study_name');
        this.studyConfig = config.studies.find(c => c.name_short === studyName) || config.studies[0]; // Default to first if not found
        return this.studyConfig;
      }
    } catch (error) {
      console.warn('Could not load local study config from JSON file "', study_config_file, '", using internal fallback:', error);
    }

    // Fallback to embedded config FALLBACK_CONFIG
    return FALLBACK_CONFIG;
  }


  destroy() {
    if (this.widget) {
      this.widget.destroy();
      this.widget = null;
    }
  }

  getDefaultValueForDimension(dimensionName) {
  const dim = this.studyConfig.rating_dimensions.find(
    d => d.dimension_title === dimensionName
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
      const newUrl = `${window.location.pathname}?uid=${uid}&study_name=${this.getStudyName()}`;
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
      missingDimensions: this.studyConfig.rating_dimensions.map(dim => dim.dimension_title)  // FIX THIS LINE
    };
  }

  const requiredDimensions = this.studyConfig.rating_dimensions.map(dim => dim.dimension_title); // AND THIS LINE
  const missingDimensions = [];

  requiredDimensions.forEach(dimName => { // Change from dim to dimName
    if (!ratingData[dimName] || !Array.isArray(ratingData[dimName]) || ratingData[dimName].length === 0) {
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

  if(!isComplete) {
    console.log('Incomplete rating data, missing dimensions:', missingDimensions);
  }

  return {
    isComplete: isComplete,
    missingDimensions: missingDimensions
  };
}



  updateAllUI() {
    this.updateSubmitButtonState();
    this.updateSongNavigationUI();
    this.updateSubmitStudyButton();
  }

  // In study_coordinator.js, update the updateSubmitButtonState method:

  updateSubmitButtonState() {
    const submitBtn = document.getElementById('submit-rating');
    if (!submitBtn) return;

    if (!this.backendAvailable) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Server Unavailable';
        return;
    }

    if (!this.widget) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Loading...';
        return;
    }

    const ratingData = this.widget.getData();
    const result = this.checkRatingDataComplete(ratingData);

    // First check if the song is completely rated
    if (!result.isComplete) {
        submitBtn.disabled = true;
        if (result.missingDimensions.length > 0) {
        submitBtn.textContent = `Rate: ${result.missingDimensions.join(', ')}`;
        } else {
        submitBtn.textContent = 'Complete all ratings to save';
        }
        return;
    }

    // Only if song is complete, check sync status
    if (this.songSyncStatus[this.currentSongIndex] === 'synced') {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Already Saved to Server';
    } else {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Save to Server';
    }
  }

  getSongStatus(songIndex) {
    const isComplete = this.isSongCompletelyRated(songIndex);

    if (!isComplete) {
      return {
        status: 'incomplete',
        icon: '○',
        color: '#ef4444',
        label: 'Incomplete ratings'
      };
    } else if (this.songSyncStatus[songIndex] === 'synced') {
      return {
        status: 'saved',
        icon: '✓',
        color: '#10b981',
        label: 'Saved to server'
      };
    } else {
      return {
        status: 'ready',
        icon: '!',
        color: '#facc15',
        label: 'Fully rated and ready to submit'
      };
    }
  }

  updateSongNavigationUI() {
    const songListDiv = document.getElementById('song-list');
    songListDiv.innerHTML = '';

    const currentSongDescription = document.getElementById('current-song-description');
    if (this.currentSongIndex !== undefined && this.currentSongIndex < this.studyConfig.songs_to_rate.length) {
      currentSongDescription.textContent = this.studyConfig.songs_to_rate[this.currentSongIndex].description || "No song description available.";
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
    this.studyConfig = await this.loadLocalStudyConfig();

    await this.checkBackendAvailability();

    if (this.backendAvailable) {
      const configLoaded = await this.loadStudyConfigFromBackend();
      if (!configLoaded) {
        console.warn("Failed to load study config from backend, using local config.");
      } else {
        console.log("Successfully loaded study config from backend. Replaced local default config with backend config.");
        // No need to set this.studyConfig here since loadStudyConfigFromBackend already sets it.
      }
    } else {
      this.showOfflineNotice();
      console.warn("Backend not available. Using local fallback config.");
    }

    document.getElementById('song-count').textContent = this.studyConfig.songs_to_rate.length; // in introduction phase
    document.getElementById('song-count-thanks').textContent = this.studyConfig.songs_to_rate.length; // in thanks phase
    document.getElementById('rating-dimensions-count').textContent = this.studyConfig.rating_dimensions.length; // in introduction phase
    document.getElementById('rating-dimensions-count-thanks').textContent = this.studyConfig.rating_dimensions.length; // in thanks phase

    // Fill song-list-intro and rating-dimensions-list-intro in introduction phase
    const songListIntro = document.getElementById('song-list-intro');
    this.studyConfig.songs_to_rate.forEach(song => {
      const li = document.createElement('li');
      li.textContent = `${song.display_name}: ${song.description || 'No description available.'}`;
      songListIntro.appendChild(li);
    });

    const ratingDimensionsListIntro = document.getElementById('rating-dimensions-list-intro');
    this.studyConfig.rating_dimensions.forEach(dim => {
      const li = document.createElement('li');
      li.textContent = `${dim.dimension_title}: ${dim.description || 'No description available.'}`;
      ratingDimensionsListIntro.appendChild(li);
    });

    // Fill study-name-title and study-name-welcome
    document.getElementById('study-name-title').textContent = this.studyConfig.name; // title in instructions phase
    document.getElementById('study-name-thanks').textContent = this.studyConfig.name;  // thanks phase
    // This is the name and the description of the study that participants see in the welcome message. It can be more friendly and descriptive than the title.
    document.getElementById('study-name-welcome').textContent = this.studyConfig.name + (this.studyConfig.description ? ` - ${this.studyConfig.description}` : '');

    // Update the page title from "Audio Rating Study" to the specific study name for better user experience
    document.title = `Audio Rating Study: ${this.studyConfig.name}`;

    document.getElementById('total-songs').textContent = this.studyConfig.songs_to_rate.length;

    this.updateSongNavigationUI();

    document.getElementById('begin-study').addEventListener('click', () => this.startRating());
    document.getElementById('submit-rating').addEventListener('click', () => this.submitRating());
    document.getElementById('download-data').addEventListener('click', () => this.downloadAllRatings());

    // Add event listener for the submit study button
    document.getElementById('submit-study').addEventListener('click', () => {
    if (this.areAllSongsSavedToServer()) {
      this.completeStudy();
    }
  });

    this.updateBackendStatus();
  }

  async checkBackendAvailability() {
  try {
    const response = await fetch(`${AR_SETTINGS.API_BASE_URL}`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' }
    });

    this.backendAvailable = response.ok;
    this.backendChecked = true;

    if (!response.ok) {
      this.showBackendError(new Error(`Backend returned ${response.status}`), response.status, 'Backend is not available, unexpected status code.');
    }
  } catch (error) {
    this.backendAvailable = false;
    this.backendChecked = true;
    this.showBackendError(error, null, "Backend is not available, request failed.");
  }
}

  async loadStudyConfigFromBackend() {
    try {
      const response = await fetch(
        `${AR_SETTINGS.API_BASE_URL}/participants/${this.uid}/studies/${this.studyName}/config`
      );

      if (response.ok) {
        const studyConfig = await response.json();
        this.studyConfig = studyConfig;

        for (let i = 0; i < this.studyConfig.songs_to_rate.length; i++) {
          try {
            const ratingsResponse = await fetch(
              `${AR_SETTINGS.API_BASE_URL}/participants/${this.uid}/studies/${this.studyName}/songs/${i}/ratings`
            );

            if (ratingsResponse.ok) {
              const data = await ratingsResponse.json();
              const songKey = `${this.studyName}_song_${i}`;

              const backendRatings = {};
              if (data.ratings) {
                Object.keys(data.ratings).forEach(ratingName => {
                  backendRatings[ratingName] = data.ratings[ratingName].segments || [];
                });
              }

              this.localRatings[songKey] = {
                data: backendRatings,
                source: 'backend',
                timestamp: new Date().toISOString()
              };

              // Mark as synced
              this.songSyncStatus[i] = 'synced';
            }
          } catch (error) {
            console.log(`No backend ratings for song ${i}`, error);
          }
        }

        this.saveLocalRatings();

        return true;
      } else {
        console.log('Failed to load config from backend with backend status code:', response.status);
        // Handle specific HTTP errors
        if (response.status === 403) {
          this.showBackendError(null, 403, "Access denied. You may not have permission to access this study and its config.");
        } else if (response.status === 404) {
          this.showBackendError(null, 404, "The requested study config was not found on the server. It may not exist or may have been removed.");
        } else {
          this.showBackendError(new Error(`HTTP ${response.status}`), response.status);
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
    await this.loadSong(this.currentSongIndex);
  }

  async loadSong(songIndex) {
    // Auto-save current song before switching
    console.log('=== LOAD SONG DEBUG ===');
    console.log('songIndex:', songIndex);
    console.log('song:', this.studyConfig.songs_to_rate[songIndex]);
    console.log('rating_dimensions:', this.studyConfig.rating_dimensions);
    console.log('rating_dimensions length:', this.studyConfig.rating_dimensions.length);


    if (this.widget) {
      await this.autoSaveCurrentSong();

      // If current song was synced, check if data changed
      if (this.songSyncStatus[this.currentSongIndex] === 'synced') {
        const currentData = this.widget.getData();
        const songKey = `${this.studyName}_song_${this.currentSongIndex}`;
        const savedData = this.localRatings[songKey];

        if (savedData && JSON.stringify(currentData) !== JSON.stringify(savedData.data)) {
          this.songSyncStatus[this.currentSongIndex] = 'modified';
          this.updateAllUI();
        }
      }

      this.widget.destroy();
      this.widget = null;
    }

    this.currentSongIndex = songIndex;
    const song = this.studyConfig.songs_to_rate[songIndex];

    document.getElementById('current-song-number').textContent = songIndex + 1;
    document.getElementById('song-status').textContent = `Currently rating: ${song.display_name}`;

    this.updateSongNavigationUI();
    this.clearStatusMessages();
    this.setLoading(true, true);

    try {
      const widgetContainer = document.getElementById('rating-widget-container');
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
        title: song.display_name
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
        this.updateAllUI();
      });



      this.updateAllUI();

      setTimeout(() => {
      this.updateSubmitButtonState();
    }, 10);

    } catch (error) {
      console.error('Error loading song:', error);
      this.showStatusMessage(`Error loading song "${song.display_name}" from file "${song.media_url}". Please try again.`, 'error');
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
      source: 'local'
    };

    try {
      this.saveLocalRatings();
    } catch (error) {
      console.error('Auto-save failed:', error);
    }
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
      localStorage.setItem(this.localStorageKey, JSON.stringify(this.localRatings));
      return true;
    } catch (error) {
      console.error('Error saving local ratings:', error);
      return false;
    }
  }

  async submitRating() {
    if (this.isLoading || !this.widget) return;

    const ratingData = this.widget.getData();
    if (Object.keys(ratingData).length === 0) {
      this.showStatusMessage('No ratings to save. Please rate the song first.', 'error');
      return;
    }

    const result = this.checkRatingDataComplete(ratingData);
    if (!result.isComplete) {
      this.showStatusMessage('Please complete all ratings before submitting.', 'error');
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
      source: 'local'
    };

    this.saveLocalRatings();
    this.updateAllUI();
    this.showStatusMessage('Rating saved locally', 'success');

    if (this.backendAvailable) {
      try {
        const backendUrl = `${AR_SETTINGS.API_BASE_URL}/participants/${this.uid}/studies/${this.studyName}/songs/${this.currentSongIndex}/ratings`;

        const response = await fetch(backendUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            timestamp: submissionTimestamp,
            ratings: ratingData
          })
        });

        if (response.ok) {
          // Update sync status
          this.songSyncStatus[this.currentSongIndex] = 'synced';

          // Update source to backend
          this.localRatings[songKey].source = 'backend';
          this.saveLocalRatings();

          this.updateAllUI();
          this.showStatusMessage('Ratings saved to server!', 'success');
        } else {
          this.showStatusMessage('Saved locally, but server submission failed.', 'warning');
        }
      } catch (error) {
        this.showStatusMessage('Saved locally. Backend temporarily unavailable.', 'warning');
      }
    }

    this.setLoading(false, false);
  }

  updateBackendStatus() {
  const statusEl = document.getElementById('backend-status');
  const storageEl = document.getElementById('storage-status');

  if (!this.backendChecked) {
    statusEl.className = 'backend-status connecting';
    statusEl.textContent = 'Checking backend...';
    if (storageEl) storageEl.textContent = 'Checking connection...';
    return;
  }

  if (this.backendAvailable) {
    statusEl.className = 'backend-status online';
    statusEl.textContent = '✓ Backend connected';
    if (storageEl) storageEl.textContent = 'Ratings will be saved to server';
  } else {
    statusEl.className = 'backend-status offline';
    statusEl.textContent = '⚠ Backend offline';
    if (storageEl) storageEl.textContent = 'Ratings saved locally only';
  }
}

  showOfflineNotice() {
    document.getElementById('backend-notice').style.display = 'block';

    const submitBtn = document.getElementById('submit-rating');
    if (submitBtn) {
      submitBtn.textContent = 'Save Locally';
    }
  }

  showStatusMessage(message, type = 'info') {
  // Use the new user message system
  this.showUserMessage(message, type, type === 'success' || type === 'warning' ? 5000 : 0);
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
      submitBtn.textContent = loading ? 'Saving...' :
        (this.backendAvailable ? 'Save to Server' : 'Save Locally');
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
    submitStudyBtn.textContent = 'Submit Study';
    statusEl.textContent = 'All songs saved! Ready to submit study.';
    statusEl.className = 'study-complete-message';
  } else {
    submitStudyBtn.disabled = true;
    submitStudyBtn.textContent = 'Submit Study';

    // Count how many songs are saved
    let savedCount = 0;
    let completeCount = 0;

    for (let i = 0; i < this.studyConfig.songs_to_rate.length; i++) {
      if (this.isSongCompletelyRated(i)) completeCount++;
      if (this.songSyncStatus[i] === 'synced') savedCount++;
    }

    statusEl.textContent = `${savedCount} of ${this.studyConfig.songs_to_rate.length} songs saved to server`;
    statusEl.className = 'study-incomplete-message';
  }
}


  completeStudy() {
    const hasLocalData = Object.keys(this.localRatings).length > 0;

    if (!this.backendAvailable && hasLocalData) {
      document.getElementById('completion-message').innerHTML = `
        You have completed all songs in this study.<br>
        <strong>Important:</strong> Your ratings are saved locally only.
      `;
      document.getElementById('download-section').style.display = 'block';
    }

    this.showPhase('completion-phase');
  }

  downloadAllRatings() {
    const dataStr = JSON.stringify(this.localRatings, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);

    const link = document.createElement('a');
    link.href = url;
    link.download = `audio_ratings_${this.studyName}_${this.uid}_${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    setTimeout(() => URL.revokeObjectURL(url), 100);
  }

  showPhase(phaseId) {
    document.querySelectorAll('.study-phase').forEach(phase => {
      phase.classList.remove('active');
    });

    document.getElementById(phaseId).classList.add('active');
  }


  // Add these methods to the StudyCoordinator class (put them after the constructor)

showUserMessage(message, type = 'info', duration = 5000) {
  // Remove existing messages of same type
  this.clearUserMessages(type);

  const messageDiv = document.createElement('div');
  messageDiv.className = `user-message ${type}-message`;
  messageDiv.innerHTML = `
    <div class="message-content">
      ${type === 'error' ? '⚠️ ' : type === 'success' ? '✓ ' : type === 'warning' ? '⚠️ ' : ''}
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

disableBeginStudyButton(reason = 'Study cannot be started') {
  const beginBtn = document.getElementById('begin-study');
  if (!beginBtn) return;

  beginBtn.disabled = true;
  beginBtn.textContent = reason;
  beginBtn.style.opacity = '0.6';
  beginBtn.style.cursor = 'not-allowed';

  // Store the original state so we can restore it if needed
  if (!beginBtn.dataset.originalText) {
    beginBtn.dataset.originalText = 'Begin Study';
  }
}

clearUserMessages(type = null) {
  const container = document.getElementById('user-messages');
  if (!container) return;

  if (type) {
    // Remove only messages of specific type
    const messages = container.querySelectorAll(`.${type}-message`);
    messages.forEach(msg => {
      if (msg.parentNode) msg.remove();
    });
  } else {
    // Remove all messages
    container.innerHTML = '';
  }
}

// Helper method to show backend errors
showBackendError(error, statusCode = null, ui_message = null) {
  let message;
  let shouldDisableStudy = false;
  let disableReason = 'Study cannot be started';

  if (statusCode === 403) {
    message = ui_message || 'Access denied. You may not have permission to acces this information.';
    shouldDisableStudy = true;
  } else if (statusCode === 404) {
    message = ui_message || 'Element not found. Could not find the requested resource on the server.';
    shouldDisableStudy = true;
  } else if (statusCode === 500) {
    message = ui_message || "Backend application error. The server encountered an error while processing your request.";
    shouldDisableStudy = true;
  } else if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
    message = ui_message || 'Backend error or backend not available. You can only save ratings locally for debug purposes, but they will not be saved to the server.';
  } else {
    message = ui_message || 'Unspecified backend error. You can only save ratings locally for debug purposes, but they will not be saved to the server.';
  }

  this.showUserMessage(message, 'error');

  if (shouldDisableStudy) {
    this.disableBeginStudyButton(disableReason);
  }

  // Also log for debugging
  console.error('Backend error:', {
    statusCode: statusCode,
    error: error,
    message: message,
    shouldDisableStudy: shouldDisableStudy
  });
}
}