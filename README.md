# audio_rating
Web-based tool for continuous multi-dimensional rating of audio content with interactive waveform visualization



![Vis](./audio_rating.png?raw=true "Audio rating")

## About

This is a small javascript web widget to allow users to play an audio file, visualize the waveform, and assign ratings to the sections of the audio. The user can create sections, and assign a discrete rating to each section.

The widget support several rating dimensions, so that users can rate, for example, valence, arousal, and enjoyment.

It is intended to be used in psychological research on music perception and based on the great [wavesurfer.js](https://wavesurfer.xyz/) audio visualization library for JavaScript.


## Features

* audio file format: supports all audio file formats supported by Wavesurfer, including `.wav`, .`mp3`, and many others
* audio playback: pause/continue and jump to arbitrary positions in audio file via a slider
* rating: split songs into arbitrary sections and rate each section
* rate different dimensions (e.g., valence, arousal, and enjoyment) and use different scales for them
* export rating data and download it directly as a CSV file


## Online Live Demo

You can [try audio_rating live here](https://dfsp-spirit.github.io/audio_rating/) on GitHub pages.


## Running locally

All you need is to have Python installed. Then run the `run.bash` script, which will serve the root directory of this repo (the [index.html](./index.html) file and the demo.wav file) in Python's built-in web server on port 8000 on your computer. Then connect to [http://localhost:8000](http://localhost:8000).

If you don't have Python or don't like its web server, use any other web server instead.


## Author, License and Dependencies

This was written by Tim Schäfer.

The major part of the work is done by [wavesurfer.js](https://wavesurfer.xyz/) though.

This software is licensed under the [3-clause BSD license](./LICENSE), the same license as [used by wavesurfer](https://github.com/katspaugh/wavesurfer.js/blob/main/LICENSE).




