const connectBtn = document.getElementById('connectBtn');
const disconnectBtn = document.getElementById('disconnectBtn');
const statusDiv = document.getElementById('status');
const agentAudio = document.getElementById('agentAudio');
const logBox = document.getElementById('logBox');

let pc = null;
let eventsDc = null;
let micStream = null;
let vadAnimationId = null;

function log(msg) {
    const p = document.createElement('p');
    p.style.margin = '2px 0';
    p.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
    logBox.appendChild(p);
    logBox.scrollTop = logBox.scrollHeight;
    console.log(msg);
}

function formatGatewayEvent(ev) {
    switch (ev.type) {
        case 'speech_started':
            return 'You started speaking';
        case 'speech_ended':
            return 'You stopped speaking';
        case 'barge_in.detected':
            return `Barge-in (${ev.reason || 'unknown'}) — agent stopped`;
        case 'speak.cancel':
            return 'Agent playback cancelled';
        case 'transcript.final':
            return `Heard: "${ev.text}"`;
        default:
            return ev.type;
    }
}

function startClientVad(stream) {
    const audioContext = new AudioContext();
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 512;
    audioContext.createMediaStreamSource(stream).connect(analyser);

    const timeData = new Uint8Array(analyser.fftSize);
    let speechFrames = 0;
    let lastHintSent = 0;

    const tick = () => {
        if (!pc) {
            return;
        }

        analyser.getByteTimeDomainData(timeData);
        let sumSquares = 0;
        for (let i = 0; i < timeData.length; i++) {
            const sample = (timeData[i] - 128) / 128;
            sumSquares += sample * sample;
        }
        const rms = Math.sqrt(sumSquares / timeData.length);

        if (rms > 0.025) {
            speechFrames += 1;
            const now = Date.now();
            if (
                speechFrames >= 3 &&
                eventsDc &&
                eventsDc.readyState === 'open' &&
                now - lastHintSent > 250
            ) {
                eventsDc.send(JSON.stringify({ type: 'client_speech_start' }));
                lastHintSent = now;
                speechFrames = 0;
            }
        } else {
            speechFrames = 0;
        }

        vadAnimationId = requestAnimationFrame(tick);
    };

    tick();
}

function stopClientVad() {
    if (vadAnimationId) {
        cancelAnimationFrame(vadAnimationId);
        vadAnimationId = null;
    }
}

async function startConnection() {
    log('Starting connection...');
    statusDiv.textContent = 'Status: Connecting...';
    connectBtn.disabled = true;

    try {
        log('Requesting microphone permissions...');
        micStream = await navigator.mediaDevices.getUserMedia({
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true,
            },
        });
        log('Microphone access granted.');

        pc = new RTCPeerConnection();

        eventsDc = pc.createDataChannel('events');
        eventsDc.onopen = () => log('Events channel open (Card 6)');
        eventsDc.onmessage = (evt) => {
            try {
                const payload = JSON.parse(evt.data);
                log(`← ${formatGatewayEvent(payload)}`);
            } catch {
                log(`← ${evt.data}`);
            }
        };

        micStream.getTracks().forEach((track) => {
            log(`Adding local track: ${track.kind}`);
            pc.addTrack(track, micStream);
        });

        startClientVad(micStream);

        pc.addEventListener('track', (evt) => {
            log('Received remote audio track from agent.');
            if (evt.track.kind === 'audio') {
                agentAudio.srcObject = evt.streams[0];
            }
        });

        pc.addEventListener('connectionstatechange', () => {
            log(`Connection state: ${pc.connectionState}`);
            if (pc.connectionState === 'connected') {
                statusDiv.textContent = 'Status: Connected — speak anytime; interrupt the agent by talking';
                disconnectBtn.disabled = false;
            } else if (
                pc.connectionState === 'disconnected' ||
                pc.connectionState === 'failed'
            ) {
                handleDisconnect();
            }
        });

        log('Creating SDP offer...');
        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        log('Sending offer to backend API...');
        const response = await fetch('/webrtc/offer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                sdp: pc.localDescription.sdp,
                type: pc.localDescription.type,
            }),
        });

        if (!response.ok) {
            throw new Error(`Server returned ${response.status}: ${await response.text()}`);
        }

        const answer = await response.json();
        log('Received SDP answer from backend.');
        await pc.setRemoteDescription(answer);
        log('WebRTC negotiation complete.');
    } catch (err) {
        log(`Error: ${err.message}`);
        statusDiv.textContent = 'Status: Error';
        connectBtn.disabled = false;
        disconnectBtn.disabled = true;
    }
}

function handleDisconnect() {
    log('Disconnecting...');
    stopClientVad();

    if (micStream) {
        micStream.getTracks().forEach((t) => t.stop());
        micStream = null;
    }

    if (pc) {
        pc.getSenders().forEach((sender) => {
            if (sender.track) {
                sender.track.stop();
            }
        });
        pc.close();
        pc = null;
    }

    eventsDc = null;
    agentAudio.srcObject = null;
    statusDiv.textContent = 'Status: Disconnected';
    connectBtn.disabled = false;
    disconnectBtn.disabled = true;
    log('Disconnected.');
}

connectBtn.addEventListener('click', startConnection);
disconnectBtn.addEventListener('click', handleDisconnect);
