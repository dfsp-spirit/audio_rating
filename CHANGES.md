## audio_rating ChangeLog


Current WIP
-----------


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
