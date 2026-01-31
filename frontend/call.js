const API_BASE = "http://localhost:8000"; // 실제 서버 주소로 변경

// --- GLOBAL STATE ---
let currentState = "IDLE"; // IDLE, INCOMING, IN_CALL
let sessionId = null;
let didRingOnce = false; // 재실행 방지 플래그
let callStartTime = 0;
let callTimerInterval = null;

let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;

// UI Elements
const screenIdle = document.getElementById("idle-screen");
const screenIncoming = document.getElementById("incoming-screen");
const screenInCall = document.getElementById("in-call-screen");

const clockEl = document.getElementById("digital-clock");
const dateEl = document.getElementById("date-text");
const statusText = document.getElementById("status-text");
const aiWave = document.getElementById("ai-wave");
const micBtn = document.getElementById("btn-mic");
const micLabel = document.getElementById("mic-label");
const timerEl = document.getElementById("call-timer");

// --- INITIALIZATION ---
function init() {
  updateClock();
  setInterval(updateClock, 1000);
  
  // 1초 후 자동 수신 시도 (단 한 번만)
  setTimeout(() => {
    if (!didRingOnce) {
      triggerIncomingCall();
    }
  }, 1000);
  
  setupEventListeners();
}

function setupEventListeners() {
  // 수신 화면 버튼
  document.getElementById("btn-accept").addEventListener("click", acceptCall);
  document.getElementById("btn-decline").addEventListener("click", declineCall);
  
  // 말하기 버튼 (Toggle 방식: 누르면 시작, 다시 누르면 전송)
  micBtn.addEventListener("click", toggleRecording);
  
  // 끊기 버튼
  document.getElementById("btn-hangup").addEventListener("click", hangupCall);
}

// --- SCREEN TRANSITIONS ---
function switchScreen(screenName) {
  [screenIdle, screenIncoming, screenInCall].forEach(el => el.classList.remove("is-active"));
  
  if (screenName === "IDLE") screenIdle.classList.add("is-active");
  if (screenName === "INCOMING") screenIncoming.classList.add("is-active");
  if (screenName === "IN_CALL") screenInCall.classList.add("is-active");
  
  currentState = screenName;
}

// --- CLOCK ---
function updateClock() {
  const now = new Date();
  const hours = String(now.getHours()).padStart(2, '0');
  const minutes = String(now.getMinutes()).padStart(2, '0');
  clockEl.textContent = `${hours}:${minutes}`;
  
  const options = { month: 'long', day: 'numeric', weekday: 'long' };
  dateEl.textContent = now.toLocaleDateString('ko-KR', options);
}

// --- CALL LOGIC ---

function triggerIncomingCall() {
  if (currentState !== "IDLE") return;
  didRingOnce = true;
  switchScreen("INCOMING");
  // 벨소리가 있다면 여기서 play()
}

function declineCall() {
  // 거절 시 그냥 IDLE로 복귀 (다시 안 울림)
  switchScreen("IDLE");
}

async function acceptCall() {
  try {
    // 세션 시작 요청
    const formData = new FormData();
    formData.append("device_info", "web-client");
    
    const res = await fetch(`${API_BASE}/session/start`, {
      method: "POST",
      body: formData
    });
    const data = await res.json();
    sessionId = data.session_id;
    
    switchScreen("IN_CALL");
    startCallTimer();
    
    // 마이크 권한 미리 요청
    await navigator.mediaDevices.getUserMedia({ audio: true });
    
    // AI 먼저 인사 시키기 (옵션)
    playAssistantTurn(0, 0); 
    
  } catch (err) {
    console.error("통화 시작 실패", err);
    alert("통화 연결 실패");
    switchScreen("IDLE");
  }
}

function startCallTimer() {
  callStartTime = Date.now();
  callTimerInterval = setInterval(() => {
    const diff = Math.floor((Date.now() - callStartTime) / 1000);
    const m = String(Math.floor(diff / 60)).padStart(2, '0');
    const s = String(diff % 60).padStart(2, '0');
    timerEl.textContent = `${m}:${s}`;
  }, 1000);
}

function stopCallTimer() {
  clearInterval(callTimerInterval);
  timerEl.textContent = "00:00";
}

async function hangupCall() {
  if (sessionId) {
    // 강제 종료 시에도 finalize 호출
    try {
      await fetch(`${API_BASE}/session/${sessionId}/finalize`, { method: "POST" });
    } catch(e) {}
  }
  endSessionUI();
}

function endSessionUI() {
  stopCallTimer();
  sessionId = null;
  switchScreen("IDLE");
  statusText.textContent = "대기 중...";
}

// --- RECORDING & TURNS ---

async function toggleRecording() {
  if (!isRecording) {
    startRecording();
  } else {
    stopRecordingAndSend();
  }
}

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream); // 기본 mimeType (보통 webm)
    audioChunks = [];
    
    mediaRecorder.ondataavailable = (event) => {
      audioChunks.push(event.data);
    };
    
    mediaRecorder.start();
    isRecording = true;
    
    // UI 업데이트
    micBtn.classList.add("recording");
    micLabel.textContent = "전송하기";
    micBtn.querySelector("svg").style.fill = "white"; // 아이콘 유지
    
    statusText.textContent = "듣고 있어요...";
    aiWave.className = "wave-box listening";
    
  } catch (err) {
    console.error("Mic error", err);
    alert("마이크 접근 불가");
  }
}

function stopRecordingAndSend() {
  if (!mediaRecorder) return;
  
  mediaRecorder.onstop = async () => {
    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' }); // 브라우저 호환성 위해 webm
    await uploadUserTurn(audioBlob);
  };
  
  mediaRecorder.stop();
  isRecording = false;
  
  // UI 업데이트
  micBtn.classList.remove("recording");
  micLabel.textContent = "말하기";
  
  statusText.textContent = "생각하는 중...";
  aiWave.className = "wave-box idle";
}

async function uploadUserTurn(blob) {
  if (!sessionId) return;
  
  // 1. User Turn Upload
  const startMs = 0; // 데모용 (실제로는 timestamp 기록 필요)
  const endMs = 1000;
  
  const formData = new FormData();
  formData.append("session_id", sessionId);
  formData.append("start_ms", startMs);
  formData.append("end_ms", endMs);
  // 파일명에 확장자 .webm 명시 (백엔드가 인식하도록)
  formData.append("audio", blob, "voice.webm"); 
  
  try {
    await fetch(`${API_BASE}/turn/user`, {
      method: "POST",
      body: formData
    });
    
    // 2. Request Assistant Turn
    requestAssistantTurn();
    
  } catch (err) {
    console.error("Turn upload failed", err);
    statusText.textContent = "오류 발생";
  }
}

async function requestAssistantTurn() {
  const formData = new FormData();
  formData.append("session_id", sessionId);
  formData.append("start_ms", 0);
  formData.append("end_ms", 0);
  
  try {
    const res = await fetch(`${API_BASE}/turn/assistant`, {
      method: "POST",
      body: formData
    });
    const data = await res.json();
    
    playAssistantTurn(data.audio_url, data.meta_json);
    
  } catch (err) {
    console.error("Assistant error", err);
  }
}

function playAssistantTurn(url, meta) {
  statusText.textContent = "말하는 중...";
  aiWave.className = "wave-box speaking";
  
  if (!url) {
     // 첫 인사 등 url 없을 때
     requestAssistantTurn();
     return;
  }
  
  const audio = new Audio(API_BASE + url);
  audio.play();
  
  audio.onended = () => {
    aiWave.className = "wave-box idle";
    statusText.textContent = "말씀해 주세요.";
    
    // 종료 플래그 확인
    if (meta && meta.end_call) {
      statusText.textContent = "통화가 종료됩니다.";
      setTimeout(async () => {
        await fetch(`${API_BASE}/session/${sessionId}/finalize`, { method: "POST" });
        endSessionUI();
      }, 1500);
    }
  };
}

// Start
init();