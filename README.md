# audio_rating
Web-based tool for continuous multi-dimensional rating of audio content with interactive waveform visualization


## About

This is a small javascript web widget to allow users to play an audio file, visualize the waveform, and assign ratings to the sections of the audio. The user can create sections, and assign a discrete rating to each section.

The widget support several rating dimensions, so that users can rate, for example, valence, arousal, and enjoyment.

It is intended to be used in psychological research on music perception and based on the great [wavesurfer.js](https://wavesurfer.xyz/) audio visualization library for JavaScript.


## Demo

You can [try audio_rating live here](https://dfsp-spirit.github.io/audio_rating/) on GitHub pages.


## Running locally

All you need is to have Python installed. Then run the `run.bash` script, which will serve the root directory of this repo (the [index.html](./index.html) file and the demo.wav file) in Python's built-in web server on port 8000 on your computer. Then connect to [http://localhost:8000](http://localhost:8000).

If you don't have Python or don't like its web server, use any other web server instead.







