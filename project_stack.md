# AI Voice Agent Project Stack

This document outlines the core models, tools, and fallback mechanisms used in the AI Voice Agent architecture.

## Primary Tools & Services

### 1. Vapi (Primary Telephony & Number Provider)
- **Purpose**: We are primarily using Vapi to acquire a phone number on a trial basis and handle the outbound calling infrastructure.
- **Role**: Vapi will act as the core telephony engine to bridge the phone network to our AI system.
- **Limitation Handling**: Trial numbers on platforms like Vapi often have geographical restrictions (e.g., they may not allow outbound calls to Pakistani numbers due to fraud prevention policies). 

### 2. Deepgram (Speech-to-Text)
- **Purpose**: Real-time, low-latency audio transcription.
- **Role**: It will listen to the user's speech over the phone and convert it into text instantly so the AI model can understand and process the user's intent. 

## Fallback Architecture

### WebRTC (Alternative Telephony Solution)
- **Purpose**: Direct browser-to-server or app-to-server audio streaming.
- **Trigger**: We will shift to WebRTC **only if** the Vapi trial number fails to successfully make outbound calls to Pakistani phone numbers.
- **Role**: Instead of relying on traditional PSTN phone numbers (which face international dialing restrictions on trials), WebRTC allows us to route voice data directly over the internet using web sockets. This guarantees we can test the voice agent's conversational flow (Deepgram + LLM + TTS) regardless of phone number region locks. 



