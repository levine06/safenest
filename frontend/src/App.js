import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';
import { getDomainById } from './config/domains';
import DomainSelector from './components/DomainSelector';
import SignalSimulator from './components/SignalSimulator';
import ResultsCard from './components/ResultsCard';
import AlertHistory from './components/AlertHistory';
import HeatMap from './components/HeatMap';
import VideoUploader from './components/VideoUploader';
import AnalysisProgress from './components/AnalysisProgress';
import VideoAnalysisResults from './components/VideoAnalysisResults';

const API_BASE_URL = 'http://localhost:5001';

function App() {
  // View state
  const [currentView, setCurrentView] = useState('dashboard'); // 'dashboard' or 'video'

  // Domain state
  const [selectedDomain, setSelectedDomain] = useState('child_safety');
  const currentDomain = getDomainById(selectedDomain);

  // Signal state (initialized based on domain)
  const [signals, setSignals] = useState({});

  // Results and UI state
  const [latestResult, setLatestResult] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Video analysis state
  const [videoAnalysisProgress, setVideoAnalysisProgress] = useState(0);
  const [videoAnalysisStatus, setVideoAnalysisStatus] = useState('');
  const [videoAnalysisResult, setVideoAnalysisResult] = useState(null);
  const [isAnalyzingVideo, setIsAnalyzingVideo] = useState(false);

  // Initialize signals when domain changes
  useEffect(() => {
    const initialSignals = {};
    currentDomain.signals.forEach((signal) => {
      initialSignals[signal.key] = false;
    });
    setSignals(initialSignals);
    setLatestResult(null); // Clear previous results when domain changes
  }, [selectedDomain, currentDomain]);

  // Fetch alerts on component mount
  useEffect(() => {
    fetchAlerts();
  }, []);

  const handleSignalChange = (signalName) => {
    setSignals((prev) => ({
      ...prev,
      [signalName]: !prev[signalName],
    }));
  };

  const analyzeRisk = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.post(`${API_BASE_URL}/analyze-risk`, {
        signals,
        domain: selectedDomain,
        context: {},
      });
      setLatestResult(response.data);
      // Refresh alerts after analysis
      await fetchAlerts();
    } catch (err) {
      setError(
        err.response?.data?.error || `Error: ${err.message}. Is backend running on port 5000?`
      );
    } finally {
      setLoading(false);
    }
  };

  const fetchAlerts = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/alerts`);
      setAlerts(response.data.alerts || []);
    } catch (err) {
      // Silently fail on fetch errors (backend might not be ready)
      console.error('Failed to fetch alerts:', err.message);
    }
  };

  const randomizeSignals = () => {
    const randomized = {};
    currentDomain.signals.forEach((signal) => {
      randomized[signal.key] = Math.random() > 0.5;
    });
    setSignals(randomized);
  };

  const clearAlerts = async () => {
    try {
      await axios.delete(`${API_BASE_URL}/alerts`);
      setAlerts([]);
    } catch (err) {
      console.error('Failed to clear alerts:', err.message);
      // Still clear locally even if API fails
      setAlerts([]);
    }
  };

  const analyzeVideo = async (videoFile) => {
    setIsAnalyzingVideo(true);
    setVideoAnalysisProgress(5);
    setVideoAnalysisStatus('Uploading video...');
    setVideoAnalysisResult(null);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('video', videoFile);

      // Track if response received
      let responseReceived = false;
      let currentProgress = 5;

      const updateProgress = () => {
        if (responseReceived) return; // Stop when response arrives

        // Increment smoothly: 2-5% per update
        currentProgress = Math.min(currentProgress + 2 + Math.random() * 3, 95);
        setVideoAnalysisProgress(currentProgress);
      };

      const progressInterval = setInterval(updateProgress, 500);

      // Update status messages based on time elapsed
      let elapsedTime = 0;
      const statusInterval = setInterval(() => {
        if (responseReceived) return;

        elapsedTime += 1000;
        if (elapsedTime > 8000) setVideoAnalysisStatus('Classifying domain...');
        else if (elapsedTime > 5000) setVideoAnalysisStatus('Analyzing motion & poses...');
        else if (elapsedTime > 2000) setVideoAnalysisStatus('Extracting frames...');
      }, 1000);

      // Set timeout for backend response (2.5 minutes)
      const timeoutId = setTimeout(() => {
        if (!responseReceived) {
          clearInterval(progressInterval);
          clearInterval(statusInterval);
          setIsAnalyzingVideo(false);
          setError('⏱️ Video analysis timeout - backend is taking too long. Is the server running?');
          setVideoAnalysisProgress(0);
        }
      }, 150000); // 2.5 minute timeout

      // Upload and analyze
      const response = await axios.post(`${API_BASE_URL}/analyze-video`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 150000, // Match timeout above
      });

      responseReceived = true;
      clearTimeout(timeoutId);
      clearInterval(progressInterval);
      clearInterval(statusInterval);

      setVideoAnalysisProgress(100);
      setVideoAnalysisStatus('✅ Analysis complete!');
      setVideoAnalysisResult(response.data);

      // Refresh alerts after analysis
      fetchAlerts();
    } catch (err) {
      let errorMsg = 'Error analyzing video';

      if (err.code === 'ECONNABORTED') {
        errorMsg = '⏱️ Request timeout - backend is not responding';
      } else if (err.response?.data?.error) {
        errorMsg = err.response.data.error;
      } else if (err.message) {
        errorMsg = err.message;
      }

      setError(errorMsg);
      console.error('Video analysis error:', err);
    } finally {
      setIsAnalyzingVideo(false);
      setTimeout(() => setVideoAnalysisProgress(0), 2000);
    }
  };

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="header-content">
          <h1>
            <svg
              className="shield-icon"
              width="32"
              height="32"
              viewBox="0 0 32 32"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M16 2L4 8V16C4 24 16 30 16 30C16 30 28 24 28 16V8L16 2Z"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                fill="none"
              />
            </svg>
            SafeNest
          </h1>
          <p className="tagline">Privacy-Preserving Community Safety Risk Intelligence</p>
        </div>
      </header>

      {/* View Tabs */}
      <div className="view-tabs">
        <button
          className={`view-tab ${currentView === 'dashboard' ? 'active' : ''}`}
          onClick={() => setCurrentView('dashboard')}
        >
          Dashboard
        </button>
        <button
          className={`view-tab ${currentView === 'video' ? 'active' : ''}`}
          onClick={() => setCurrentView('video')}
        >
          Video Analysis
        </button>
      </div>

      {/* Main Content */}
      <main className="main-content">
        <div className="container">
          {error && (
            <div className="error-message">
              <strong>⚠️ Error:</strong> {error}
            </div>
          )}

          {currentView === 'dashboard' ? (
            <>
              {/* Dashboard View */}
              <DomainSelector
                selectedDomain={selectedDomain}
                onDomainChange={setSelectedDomain}
                currentDomainInfo={currentDomain}
              />

              <div className="dashboard-grid">
                {/* Left Column: Signal Simulator + Results */}
                <div className="left-column">
                  <SignalSimulator
                    domain={currentDomain}
                    signals={signals}
                    onSignalChange={handleSignalChange}
                    onAnalyze={analyzeRisk}
                    onRandomize={randomizeSignals}
                    loading={loading}
                  />

                  {latestResult && <ResultsCard result={latestResult} domain={currentDomain} />}
                </div>

                {/* Right Column: Alert History */}
                <div className="right-column">
                  <AlertHistory alerts={alerts} domain={currentDomain} onClearAlerts={clearAlerts} />
                </div>
              </div>

              {/* Heat Map - Geographic Risk Distribution */}
              <HeatMap alerts={alerts} />
            </>
          ) : (
            <>
              {/* Video Analysis View */}
              {!isAnalyzingVideo && !videoAnalysisResult ? (
                <VideoUploader onAnalyze={analyzeVideo} isAnalyzing={isAnalyzingVideo} />
              ) : isAnalyzingVideo ? (
                <AnalysisProgress
                  progress={videoAnalysisProgress}
                  status={videoAnalysisStatus}
                  message={videoAnalysisStatus}
                />
              ) : (
                <>
                  <VideoAnalysisResults result={videoAnalysisResult} />
                  <button
                    className="btn btn-secondary"
                    onClick={() => {
                      setVideoAnalysisResult(null);
                      setVideoAnalysisProgress(0);
                    }}
                    style={{ marginTop: '1rem' }}
                  >
                    ← Analyze Another Video
                  </button>
                </>
              )}
            </>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="footer">
        <p>SafeNest v2.0 | Privacy-First Community Safety Dashboard | Multi-Domain Support</p>
      </footer>
    </div>
  );
}

export default App;
