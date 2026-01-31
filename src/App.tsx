import { useEffect, useState } from 'react'
import './App.css'

const hospitals = [
  {
    name: '서울아산병원',
    rating: 3.0,
    address: '탄방동 91-23',
    status: '영업중',
    close: '오후 6시에 영업 종료',
  },
  {
    name: '서울아산병원',
    rating: 3.0,
    address: '탄방동 91-23',
    status: '영업중',
    close: '오후 6시에 영업 종료',
  },
  {
    name: '서울아산병원',
    rating: 3.0,
    address: '탄방동 91-23',
    status: '영업중',
    close: '오후 6시에 영업 종료',
  },
  {
    name: '서울아산병원',
    rating: 3.0,
    address: '탄방동 91-23',
    status: '영업중',
    close: '오후 6시에 영업 종료',
  },
]

const calls = [
  {
    time: '2026.02.01. 01:23',
    risk: '75%',
    signals: '7개의 위험 신호',
    summary: '요약: 어제 먹은 저녁, 좋아하는 음식과 좋아하는…',
  },
  {
    time: '2026.02.01. 01:23',
    risk: '53%',
    signals: '7개의 위험 신호',
    summary: '요약: 어제 먹은 저녁, 좋아하는 음식과 좋아하는…',
  },
  {
    time: '2026.02.01. 01:23',
    risk: '75%',
    signals: '7개의 위험 신호',
    summary: '요약: 어제 먹은 저녁, 좋아하는 음식과 좋아하는…',
  },
  {
    time: '2026.02.01. 01:23',
    risk: '75%',
    signals: '7개의 위험 신호',
    summary: '요약: 어제 먹은 저녁, 좋아하는 음식과 좋아하는…',
  },
  {
    time: '2026.02.01. 01:23',
    risk: '75%',
    signals: '7개의 위험 신호',
    summary: '요약: 어제 먹은 저녁, 좋아하는 음식과 좋아하는…',
  },
]

const historySections = [
  {
    title: '2월',
    items: [
      {
        time: '2026.02.01. 01:23',
        risk: '75%',
        signals: '7개의 위험 신호',
        summary: '요약: 어제 먹은 저녁, 좋아하는 음식과 좋아하는…',
      },
    ],
  },
  {
    title: '1월',
    items: [
      {
        time: '2026.01.01. 02:01',
        risk: '75%',
        signals: '7개의 위험 신호',
        summary: '요약: 어제 먹은 저녁, 좋아하는 음식과 좋아하는…',
      },
      {
        time: '2026.02.01. 01:23',
        risk: '75%',
        signals: '7개의 위험 신호',
        summary: '요약: 어제 먹은 저녁, 좋아하는 음식과 좋아하는…',
      },
      {
        time: '2026.02.01. 01:23',
        risk: '75%',
        signals: '7개의 위험 신호',
        summary: '요약: 어제 먹은 저녁, 좋아하는 음식과 좋아하는…',
      },
      {
        time: '2026.02.01. 01:23',
        risk: '75%',
        signals: '7개의 위험 신호',
        summary: '요약: 어제 먹은 저녁, 좋아하는 음식과 좋아하는…',
      },
    ],
  },
  {
    title: '2025년 12월',
    items: [
      {
        time: '2026.01.01. 오후 3시 45분',
        risk: '75%',
        signals: '7개의 위험 신호',
        summary: '요약: 어제 먹은 저녁, 좋아하는 음식과 좋아하는…',
      },
      {
        time: '2026.02.01. 01:23',
        risk: '75%',
        signals: '7개의 위험 신호',
        summary: '요약: 어제 먹은 저녁, 좋아하는 음식과 좋아하는…',
      },
      {
        time: '2026.02.01. 01:23',
        risk: '75%',
        signals: '7개의 위험 신호',
        summary: '요약: 어제 먹은 저녁, 좋아하는 음식과 좋아하는…',
      },
      {
        time: '2026.02.01. 01:23',
        risk: '75%',
        signals: '7개의 위험 신호',
        summary: '요약: 어제 먹은 저녁, 좋아하는 음식과 좋아하는…',
      },
    ],
  },
]

const analysisGrid = [
  0, 1, 2, 1, 0, 3, 2, 2, 1, 0, 1, 2, 3, 2, 1, 0, 2, 3,
  1, 2, 3, 1, 0, 1, 2, 4, 3, 1, 0, 2, 1, 2, 3, 1, 0, 1,
  0, 2, 1, 1, 2, 3, 4, 2, 1, 1, 2, 2, 3, 4, 2, 1, 0, 1,
  1, 0, 1, 2, 3, 2, 1, 0, 1, 2, 3, 2, 1, 0, 1, 2, 3, 2,
  2, 3, 2, 1, 0, 1, 2, 3, 1, 0, 1, 2, 3, 1, 0, 2, 3, 4,
  1, 2, 3, 2, 1, 0, 1, 2, 3, 4, 2, 1, 0, 1, 2, 3, 2, 1,
  0, 1, 2, 3, 2, 1, 0, 1, 2, 3, 2, 1, 0, 2, 3, 4, 2, 1,
]

function App() {
  const [activeTab, setActiveTab] = useState<'home' | 'analysis' | 'history' | 'profile'>(
    'home',
  )
  const riskTarget = 75
  const [riskValue, setRiskValue] = useState(0)

  useEffect(() => {
    if (typeof window === 'undefined') return
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduceMotion) {
      setRiskValue(riskTarget)
      return
    }

    const duration = 1200
    let start: number | null = null
    let frameId = 0

    const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3)

    const step = (timestamp: number) => {
      if (start === null) start = timestamp
      const progress = Math.min((timestamp - start) / duration, 1)
      const value = Math.round(riskTarget * easeOutCubic(progress))
      setRiskValue(value)
      if (progress < 1) frameId = window.requestAnimationFrame(step)
    }

    frameId = window.requestAnimationFrame(step)
    return () => window.cancelAnimationFrame(frameId)
  }, [riskTarget])

  return (
    <div className="app">
      <div className="phone">
        <div className="screen" role="main">
          {activeTab === 'profile' ? (
            <section className="profile">
              <div className="profile-header">
                <img className="profile-avatar" src="/grandpa.jpg" alt="남동구 프로필" />
                <div className="profile-name">남동구</div>
                <div className="profile-sub">1943.02.01.</div>
                <div className="profile-address">서울특별시 마포구 마포대로 122 13층</div>
              </div>

              <div className="profile-list">
                <div className="profile-item">
                  <span>상대방 이름</span>
                  <span className="profile-right">
                    <span className="profile-value">뚝뚝이</span>
                    <span className="profile-chevron" aria-hidden="true">
                      ›
                    </span>
                  </span>
                </div>
                <div className="profile-item">
                  <span>상대방 목소리</span>
                  <span className="profile-right">
                    <span className="profile-value">소년</span>
                    <span className="profile-chevron" aria-hidden="true">
                      ›
                    </span>
                  </span>
                </div>
                <div className="profile-item">
                  <span>전화 간격</span>
                  <span className="profile-right">
                    <span className="profile-value">매일</span>
                    <span className="profile-chevron" aria-hidden="true">
                      ›
                    </span>
                  </span>
                </div>
                <div className="profile-item">
                  <span>전화 시각</span>
                  <span className="profile-right">
                    <span className="profile-value">오후 3:00</span>
                    <span className="profile-chevron" aria-hidden="true">
                      ›
                    </span>
                  </span>
                </div>
              </div>

              <div className="profile-list">
                <div className="profile-item">
                  <span>고객센터</span>
                  <span className="profile-right">
                    <span className="profile-value" />
                    <span className="profile-chevron" aria-hidden="true">
                      ›
                    </span>
                  </span>
                </div>
                <div className="profile-item">
                  <span>공지사항</span>
                  <span className="profile-right">
                    <span className="profile-value" />
                    <span className="profile-chevron" aria-hidden="true">
                      ›
                    </span>
                  </span>
                </div>
                <div className="profile-item">
                  <span>다른 대상자 추가하기</span>
                  <span className="profile-right">
                    <span className="profile-value" />
                    <span className="profile-chevron" aria-hidden="true">
                      ›
                    </span>
                  </span>
                </div>
                <div className="profile-item">
                  <span>로그아웃</span>
                  <span className="profile-right">
                    <span className="profile-value" />
                    <span className="profile-chevron" aria-hidden="true">
                      ›
                    </span>
                  </span>
                </div>
              </div>
            </section>
          ) : activeTab === 'analysis' ? (
            <section className="analysis">
              <div className="analysis-header">
                <h2 className="analysis-title">분석</h2>
                <p className="analysis-sub">
                  사용자들의 날짜별 인지능력 저하 심각도 추이
                </p>
              </div>

              <div className="analysis-card">
                <div className="analysis-months">
                  <span>8월</span>
                  <span>9월</span>
                  <span>10월</span>
                  <span>11월</span>
                  <span>12월</span>
                  <span>1월</span>
                </div>
                <div className="grass-grid" role="img" aria-label="일자별 심각도">
                  {analysisGrid.map((level, index) => (
                    <span
                      key={`cell-${index}`}
                      className={`grass-cell level-${level}`}
                    />
                  ))}
                </div>
                <div className="grass-legend">
                  <span className="legend-label">낮음</span>
                  <div className="legend-scale">
                    {[0, 1, 2, 3, 4].map((level) => (
                      <span
                        key={`legend-${level}`}
                        className={`grass-cell level-${level}`}
                      />
                    ))}
                  </div>
                  <span className="legend-label">높음</span>
                </div>
              </div>

              <div className="analysis-card">
                <div className="analysis-chart">
                  <div className="chart-grid">
                    {[100, 75, 50, 25, 0].map((tick) => (
                      <div className="chart-row" key={tick}>
                        <span className="chart-label">{tick}</span>
                        <span className="chart-line" />
                      </div>
                    ))}
                  </div>
                  <svg className="chart-svg" viewBox="0 0 320 200" aria-hidden="true">
                    <path
                      className="chart-line orange"
                      d="M10 40 C 70 40, 90 50, 120 60 S 180 160, 230 170 S 300 160, 310 40"
                    />
                    <path
                      className="chart-line purple"
                      d="M10 140 C 70 100, 120 60, 160 50 S 230 120, 300 190"
                    />
                    <path
                      className="chart-line pink"
                      d="M10 180 C 60 90, 110 70, 160 80 S 240 90, 310 110"
                    />
                    <g className="chart-points">
                      <circle cx="10" cy="40" r="5" className="dot orange" />
                      <circle cx="120" cy="60" r="5" className="dot orange" />
                      <circle cx="160" cy="160" r="5" className="dot orange" />
                      <circle cx="230" cy="170" r="5" className="dot orange" />
                      <circle cx="310" cy="40" r="5" className="dot orange" />

                      <circle cx="10" cy="140" r="5" className="dot purple" />
                      <circle cx="120" cy="90" r="5" className="dot purple" />
                      <circle cx="160" cy="50" r="5" className="dot purple" />
                      <circle cx="230" cy="120" r="5" className="dot purple" />
                      <circle cx="310" cy="190" r="5" className="dot purple" />

                      <circle cx="10" cy="180" r="5" className="dot pink" />
                      <circle cx="120" cy="100" r="5" className="dot pink" />
                      <circle cx="160" cy="90" r="5" className="dot pink" />
                      <circle cx="230" cy="100" r="5" className="dot pink" />
                      <circle cx="310" cy="110" r="5" className="dot pink" />
                    </g>
                  </svg>
                  <div className="chart-xlabels">
                    <span>Text</span>
                    <span>Text</span>
                    <span>Text</span>
                    <span>Text</span>
                    <span>Text</span>
                  </div>
                </div>
              </div>
            </section>
          ) : activeTab === 'history' ? (
            <section className="history">
              <div className="history-header">
                <h2 className="history-title">통화 기록</h2>
                <div className="history-search">
                  <span className="history-search-icon" aria-hidden="true">
                    🔍
                  </span>
                  <input
                    className="history-input"
                    type="text"
                    placeholder="날짜, 키워드로 검색"
                    aria-label="날짜, 키워드로 검색"
                  />
                  <span className="history-mic" aria-hidden="true">
                    🎤
                  </span>
                </div>
              </div>

              <div className="history-sections">
                {historySections.map((section) => (
                  <div className="history-section" key={section.title}>
                    <div className="history-month">{section.title}</div>
                    <div className="history-cards">
                      {section.items.map((item, index) => (
                        <article className="call-card history-card" key={`${item.time}-${index}`}>
                          <div className="call-time">{item.time}</div>
                          <div className="call-tags">
                            <span className="tag risk">{item.risk}</span>
                            <span className="tag alert">{item.signals}</span>
                          </div>
                          <div className="call-summary">{item.summary}</div>
                        </article>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ) : (
            <>
              <section className="hero">
                <p className="hero-title">
                  <span className="hero-name">남동구</span> 님의 위험도는…
                </p>
                <div className="gauge">
                  <svg viewBox="0 0 200 120" className="gauge-svg" aria-hidden="true">
                    <defs>
                      <linearGradient id="riskGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="#7c3aed" />
                        <stop offset="55%" stopColor="#ec4899" />
                        <stop offset="100%" stopColor="#f97316" />
                      </linearGradient>
                    </defs>
                    <path
                      className="gauge-track"
                      d="M20 100 A80 80 0 0 1 180 100"
                    />
                    <path
                      className="gauge-progress"
                      d="M20 100 A80 80 0 0 1 180 100"
                      pathLength="100"
                    />
                  </svg>
                  <div className="gauge-center">
                    <div className="gauge-value">{riskValue}%</div>
                    <div className="gauge-label">
                      <span>인지 능력 저하</span>
                      <span>가능성 높음</span>
                    </div>
                  </div>
                </div>
              </section>

              <section className="section">
                <div className="section-title">근처 병원 정보</div>
                <div className="h-scroll" aria-label="근처 병원 리스트">
                  <div className="h-scroll-inner">
                    {hospitals.map((hospital, index) => (
                      <article className="hospital-card" key={`${hospital.name}-${index}`}>
                        <div
                          className="hospital-thumb"
                          style={{ backgroundImage: 'url(/hospital.jpg)' }}
                          aria-hidden="true"
                        />
                        <div className="hospital-info">
                          <div className="hospital-name">{hospital.name}</div>
                          <div className="hospital-rating">
                            <span className="rating-score">
                              {hospital.rating.toFixed(1)}
                            </span>
                            <span className="stars" aria-hidden="true">
                              <span className="star active">★</span>
                              <span className="star active">★</span>
                              <span className="star active">★</span>
                              <span className="star">★</span>
                              <span className="star">★</span>
                            </span>
                          </div>
                          <div className="hospital-address">{hospital.address}</div>
                          <div className="hospital-meta">
                            <span className="status open">{hospital.status}</span>
                            <span className="close">{hospital.close}</span>
                          </div>
                        </div>
                      </article>
                    ))}
                  </div>
                </div>
              </section>

              <section className="section">
                <div className="section-title">최근 통화 기록</div>
                <div className="call-list">
                  {calls.map((call, index) => (
                    <article className="call-card" key={`${call.time}-${index}`}>
                      <div className="call-time">{call.time}</div>
                      <div className="call-tags">
                        <span className="tag risk">{call.risk}</span>
                        <span className="tag alert">{call.signals}</span>
                      </div>
                      <div className="call-summary">{call.summary}</div>
                    </article>
                  ))}
                </div>
                <button className="more-button" type="button">
                  더보기
                </button>
              </section>
            </>
          )}
        </div>

        <nav className="bottom-nav" aria-label="메뉴">
          <button
            className={`nav-item ${activeTab === 'home' ? 'active' : ''}`}
            type="button"
            aria-current={activeTab === 'home' ? 'page' : undefined}
            onClick={() => setActiveTab('home')}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M4 10.5L12 4l8 6.5V20a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1v-9.5Z" />
            </svg>
            <span>홈</span>
          </button>
          <button
            className={`nav-item ${activeTab === 'analysis' ? 'active' : ''}`}
            type="button"
            aria-current={activeTab === 'analysis' ? 'page' : undefined}
            onClick={() => setActiveTab('analysis')}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M4 19h3V9H4v10Zm6 0h3V5h-3v14Zm6 0h3v-7h-3v7Z" />
            </svg>
            <span>분석</span>
          </button>
          <button
            className={`nav-item ${activeTab === 'history' ? 'active' : ''}`}
            type="button"
            aria-current={activeTab === 'history' ? 'page' : undefined}
            onClick={() => setActiveTab('history')}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M6 4h9l3 3v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1Zm8 1v3h3" />
            </svg>
            <span>기록</span>
          </button>
          <button
            className={`nav-item ${activeTab === 'profile' ? 'active' : ''}`}
            type="button"
            aria-current={activeTab === 'profile' ? 'page' : undefined}
            onClick={() => setActiveTab('profile')}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 12a4 4 0 1 0-0.001-8.001A4 4 0 0 0 12 12Zm7 8a7 7 0 0 0-14 0" />
            </svg>
            <span>프로필</span>
          </button>
        </nav>
      </div>
    </div>
  )
}

export default App
