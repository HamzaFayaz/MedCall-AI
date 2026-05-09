const connectBtn = document.getElementById('connectBtn');
const disconnectBtn = document.getElementById('disconnectBtn');
const statusDiv = document.getElementById('status');
const agentAudio = document.getElementById('agentAudio');
const logBox = document.getElementById('logBox');

let pc = null;

function log(msg) {
    const p = document.createElement('p');
    p.style.margin = '2px 0';
    p.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
    logBox.appendChild(p);
    logBox.scrollTop = logBox.scrollHeight;
    console.log(msg);
}

async function startConnection() {
    log("Starting connection...");
    statusDiv.textContent = "Status: Connecting...";
    connectBtn.disabled = true;

    try {
        // 1. Get Microphone access
        log("Requesting microphone permissions...");
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        log("Microphone access granted.");

        // 2. Create PeerConnection
        pc = new RTCPeerConnection();

        // 3. Add tracks to PeerConnection
        stream.getTracks().forEach(track => {
            log(`Adding local track: ${track.kind}`);
            pc.addTrack(track, stream);
        });

        // 4. Listen for remote audio
        pc.addEventListener("track", (evt) => {
            log("Received remote audio track from agent.");
            if (evt.track.kind === 'audio') {
                agentAudio.srcObject = evt.streams[0];
            }
        });

        pc.addEventListener("connectionstatechange", () => {
            log(`Connection state: ${pc.connectionState}`);
            if (pc.connectionState === 'connected') {
                statusDiv.textContent = "Status: Connected";
                disconnectBtn.disabled = false;
            } else if (pc.connectionState === 'disconnected' || pc.connectionState === 'failed') {
                handleDisconnect();
            }
        });

        // 5. Create Offer
        log("Creating SDP offer...");
        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        // 6. Send Offer to Backend API
        log("Sending offer to backend API...");
        const response = await fetch('/webrtc/offer', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                sdp: pc.localDescription.sdp,
                type: pc.localDescription.type
            })
        });

        if (!response.ok) {
            throw new Error(`Server returned ${response.status}: ${await response.text()}`);
        }

        const answer = await response.json();
        log("Received SDP answer from backend.");
        
        // 7. Set Remote Description
        await pc.setRemoteDescription(answer);
        log("WebRTC Negotiation complete. Waiting for connection...");

    } catch (err) {
        log(`Error: ${err.message}`);
        statusDiv.textContent = "Status: Error";
        connectBtn.disabled = false;
        disconnectBtn.disabled = true;
    }
}

function handleDisconnect() {
    log("Disconnecting...");
    if (pc) {
        pc.getSenders().forEach(sender => {
            if (sender.track) sender.track.stop();
        });
        pc.close();
        pc = null;
    }
    
    agentAudio.srcObject = null;
    statusDiv.textContent = "Status: Disconnected";
    connectBtn.disabled = false;
    disconnectBtn.disabled = true;
    log("Disconnected.");
}

connectBtn.addEventListener('click', startConnection);
disconnectBtn.addEventListener('click', handleDisconnect);
