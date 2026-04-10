"use client";

import { useEffect, useState } from "react";

interface Props {
  amplitude: number; // 0 to 1
  listening: boolean;
}

export function VoiceOrb({ amplitude, listening }: Props) {
  // Smooth the amplitude for a nicer pulse (exponential smoothing)
  const [smoothed, setSmoothed] = useState(0);

  useEffect(() => {
    setSmoothed((prev) => prev * 0.6 + amplitude * 0.4);
  }, [amplitude]);

  // Much more aggressive scaling:
  // Base 80px, can grow to 200px at max amplitude
  const baseRadius = 80;
  const maxBoost = 120;
  // Apply a curve so quiet speech still shows a visible bump
  const boostedAmp = Math.pow(smoothed, 0.5); // sqrt curve: boosts low values
  const radius = baseRadius + boostedAmp * maxBoost;

  // Glow intensity scales with amplitude
  const glowIntensity = listening ? 0.5 + boostedAmp * 0.5 : 0.25;

  // Outer ring radii pulse too
  const ring1Radius = 160 + boostedAmp * 60;
  const ring2Radius = 200 + boostedAmp * 80;
  const ring3Radius = 240 + boostedAmp * 100;

  return (
    <div className="relative flex items-center justify-center">
      <svg
        width="600"
        height="600"
        viewBox="0 0 600 600"
        className="drop-shadow-2xl"
      >
        <defs>
          {/* Main orb gradient — sunlike core */}
          <radialGradient id="orbGradient" cx="50%" cy="50%">
            <stop offset="0%" stopColor="#fef3c7" stopOpacity="1" />
            <stop offset="20%" stopColor="#fbbf24" stopOpacity="1" />
            <stop offset="50%" stopColor="#f59e0b" stopOpacity="0.95" />
            <stop offset="80%" stopColor="#d97706" stopOpacity="0.7" />
            <stop offset="100%" stopColor="#92400e" stopOpacity="0" />
          </radialGradient>

          {/* Soft glow filter */}
          <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="20" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          {/* Outer glow */}
          <filter id="outerGlow" x="-100%" y="-100%" width="300%" height="300%">
            <feGaussianBlur stdDeviation="30" />
          </filter>
        </defs>

        {/* Outer pulse rings — visible when listening */}
        {listening && (
          <>
            <circle
              cx="300"
              cy="300"
              r={ring3Radius}
              fill="none"
              stroke="#fbbf24"
              strokeWidth="1"
              opacity={glowIntensity * 0.08}
              style={{ transition: "r 0.1s ease-out, opacity 0.1s ease-out" }}
            />
            <circle
              cx="300"
              cy="300"
              r={ring2Radius}
              fill="none"
              stroke="#fbbf24"
              strokeWidth="1.5"
              opacity={glowIntensity * 0.15}
              style={{ transition: "r 0.1s ease-out, opacity 0.1s ease-out" }}
            />
            <circle
              cx="300"
              cy="300"
              r={ring1Radius}
              fill="none"
              stroke="#fbbf24"
              strokeWidth="2"
              opacity={glowIntensity * 0.25}
              style={{ transition: "r 0.1s ease-out, opacity 0.1s ease-out" }}
            />
          </>
        )}

        {/* Soft outer glow halo — biggest, most blurred */}
        <circle
          cx="300"
          cy="300"
          r={radius * 1.4}
          fill="#f59e0b"
          opacity={glowIntensity * 0.15}
          filter="url(#outerGlow)"
          style={{ transition: "r 0.1s ease-out, opacity 0.1s ease-out" }}
        />

        {/* The main orb — SUN */}
        <circle
          cx="300"
          cy="300"
          r={radius}
          fill="url(#orbGradient)"
          filter="url(#glow)"
          opacity={listening ? 1 : 0.5}
          style={{ transition: "r 0.1s ease-out, opacity 0.5s ease-out" }}
        />

        {/* Inner bright highlight */}
        <circle
          cx={300 - radius * 0.15}
          cy={300 - radius * 0.15}
          r={radius * 0.25}
          fill="#fef3c7"
          opacity={listening ? glowIntensity * 0.7 : 0.15}
          style={{ transition: "all 0.1s ease-out" }}
        />

        {/* Tiny center bright spot for that "star core" look */}
        <circle
          cx="300"
          cy="300"
          r="8"
          fill="#ffffff"
          opacity={listening ? glowIntensity * 0.9 : 0.3}
        />
      </svg>
    </div>
  );
}
