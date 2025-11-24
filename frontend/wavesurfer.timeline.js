<!DOCTYPE html>
<html lang="en">
  <head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />

  <title>wavesurfer.js | audio waveform player JavaScript library</title>

  <link rel="apple-touch-icon" sizes="180x180" href="/favicons/apple-touch-icon.png" />
  <link rel="icon" type="image/png" sizes="32x32" href="/favicons/favicon-32x32.png" />
  <link rel="icon" type="image/png" sizes="16x16" href="/favicons/favicon-16x16.png" />
  <link rel="manifest" href="/site.webmanifest" />

  <link rel="stylesheet" href="/style.css" />
</head>


  <body>
    

  <header class="no-bg">
    <a class="logo">
      <img src="/logo-small.png" alt="wavesurfer.js logo" />
      <h1>wavesurfer.js</h1>
    </a>

    <div class="links">
      <a href="/examples">Examples</a>
      <a href="/docs">Docs</a>
      <a class="github" href="https://github.com/katspaugh/wavesurfer.js">GitHub</a>
    </div>
  </header>




    <div class="content">
      

      <div>
  <div class="hero">
    <div id="waveform"></div>

    <div class="carbon-index">
      <script async type="text/javascript" src="//cdn.carbonads.com/carbon.js?serve=CKYIE237&placement=wavesurfer-jsorg" id="_carbonads_js"></script>

    </div>

    <script type="module">
      import WaveSurfer from 'https://cdn.jsdelivr.net/npm/wavesurfer.js@7/dist/wavesurfer.esm.js'

      const wavesurfer = WaveSurfer.create({
        container: '#waveform',
        waveColor: '#fff',
        progressColor: '#F1EAF5',
        url: '/wavesurfer-code/examples/audio/audio.wav',
        height: 164,
      })

      wavesurfer.once('interaction', () => {
        wavesurfer.play()
      })
    </script>
  </div>

  <div class="description">
    <b>Wavesurfer.js</b> is an open-source audio visualization library for creating interactive, customizable waveforms.
  </div>

  <div class="description" style="font-size: 18px; padding-top: 30px;">
    Gold sponsor 💖 <a href="https://www.closedcaptioncreator.com" target="_blank">Closed Caption Creator</a>
  </div>

  <div class="flex">
    <div class="text">
      <h2>✨ Features</h2>
      <ul>
        <li>HTML5 Audio and Web Audio support</li>
        <li>Responsive and customizable waveforms</li>
        <li>Highly extensible with plugins</li>
        <li>TypeScript API – see the <a href="/docs" target="_blank">documentation</a></li>
      </ul>
    </div>

    <div>
      <div id="features" style="height: 128px"></div>

      <p style="text-align: center; margin: 2em 0 0; font-size: 1.3em;">
        <a href="/examples">See more examples</a>
      </p>

      <script type="module">
        import WaveSurfer from 'https://cdn.jsdelivr.net/npm/wavesurfer.js@7/dist/wavesurfer.esm.js'

        const wavesurfer = WaveSurfer.create({
          container: '#features',
          waveColor: '#4F4A85',
          progressColor: '#383351',
          barWidth: 4,
          barGap: 3,
          barRadius: 2,
          url: '/wavesurfer-code/examples/audio/mono.mp3',
        })

        wavesurfer.on('interaction', () => {
          wavesurfer.play()
        })
      </script>
    </div>
  </div>

  <div class="no-flex">
    <h2>🧑‍💻 Quick start</h2>

    <pre><code>
<h>&lt;div id="waveform"&gt;
  &lt;!-- the waveform will be rendered here --&gt;
&lt;/div&gt;</h>

<h>&lt;script type="module"&gt;</h>
<i>import</i> WaveSurfer <i>from</i> <s>'https://cdn.jsdelivr.net/npm/wavesurfer.js@7/dist/wavesurfer.esm.js'</s>

<i>const</i> wavesurfer = WaveSurfer.create({
  container: <s>'#waveform'</s>,
  waveColor: <s>'#4F4A85'</s>,
  progressColor: <s>'#383351'</s>,
  url: <s>'/audio.mp3'</s>,
})

wavesurfer.on(<s>'interaction'</s>, () => {
  wavesurfer.play()
})
<h>&lt;/script&gt;</h>
    </code></pre>
  </div>

  <div class="flex">
    <div class="text">
      <h2>🧩 Plugins</h2>
      <ul>
        <li>
          <a href="/examples/?regions.js">Regions</a><br />
          Creates clickable overlays to mark regions of audio.
        </li>

        <li>
          <a href="/examples/?hover.js">Hover</a><br />
          Shows the time position on hover.
        </li>

        <li>
          <a href="/examples/?envelope.js">Envelope</a><br />
          A graphical interface to add fade-in and -out effects and control volume.
        </li>

        <li>
          <a href="/examples/?record.js">Record</a><br />
          Records audio from the microphone and renders a waveform.
        </li>

        <li>
          <a href="/examples/?minimap.js">Minimap</a><br />
          A small waveform that serves as a scrollbar for the main waveform.
        </li>

        <li>
          <a href="/examples/?timeline.js">Timeline</a><br />
          Displays notches and time labels below the waveform.
        </li>

        <li>
          <a href="/examples/?spectrogram.js">Spectrogram</a><br />
          A visual representation of the spectrum of frequencies in audio using FFT. Created by <a href="https://github.com/akreal">@akreal</a>.
        </li>
      </ul>
    </div>

    <div>
      <div id="plugins" style="font-size: 14px"></div>

      <script type="module">
        import WaveSurfer from 'https://cdn.jsdelivr.net/npm/wavesurfer.js@7/dist/wavesurfer.esm.js'
        import Regions from 'https://cdn.jsdelivr.net/npm/wavesurfer.js@7/dist/plugins/regions.esm.js'
        import Spectrogram from 'https://cdn.jsdelivr.net/npm/wavesurfer.js@7/dist/plugins/spectrogram.esm.js'

        const regions = Regions.create()

        const wavesurfer = WaveSurfer.create({
          container: '#plugins',
          waveColor: '#4F4A85',
          progressColor: '#2C5B88',
          url: '/wavesurfer-code/examples/audio/demo.wav',
          plugins: [
            regions,
            Spectrogram.create({ labels: true }),
          ],
        })

        wavesurfer.once('ready', () => {
          const intro = regions.addRegion({ start: 0, end: 3.5, content: 'Click me', color: 'rgba(100, 0, 100, 0.5)' })
          regions.addRegion({ start: 12, content: 'Marker', color: 'rgba(100, 0, 0, 0.5)' })
          regions.addRegion({ start: 14, content: 'Second marker', color: 'rgba(0, 100, 0, 0.5)' })

          intro.element.addEventListener('click', () => {
            wavesurfer.play()
            intro.setOptions({ color: 'rgba(0, 100, 0, 0.5)' })
          })
        })
      </script>
    </div>
  </div>

  <div class="flex">
    <div class="text">
      <h2>💾 Examples</h2>
      <ul>
        <li><a href="/examples/?basic.js">Basic waveform visualization</a></li>
        <li><a href="/examples/?multitrack.js">Multi-track mixing</a></li>
        <li><a href="/examples/?regions.js">Audio annotations</a></li>
        <li><a href="/examples/?record.js">Real-time microphone recording</a></li>
        <li><a href="/examples/?webaudio.js">Web Audio equalizer</a></li>
        <li><a href="/examples/?soundcloud.js">A soundcloud-style player</a></li>
      </ul>
    </div>

    <div>
      <div id="examples"></div>

      <button style="margin: 1rem">Play</button> Volume: <label>0</label>

      <script type="module">
        import WaveSurfer from 'https://cdn.jsdelivr.net/npm/wavesurfer.js@7/dist/wavesurfer.esm.js'
        import Timeline from 'https://cdn.jsdelivr.net/npm/wavesurfer.js@7/dist/plugins/timeline.esm.js'
        import Envelope from 'https://cdn.jsdelivr.net/npm/wavesurfer.js@7/dist/plugins/envelope.esm.js'

        const envelope = Envelope.create({
          volume: 0.8,
          points: [
            { time: 11.2, volume: 0.5 },
            { time: 15.5, volume: 0.8 },
          ],
        })

        const wavesurfer = WaveSurfer.create({
          container: '#examples',
          waveColor: '#A32EB8',
          progressColor: '#8124A3',
          url: '/wavesurfer-code/examples/audio/audio.wav',
          plugins: [
            envelope,
            Timeline.create({ timeInterval: 1, primaryLabelInterval: 5 }),
          ],
        })

        wavesurfer.once('ready', () => {
          const button = document.querySelector('button')
          button.onclick = () => wavesurfer.playPause()
          wavesurfer.on('play', () => button.textContent = 'Pause')
          wavesurfer.on('pause', () => button.textContent = 'Play')

          const volumeLabel = document.querySelector('label')
          volumeLabel.textContent = envelope.getCurrentVolume().toFixed(2)
          envelope.on('volume-change', (volume) => {
            volumeLabel.textContent = volume.toFixed(2)
          })
        })
      </script>
    </div>

  </div>

  <div class="flex">
    <div class="text">
      <h2>📖 API Documentation</h2>
      <p>Discover how to use <b>wavesurfer.js</b> with our comprehensive TypeScript API documentation.</p>
      <a href="/docs">Explore the API Docs</a>
    </div>

    <div class="text">
      <h2>🙏 Contributors</h2>
      <p>We'd like to thank all our contributors for their hard work and dedication to making <b>wavesurfer.js</b> the best audio visualization library out there.</p>
      <a href="https://github.com/wavesurfer-js/wavesurfer.js/graphs/contributors">View Contributors on GitHub</a>
    </div>
  </div>
</div>

    </div>

    <footer>
  <ul>
    <li>
      © 2012&ndash;2024 <a href="https://github.com/katspaugh" target="_blank">katspaugh</a>
    </li>
    <li>
      <a href="/about">About</a>
    </li>
    <li>
      <a href="/privacy-policy">Privacy policy</a>
    </li>
    <li>
      <a href="/contact-us">Contact us</a>
    </li>
    <li>
      <a href="/example">V6 examples</a>
    </li>
    <li>
      <a href="https://github.com/katspaugh/wavesurfer.js/blob/beta/LICENSE" target="_blank">BSD-3-Clause License</a>
    </li>
  </ul>
</footer>

  </body>
</html>
