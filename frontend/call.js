const API_BASE = "http://localhost:8000"; // 실제 서버 주소

// --- GLOBAL STATE ---
let currentState = "IDLE"; // IDLE, INCOMING, IN_CALL
let sessionId = null;
let didRingOnce = false;
let callStartTime = 0;
let callTimerInterval = null;

// 미리 로드된 첫 번째 턴 데이터
let firstAudioData = null; 

// 오디오 객체
const globalAudio = new Audio();
let isAudioUnlocked = false;

// 녹음 관련
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

// --- UTILS ---
function log(msg) {
  // 화면 출력 로직 삭제, 콘솔에만 표시
  console.log(`[Call] ${msg}`);
}

// --- INITIALIZATION ---
function init() {
  updateClock();
  setInterval(updateClock, 1000);
  setupEventListeners();
  
  // 페이지 로드 즉시 통화 준비 시작
  prepareCall();
}

function setupEventListeners() {
  document.getElementById("btn-accept").addEventListener("click", acceptCall);
  document.getElementById("btn-decline").addEventListener("click", declineCall);
  micBtn.addEventListener("click", toggleRecording);
  document.getElementById("btn-hangup").addEventListener("click", hangupCall);
  
  globalAudio.addEventListener("ended", onAudioEnded);
  globalAudio.addEventListener("error", (e) => log("오디오 에러: " + e.message));
}

// --- PRE-FETCHING ---
async function prepareCall() {
    if (didRingOnce) return;

    try {
        log("통화 준비 중... (세션 생성 & 첫 멘트 생성)");
        
        const formData = new FormData();
        formData.append("device_info", "web-client");
        const res1 = await fetch(`${API_BASE}/session/start`, { method: "POST", body: formData });
        const data1 = await res1.json();
        sessionId = data1.session_id;
        
        const turnData = new FormData();
        turnData.append("session_id", sessionId);
        turnData.append("start_ms", 0);
        turnData.append("end_ms", 0);
        
        const res2 = await fetch(`${API_BASE}/turn/assistant`, { method: "POST", body: turnData });
        const data2 = await res2.json();
        
        firstAudioData = {
            url: data2.audio_url,
            meta: data2.meta_json
        };
        
        log("준비 완료! 전화 수신 화면 전환");
        triggerIncomingCall();
        
    } catch (e) {
        log("통화 준비 실패: " + e);
    }
}

function unlockAudio() {
    if (isAudioUnlocked) return;
    globalAudio.src = 'data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEAQB8AAEAfAAABAAgAAABmYWN0BAAAAAAAAABkYXRhAAAAAA==';
    globalAudio.play().then(() => {
        isAudioUnlocked = true;
        log("오디오 권한 획득");
    }).catch(e => {
        log("오디오 권한 획득 실패: " + e);
    });
}

function switchScreen(screenName) {
  [screenIdle, screenIncoming, screenInCall].forEach(el => el.classList.remove("is-active"));
  
  if (screenName === "IDLE") screenIdle.classList.add("is-active");
  if (screenName === "INCOMING") screenIncoming.classList.add("is-active");
  if (screenName === "IN_CALL") screenInCall.classList.add("is-active");
  
  currentState = screenName;
}

function updateClock() {
  const now = new Date();
  const hours = String(now.getHours()).padStart(2, '0');
  const minutes = String(now.getMinutes()).padStart(2, '0');
  clockEl.textContent = `${hours}:${minutes}`;
  const options = { month: 'long', day: 'numeric', weekday: 'long' };
  dateEl.textContent = now.toLocaleDateString('ko-KR', options);
}

function triggerIncomingCall() {
  if (currentState !== "IDLE") return;
  didRingOnce = true;
  switchScreen("INCOMING");
}

function declineCall() {
  switchScreen("IDLE");
}

async function acceptCall() {
  unlockAudio(); // 클릭 시점 권한 획득

  try {
    if (!sessionId) throw new Error("세션 미준비");

    switchScreen("IN_CALL");
    startCallTimer();
    
    await navigator.mediaDevices.getUserMedia({ audio: true });
    
    if (firstAudioData && firstAudioData.url) {
        playAssistantTurn(firstAudioData.url, firstAudioData.meta);
        firstAudioData = null;
    } else {
        requestAssistantTurn();
    }
    
  } catch (err) {
    log("통화 연결 에러: " + err);
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
    try {
      await fetch(`${API_BASE}/session/${sessionId}/finalize`, { method: "POST" });
    } catch(e) {}
  }
  endSessionUI();
}

function endSessionUI() {
  stopCallTimer();
  globalAudio.pause();
  globalAudio.currentTime = 0;
  sessionId = null;
  switchScreen("IDLE");
  statusText.textContent = "대기 중...";
}

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
    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];
    
    mediaRecorder.ondataavailable = (event) => {
      audioChunks.push(event.data);
    };
    
    mediaRecorder.start();
    isRecording = true;
    
    micBtn.classList.add("recording");
    micLabel.textContent = "전송하기";
    micBtn.querySelector("svg").style.fill = "white";
    
    statusText.textContent = "듣고 있어요...";
    aiWave.className = "wave-box listening";
    
  } catch (err) {
    log("마이크 에러: " + err);
    alert("마이크 접근 불가");
  }
}

function stopRecordingAndSend() {
  if (!mediaRecorder) return;
  
  mediaRecorder.onstop = async () => {
    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
    await uploadUserTurn(audioBlob);
  };
  
  mediaRecorder.stop();
  isRecording = false;
  
  micBtn.classList.remove("recording");
  micLabel.textContent = "말하기";
  
  statusText.textContent = "생각하는 중...";
  aiWave.className = "wave-box idle";
}

async function uploadUserTurn(blob) {
  if (!sessionId) return;
  
  const formData = new FormData();
  formData.append("session_id", sessionId);
  formData.append("start_ms", 0);
  formData.append("end_ms", 1000);
  formData.append("audio", blob, "voice.webm"); 
  
  try {
    await fetch(`${API_BASE}/turn/user`, {
      method: "POST",
      body: formData
    });
    
    requestAssistantTurn();
    
  } catch (err) {
    log("업로드 실패: " + err);
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
    log("AI 응답 에러: " + err);
  }
}

let currentMeta = null;

function playAssistantTurn(url, meta) {
  statusText.textContent = "말하는 중...";
  aiWave.className = "wave-box speaking";
  currentMeta = meta;
  
  if (!url) {
     requestAssistantTurn();
     return;
  }
  
  log("재생 시작: " + url);
  globalAudio.src = API_BASE + url;
  
  globalAudio.play().catch(e => {
      log("재생 실패(브라우저 차단): " + e);
      statusText.textContent = "🔊 눌러서 듣기";
      statusText.style.cursor = "pointer";
      statusText.onclick = () => {
          globalAudio.play();
          statusText.textContent = "말하는 중...";
          statusText.style.cursor = "default";
          statusText.onclick = null;
      };
  });
}

function onAudioEnded() {
    log("재생 완료");
    aiWave.className = "wave-box idle";
    statusText.textContent = "말씀해 주세요.";
    
    if (currentMeta && currentMeta.end_call) {
      statusText.textContent = "통화가 종료됩니다.";
      setTimeout(async () => {
        await hangupCall();
      }, 1500);
    }
}

// Start
init();