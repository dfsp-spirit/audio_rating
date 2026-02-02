## audio_rating ChangeLog


Current WIP
-----------

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
