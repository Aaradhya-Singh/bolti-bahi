"use client";

import { useState, useRef, useCallback } from "react";
import { Mic, Loader2, CheckCircle2, Play, Square, XCircle } from "lucide-react";
import { processVoice } from "@/lib/api";

const STATES = {
  IDLE: "idle",
  LISTENING: "listening",
  PROCESSING: "processing",
  RESULT: "result",
  ERROR: "error",
};

export default function VoiceButton({ shopId, languageCode = "hi-IN", onTransactionComplete }) {
  const [state, setState] = useState(STATES.IDLE);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);

  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const audioRef = useRef(null);
  const streamRef = useRef(null);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
  }, []);

  const startRecording = useCallback(async () => {
    try {
      setResult(null);
      setError(null);
      chunksRef.current = [];

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";

      const recorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      recorder.onstop = async () => {
        setState(STATES.PROCESSING);

        const blob = new Blob(chunksRef.current, { type: mimeType });

        try {
          const response = await processVoice(blob, shopId, languageCode);
          setResult(response);
          setState(STATES.RESULT);

          // Play response audio if present
          if (response.audio_response) {
            playAudio(response.audio_response);
          }

          // Notify parent to refresh
          onTransactionComplete?.();
        } catch (err) {
          setError(err.message || "कुछ गड़बड़ हो गई। दोबारा कोशिश करें।");
          setState(STATES.ERROR);
        }
      };

      recorder.start(250); // Collect in 250ms chunks
      setState(STATES.LISTENING);
    } catch (err) {
      if (err.name === "NotAllowedError") {
        setError("माइक्रोफ़ोन की अनुमति दें (Allow microphone access)");
      } else {
        setError("माइक्रोफ़ोन शुरू नहीं हो पाया");
      }
      setState(STATES.ERROR);
    }
  }, [shopId, languageCode, onTransactionComplete]);

  const handlePress = useCallback(() => {
    if (state === STATES.IDLE || state === STATES.RESULT || state === STATES.ERROR) {
      startRecording();
    } else if (state === STATES.LISTENING) {
      stopRecording();
    }
  }, [state, startRecording, stopRecording]);

  function playAudio(base64Audio) {
    try {
      const binaryString = atob(base64Audio);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }
      const blob = new Blob([bytes], { type: "audio/wav" });
      const url = URL.createObjectURL(blob);

      if (audioRef.current) {
        audioRef.current.pause();
        URL.revokeObjectURL(audioRef.current.src);
      }

      const audio = new Audio(url);
      audioRef.current = audio;
      setIsPlaying(true);

      audio.onended = () => {
        setIsPlaying(false);
        URL.revokeObjectURL(url);
      };
      audio.onerror = () => {
        setIsPlaying(false);
        URL.revokeObjectURL(url);
      };

      audio.play().catch(() => setIsPlaying(false));
    } catch {
      // Silently fail audio playback
    }
  }

  function toggleAudioPlayback() {
    if (audioRef.current && isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else if (result?.audio_response) {
      playAudio(result.audio_response);
    }
  }

  function resetToIdle() {
    setState(STATES.IDLE);
    setResult(null);
    setError(null);
    setIsPlaying(false);
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
  }

  // Button appearance by state
  const config = {
    [STATES.IDLE]: {
      bg: "bg-orange-500",
      ring: "",
      icon: <Mic size={36} className="text-white" />,
      label: "बोलिए",
      sublabel: "Tap to speak",
    },
    [STATES.LISTENING]: {
      bg: "bg-red-500 animate-pulse-dot",
      ring: "animate-pulse-ring",
      icon: <Square size={28} className="text-white" fill="white" />,
      label: "सुन रहे हैं...",
      sublabel: "Listening... Tap to stop",
    },
    [STATES.PROCESSING]: {
      bg: "bg-orange-400",
      ring: "",
      icon: <Loader2 size={36} className="text-white animate-spin-slow" />,
      label: "समझ रहे हैं...",
      sublabel: "Processing...",
    },
    [STATES.RESULT]: {
      bg: "bg-green-500",
      ring: "",
      icon: <CheckCircle2 size={36} className="text-white" />,
      label: "हो गया!",
      sublabel: "Done! Tap to speak again",
    },
    [STATES.ERROR]: {
      bg: "bg-red-400",
      ring: "",
      icon: <XCircle size={36} className="text-white" />,
      label: "गड़बड़",
      sublabel: "Error. Tap to retry",
    },
  };

  const c = config[state];

  return (
    <div className="flex flex-col items-center gap-3 py-4">
      {/* Main mic button */}
      <div className="relative flex items-center justify-center">
        {/* Pulse ring for listening state */}
        {state === STATES.LISTENING && (
          <div className="absolute inset-0 rounded-full bg-red-400 opacity-40 animate-pulse-ring" />
        )}
        <button
          onClick={handlePress}
          disabled={state === STATES.PROCESSING}
          className={`relative z-10 w-[88px] h-[88px] rounded-full flex items-center justify-center shadow-lg transition-all active:scale-95 disabled:opacity-80 disabled:cursor-wait ${c.bg}`}
          aria-label={c.label}
        >
          {c.icon}
        </button>
      </div>

      {/* Label */}
      <div className="text-center">
        <p className="text-lg font-semibold text-gray-800">{c.label}</p>
        <p className="text-xs text-gray-400">{c.sublabel}</p>
      </div>

      {/* Result card */}
      {state === STATES.RESULT && result && (
        <div className="w-full max-w-sm bg-white rounded-2xl shadow-md border border-gray-100 p-4 space-y-3">
          {/* Transcript */}
          {result.transcript && (
            <div>
              <p className="text-xs text-gray-400 mb-0.5">आपने कहा:</p>
              <p className="text-base text-gray-800 font-medium">
                &ldquo;{result.transcript}&rdquo;
              </p>
            </div>
          )}

          {/* Action taken */}
          {result.action && (
            <div className="bg-green-50 rounded-xl px-3 py-2">
              <p className="text-xs text-green-600 mb-0.5">किया गया काम:</p>
              <p className="text-sm text-green-800 font-medium">
                {result.action_description || result.action}
              </p>
            </div>
          )}

          {/* Amount if present */}
          {result.amount != null && (
            <p className="text-xl font-bold text-orange-600">
              ₹{Number(result.amount).toLocaleString("en-IN")}
            </p>
          )}

          {/* Audio playback */}
          {result.audio_response && (
            <button
              onClick={toggleAudioPlayback}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-orange-50 text-orange-600 font-medium text-sm min-h-[44px] active:bg-orange-100 transition-colors"
            >
              {isPlaying ? (
                <Square size={16} fill="currentColor" />
              ) : (
                <Play size={16} fill="currentColor" />
              )}
              {isPlaying ? "रोकें" : "जवाब सुनें"}
            </button>
          )}

          {/* Speak again */}
          <button
            onClick={resetToIdle}
            className="w-full text-center text-sm text-gray-400 py-2 min-h-[44px]"
          >
            फिर से बोलें →
          </button>
        </div>
      )}

      {/* Error message */}
      {state === STATES.ERROR && error && (
        <div className="w-full max-w-sm bg-red-50 rounded-2xl p-4 text-center">
          <p className="text-sm text-red-600">{error}</p>
          <button
            onClick={resetToIdle}
            className="mt-2 text-sm text-red-400 underline min-h-[44px]"
          >
            दोबारा कोशिश करें
          </button>
        </div>
      )}
    </div>
  );
}
