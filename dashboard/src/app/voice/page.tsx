"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { VoiceOrb } from "@/components/VoiceOrb";

interface SpeechRecognitionEvent extends Event {
  results: { length: number; [index: number]: { isFinal: boolean; [index: number]: { transcript: string } } };
  resultIndex: number;
}

interface SpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  onresult: ((ev: SpeechRecognitionEvent) => void) | null;
  onerror: ((ev: Event) => void) | null;
  onend: (() => void) | null;
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

  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const animationRef = useRef<number | null>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const listeningRef = useRef(false);

  useEffect(() => {
    return () => { stopListening(); };
  }, []);

  async function startListening() {
    setError(null);
    setTranscript("");
    setInterim("");

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      streamRef.current = stream;

      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const audioContext = new AudioCtx();
      audioContextRef.current = audioContext;

      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.85;
      analyserRef.current = analyser;

      const source = audioContext.createMediaStreamSource(stream);
      source.connect(analyser);

      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      const tick = () => {
        if (!analyserRef.current) return;
        analyserRef.current.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
        const avg = sum / dataArray.length;
        setAmplitude(Math.min(1, avg / 100));
        animationRef.current = requestAnimationFrame(tick);
      };
      tick();

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

        recognition.onerror = () => {
          setError("Speech recognition paused — click start again");
        };

        recognition.onend = () => {
          if (listeningRef.current) {
            try { recognition.start(); } catch {}
          }
        };

        recognition.start();
        recognitionRef.current = recognition;
      }

      setListening(true);
      listeningRef.current = true;
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      stopListening();
    }
  }

  function stopListening() {
    setListening(false);
    listeningRef.current = false;
    setAmplitude(0);

    if (animationRef.current !== null) {
      cancelAnimationFrame(animationRef.current);
      animationRef.current = null;
    }
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch {}
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

  return (
    <div className="relative flex h-screen flex-col items-center justify-center bg-black overflow-hidden">

      <div className="absolute left-5 top-5 z-10">
        <Link
          href="/"
          className="text-xs tracking-widest text-zinc-600 transition hover:text-zinc-400"
          style={{ fontFamily: "monospace" }}
        >
          &larr; back
        </Link>
      </div>

      <div className="absolute right-5 top-5 z-10 flex items-center gap-2">
        <div className="h-1.5 w-1.5 rounded-full bg-emerald-500" style={{ boxShadow: "0 0 6px rgba(16,185,129,0.6)" }} />
        <span className="text-[10px] tracking-widest text-zinc-700" style={{ fontFamily: "monospace" }}>
          {listening ? "listening" : "ready"}
        </span>
      </div>

      <div className="flex flex-col items-center">
        <VoiceOrb amplitude={amplitude} listening={listening} />

        <div className="mt-8 flex flex-col items-center gap-6">
          <button
            onClick={listening ? stopListening : startListening}
            className={[
              "rounded-full border px-8 py-3 text-xs font-medium uppercase tracking-[0.2em] transition",
              listening
                ? "border-red-500/30 bg-red-500/5 text-red-400 hover:bg-red-500/10"
                : "border-zinc-700 bg-zinc-900/50 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200",
            ].join(" ")}
          >
            {listening ? "stop" : "start listening"}
          </button>

          <div className="min-h-[80px] max-w-lg px-6 text-center">
            {transcript || interim ? (
              <p className="text-sm leading-relaxed text-zinc-400">
                {transcript}
                {interim && <span className="text-zinc-600"> {interim}</span>}
              </p>
            ) : (
              <p className="text-xs text-zinc-700">
                {listening ? "speak — the sphere reacts to your voice" : "click start to begin"}
              </p>
            )}
          </div>

          {error && (
            <p className="text-[11px] text-red-500/60">{error}</p>
          )}
        </div>
      </div>

      <div className="absolute bottom-4 text-center">
        <p className="text-[9px] tracking-[0.15em] text-zinc-800">
          voice preview — not connected to lucy yet
        </p>
      </div>
    </div>
  );
}
