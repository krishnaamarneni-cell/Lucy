"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { VoiceOrb } from "@/components/VoiceOrb";

// Minimal type for the Web Speech API since TypeScript doesn't ship with it
interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList;
  resultIndex: number;
}

interface SpeechRecognitionResultList {
  readonly length: number;
  item(index: number): SpeechRecognitionResult;
  [index: number]: SpeechRecognitionResult;
}

interface SpeechRecognitionResult {
  readonly length: number;
  item(index: number): SpeechRecognitionAlternative;
  [index: number]: SpeechRecognitionAlternative;
  readonly isFinal: boolean;
}

interface SpeechRecognitionAlternative {
  readonly transcript: string;
  readonly confidence: number;
}

interface SpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((this: SpeechRecognition, ev: SpeechRecognitionEvent) => void) | null;
  onerror: ((this: SpeechRecognition, ev: Event) => void) | null;
  onend: ((this: SpeechRecognition, ev: Event) => void) | null;
}

declare global {
  interface Window {
    SpeechRecognition?: new () => SpeechRecognition;
    webkitSpeechRecognition?: new () => SpeechRecognition;
  }
}

export default function VoicePage() {
  const [listening, setListening] = useState(false);
  const [amplitude, setAmplitude] = useState(0);
  const [transcript, setTranscript] = useState("");
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [supported, setSupported] = useState<boolean | null>(null);

  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const animationRef = useRef<number | null>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  useEffect(() => {
    // Check browser support for Web Speech API
    const SR =
      typeof window !== "undefined"
        ? window.SpeechRecognition || window.webkitSpeechRecognition
        : undefined;
    setSupported(Boolean(SR));
  }, []);

  useEffect(() => {
    return () => {
      stopListening();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function startListening() {
    setError(null);
    setTranscript("");
    setInterim("");

    try {
      // 1. Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;

      // 2. Set up Web Audio API for amplitude analysis
      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext })
          .webkitAudioContext;
      const audioContext = new AudioCtx();
      audioContextRef.current = audioContext;

      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.8;
      analyserRef.current = analyser;

      const source = audioContext.createMediaStreamSource(stream);
      source.connect(analyser);

      // 3. Start the amplitude read loop
      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      const tick = () => {
        if (!analyserRef.current) return;
        analyserRef.current.getByteFrequencyData(dataArray);
        // Average volume → 0-1 amplitude
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
        const avg = sum / dataArray.length;
        const normalized = Math.min(1, avg / 128);
        setAmplitude(normalized);
        animationRef.current = requestAnimationFrame(tick);
      };
      tick();

      // 4. Start Web Speech API for transcription
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (SR) {
        const recognition = new SR();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = "en-US";

        recognition.onresult = (event: SpeechRecognitionEvent) => {
          let finalText = "";
          let interimText = "";
          for (let i = event.resultIndex; i < event.results.length; i++) {
            const result = event.results[i];
            const text = result[0].transcript;
            if (result.isFinal) {
              finalText += text + " ";
            } else {
              interimText += text;
            }
          }
          if (finalText) {
            setTranscript((prev) => (prev + " " + finalText).trim());
            setInterim("");
          } else {
            setInterim(interimText);
          }
        };

        recognition.onerror = (ev: Event) => {
          const errEvent = ev as Event & { error?: string };
          setError(`Speech recognition error: ${errEvent.error || "unknown"}`);
        };

        recognition.onend = () => {
          // If we're supposed to be listening but it stopped, restart
          if (listening && recognitionRef.current) {
            try {
              recognitionRef.current.start();
            } catch {}
          }
        };

        recognition.start();
        recognitionRef.current = recognition;
      }

      setListening(true);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(`Microphone error: ${msg}`);
      stopListening();
    }
  }

  function stopListening() {
    setListening(false);
    setAmplitude(0);

    if (animationRef.current !== null) {
      cancelAnimationFrame(animationRef.current);
      animationRef.current = null;
    }
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {}
      recognitionRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    analyserRef.current = null;
  }

  function handleToggle() {
    if (listening) {
      stopListening();
    } else {
      startListening();
    }
  }

  return (
    <div className="relative flex h-screen flex-col bg-black text-zinc-100">
      {/* Back button */}
      <div className="absolute left-6 top-6 z-10">
        <Link
          href="/"
          className="flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/50 px-4 py-2 text-sm text-zinc-400 backdrop-blur transition hover:border-zinc-700 hover:text-zinc-200"
        >
          ← Back to chat
        </Link>
      </div>

      {/* Orb centered */}
      <div className="flex flex-1 flex-col items-center justify-center gap-12">
        <VoiceOrb amplitude={amplitude} listening={listening} />

        {/* Mic button */}
        <button
          onClick={handleToggle}
          disabled={supported === false}
          className={[
            "rounded-full border px-8 py-3 text-sm font-semibold uppercase tracking-widest transition",
            listening
              ? "border-red-500 bg-red-500/10 text-red-300 hover:bg-red-500/20"
              : "border-amber-500 bg-amber-500/10 text-amber-300 hover:bg-amber-500/20",
            "disabled:opacity-50",
          ].join(" ")}
        >
          {listening ? "◼ Stop" : "● Start listening"}
        </button>

        {supported === false && (
          <p className="text-xs text-red-400">
            Web Speech API not supported in this browser. Try Chrome or Edge.
          </p>
        )}

        {/* Live transcript */}
        <div className="mx-6 max-w-2xl text-center">
          {transcript || interim ? (
            <p className="text-lg text-zinc-300">
              <span>{transcript}</span>
              {interim && (
                <span className="text-zinc-500"> {interim}</span>
              )}
            </p>
          ) : (
            <p className="text-sm text-zinc-600">
              {listening
                ? "Listening... say something."
                : "Click Start listening and speak."}
            </p>
          )}
        </div>

        {error && (
          <p className="text-xs text-red-400">⚠ {error}</p>
        )}
      </div>

      {/* Preview notice */}
      <div className="pb-4 text-center">
        <p className="text-[10px] uppercase tracking-widest text-zinc-700">
          preview — voice view is local only, not connected to Lucy yet
        </p>
      </div>
    </div>
  );
}
