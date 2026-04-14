## audio_rating ChangeLog


WIP
-------
* NEW: add admin endpoint to create studies at runtime
* NEW: add buttons in admin interface to change start/end dates of existing studies

Version 0.7.2 -- Bug fixes
---------------------------
* NEW: extend admin interface with tabs on songs, rating dims
* FIX: Admin dashboard Jinja2 rendering - bypass Starlette TemplateResponse cache bug for wheel installations. Fixes unhashable type: 'dict' bug when trying to access admin interface.
* FIX: tooling: fix extra sourcing of local .env file in create DB script
* NEW: development only: add smoketests that try running from wheel file, as there is a jinja2 template chaching bug that manifests only when run from wheel and will be missed by unit tests


Version 0.7.1 -- UX polish
---------------------------
* NEW: better error messages on study not found, no access for user
* NEW: show proper error page instead of study info when no such study available
* NEW: Keep audio scrollbar visible all the time if zoomed in
* NEW: support deleting segment separators on long press, needed for mobile
* NEW: make x axis ticks dynamic based on zoom level
* NEW: switch to move up/down cursor on hovering rating horizontal line
* NEW: switch to resize cursor on hovering segment border, adapt colors slightly
* NEW: allow full keyboard control


Version 0.7.0 -- i18n and major UI/UX improvements
----------------------------------------------------
* NEW: Internationalization (i18n) Support: Added multi-language support with translations for ES, FR, SV; study-specific text can now be defined per language in the configuration file
* NEW: Improved Audio & Rating UI: Added backspace key to reset audio playback, improved Y-axis labeling to prevent overlap, moved rating display to the right side of segments, and optimized screen space usage for large monitors
* NEW: Study Submission & Navigation: Added confirmation modal for study submission, improved button labels to clarify the difference between the two save buttons, and moved the submit button lower on the page
* NEW: Accessibility & Keyboard Support: Enhanced keyboard navigation and accessibility across the application
* NEW: Admin & Configuration Features: Added runtime study config export to admin dashboard, new admin endpoint for config export, and support for minimal_value in studies_config file
* NEW: Testing Infrastructure: Added comprehensive end-to-end (E2E) tests for rating flows, admin interface, and API endpoints; added unit and integration test badges


Version 0.6.4 -- QOL and small fixes
--------------------------------------
* NEW: support deleting ratings of a participant for admins: new backend endpoint, new admin web interface button
* NEW: only show data download button in admin interface if ratings are available
* FIX: fix check for song audio files in frontend to prevent false positive alarms about missing files
* FIX: properly save status of songs (synces/not synced) from backend response, make more details on ratings available in backend response for that. fixes #22
* NEW: dev script QOL improvements, local minimal scripts now automatically copy proper settings files


Version 0.6.3 -- Bugfix release
--------------------------------
* FIX: remove default value for command line arg --studies-config-json-file, preventing backend startup
* CHG: remove 1 second ticks in timeline plugin of frontend


Version 0.6.2 -- Various fixes, check for audio files
------------------------------------------------------
* NEW: add function to check for missing audio files in frontend dir
* FIX: fix more links in admin interface
* NEW: various improvements to study intro and thatnks pages
* NEW: various improvements to admin interface
* DEV: make dev script for local nginx copy cfg files automatically


Version 0.6.1 -- Bugfix release for admin panel
------------------------------------------------
* FIX: Use url_for in admin_base template navigation to make navigation work with a fastapi rootpath other than /


Version 0.6.0 -- Better dimensions handling and UX
--------------------------------------------------
* BRK: move settings files, including ar_settings.js, to settings/ sub dir
* CHG: use local wavesurfer instead of remote, see #30
* NEW: show description of rating dimension in UI
* NEW: display proper error messages in UI ob backend errors like 404, 403, etc
* NEW: use default studies_config.json from file in frontend to mirror backend setup
* CHG: move audio files to new audio_files/ sub dir
* NEW: add AR_FRONTEND_URL setting and use it to construct study invitation links in backend
* NEW: load dimensions from server and update them when needed
* NEW: Support deleting data for one specific study via backend command line arguments


Version 0.5.2 -- Support fastapi rootpath
------------------------------------------
* report proper version on startup in log message
* support setting FastAPI rootpath for app based on new env var / .env config file setting AR_ROOTPATH


Version 0.5.1 -- Version bump only
----------------------------------
Bump version in __init__.py to 5.1.0


Version 0.5.0 -- Admin endpoint improvements, Descriptions of Songs and RatingDimensions
----------------------------------------------------------------------------------------
* Encode study and uid in URL in frontend
* Add admin endpoints to assign / remove participant from study
* Support adding a description to Song and RatingDimension in cfg/database


Version 0.4.0 -- Backend operational, study interface ready
-------------------------------------------------------------
* Added backend and database with declarative multi-study config, admin interface, etc
* Created study.html with a StudyController class in frontend that manages a study



Version 0.3.0 -- Cleanups, add optional volume slider
------------------------------------------------------
* Constructor of widget class now allows customizations
* Add a volume slider (can be turned off via constructor)


Version 0.2.0 -- Refactored to class
-------------------------------------
* Refactored to a class
* Split code into .html, .js and .css files
* Now supports mounting the rating widget easily into an existing page
* Several widgets per page are possible


Version 0.1.0 -- Initial prototype
-----------------------------------
* Support for multi-dimensional rating of audio files
* Currently all code in a single HTML file
