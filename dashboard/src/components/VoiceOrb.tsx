"use client";

import { useEffect, useRef } from "react";

interface Props {
  amplitude: number;
  listening: boolean;
}

interface Particle {
  theta: number;
  phi: number;
  baseR: number;
  currentR: number;
  thetaV: number;
  phiV: number;
  size: number;
  brightness: number;
  trail: Array<{ x: number; y: number; a: number }>;
}

export function VoiceOrb({ amplitude, listening }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stateRef = useRef({
    particles: [] as Particle[],
    edges: [] as [number, number][],
    currentSpread: 1.0,
    coreGlow: 0.3,
    t: 0,
    amplitude: 0,
    listening: false,
    initialized: false,
  });

  useEffect(() => {
    stateRef.current.amplitude = amplitude;
    stateRef.current.listening = listening;
  }, [amplitude, listening]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const s = stateRef.current;

    if (!s.initialized) {
      const NUM = 200;
      for (let i = 0; i < NUM; i++) {
        s.particles.push({
          theta: Math.random() * Math.PI * 2,
          phi: Math.acos(2 * Math.random() - 1),
          baseR: 0.85 + Math.random() * 0.15,
          currentR: 0.85 + Math.random() * 0.15,
          thetaV: (Math.random() - 0.5) * 0.003,
          phiV: (Math.random() - 0.5) * 0.002,
          size: 0.8 + Math.random() * 1.5,
          brightness: 0.3 + Math.random() * 0.7,
          trail: [],
        });
      }
      for (let i = 0; i < NUM; i++) {
        for (let j = i + 1; j < NUM; j++) {
          if (Math.random() < 0.012) s.edges.push([i, j]);
        }
      }
      s.initialized = true;
    }

    const W = canvas.width;
    const H = canvas.height;
    const CX = W / 2;
    const CY = H * 0.45;
    const BASE = 130;
    let raf: number;

    function project(p: Particle, spread: number) {
      const r = p.currentR * BASE * spread;
      const x = r * Math.sin(p.phi) * Math.cos(p.theta);
      const y = r * Math.sin(p.phi) * Math.sin(p.theta);
      const z = r * Math.cos(p.phi);
      const perspective = 600;
      const scale = perspective / (perspective + z);
      return {
        sx: CX + x * scale,
        sy: CY + y * scale,
        z,
        scale,
        depth: (z + BASE * spread) / (2 * BASE * spread),
      };
    }

    function frame() {
      if (!ctx) return;
      ctx.clearRect(0, 0, W, H);
      s.t += 0.016;

      const amp = s.amplitude;
      const isListening = s.listening;

      let targetSpread: number;
      let targetCoreGlow: number;

      if (!isListening && amp < 0.01) {
        targetSpread = 1.0 + Math.sin(s.t * 0.8) * 0.06;
        targetCoreGlow = 0.2 + Math.sin(s.t * 1.2) * 0.08;
      } else if (isListening && amp < 0.1) {
        targetSpread = 0.6 + Math.sin(s.t * 1.5) * 0.03;
        targetCoreGlow = 0.5 + Math.sin(s.t * 2) * 0.15;
      } else {
        const boosted = Math.pow(amp, 0.6);
        targetSpread = 0.6 + boosted * 2.0 + Math.sin(s.t * 3) * boosted * 0.15;
        targetCoreGlow = 0.4 + boosted * 0.6;
      }

      s.currentSpread += (targetSpread - s.currentSpread) * 0.045;
      s.coreGlow += (targetCoreGlow - s.coreGlow) * 0.05;

      const rotSpeed = 0.3 + (s.currentSpread - 0.5) * 0.8;
      const isExpanding = s.currentSpread > 1.2;

      for (let i = 0; i < s.particles.length; i++) {
        const p = s.particles[i];
        p.theta += p.thetaV * rotSpeed;
        p.phi += p.phiV * rotSpeed;
        if (isExpanding) {
          p.currentR = p.baseR + (Math.random() - 0.5) * 0.01;
        } else {
          p.currentR += (p.baseR - p.currentR) * 0.02;
        }
      }

      const outerR = BASE * s.currentSpread * 1.5;
      const cg = ctx.createRadialGradient(CX, CY, 0, CX, CY, outerR);
      cg.addColorStop(0, `rgba(200,230,255,${s.coreGlow * 0.15})`);
      cg.addColorStop(0.3, `rgba(160,200,240,${s.coreGlow * 0.06})`);
      cg.addColorStop(1, "rgba(120,170,220,0)");
      ctx.beginPath();
      ctx.arc(CX, CY, outerR, 0, Math.PI * 2);
      ctx.fillStyle = cg;
      ctx.fill();

      const coreR = 8 + s.coreGlow * 25;
      const coreG = ctx.createRadialGradient(CX, CY, 0, CX, CY, coreR);
      coreG.addColorStop(0, `rgba(255,255,255,${s.coreGlow * 0.9})`);
      coreG.addColorStop(0.3, `rgba(210,235,255,${s.coreGlow * 0.5})`);
      coreG.addColorStop(0.7, `rgba(170,210,250,${s.coreGlow * 0.15})`);
      coreG.addColorStop(1, "rgba(140,190,240,0)");
      ctx.beginPath();
      ctx.arc(CX, CY, coreR, 0, Math.PI * 2);
      ctx.fillStyle = coreG;
      ctx.fill();

      const proj = s.particles.map((p) => project(p, s.currentSpread));

      for (let i = 0; i < s.edges.length; i++) {
        const a = proj[s.edges[i][0]];
        const b = proj[s.edges[i][1]];
        const dx = a.sx - b.sx;
        const dy = a.sy - b.sy;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const maxDist = 120 * s.currentSpread;
        if (dist > maxDist) continue;
        const alpha =
          (1 - dist / maxDist) * 0.25 * ((a.depth + b.depth) / 2) *
          (isExpanding ? 0.5 : 1);
        ctx.beginPath();
        ctx.moveTo(a.sx, a.sy);
        ctx.lineTo(b.sx, b.sy);
        ctx.strokeStyle = `rgba(180,220,255,${alpha})`;
        ctx.lineWidth = 0.5;
        ctx.stroke();
      }

      for (let i = 0; i < s.particles.length; i++) {
        const p = proj[i];
        const part = s.particles[i];
        const sz = part.size * p.scale * (0.8 + s.coreGlow * 0.5);
        const alpha = p.depth * part.brightness * (0.4 + s.coreGlow * 0.4);

        if (isExpanding) {
          part.trail.push({ x: p.sx, y: p.sy, a: alpha * 0.3 });
          if (part.trail.length > 3) part.trail.shift();
          for (let ti = 0; ti < part.trail.length; ti++) {
            const tt = part.trail[ti];
            const ta = tt.a * (ti / part.trail.length) * 0.5;
            ctx.beginPath();
            ctx.arc(tt.x, tt.y, sz * 0.6, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(180,220,255,${ta})`;
            ctx.fill();
          }
        } else {
          part.trail = [];
        }

        ctx.beginPath();
        ctx.arc(p.sx, p.sy, sz, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(210,235,255,${alpha})`;
        ctx.fill();

        if (part.brightness > 0.85) {
          ctx.beginPath();
          ctx.arc(p.sx, p.sy, sz * 2.5, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(220,240,255,${alpha * 0.15})`;
          ctx.fill();
        }
      }

      if (isExpanding) {
        const numSparks = Math.floor(5 + amp * 15);
        for (let i = 0; i < numSparks; i++) {
          const angle = Math.random() * Math.PI * 2;
          const dist2 = BASE * s.currentSpread * (0.8 + Math.random() * 0.5);
          const sx = CX + Math.cos(angle) * dist2;
          const sy = CY + Math.sin(angle) * dist2;
          ctx.beginPath();
          ctx.arc(sx, sy, 0.5 + Math.random(), 0, Math.PI * 2);
          ctx.fillStyle = `rgba(220,240,255,${Math.random() * 0.4})`;
          ctx.fill();
        }
      }

      const rimAlpha = 0.06 + s.coreGlow * 0.08;
      ctx.beginPath();
      ctx.arc(CX, CY, BASE * s.currentSpread, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(180,220,255,${rimAlpha})`;
      ctx.lineWidth = 0.5;
      ctx.stroke();

      raf = requestAnimationFrame(frame);
    }

    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <canvas
      ref={canvasRef}
      width={700}
      height={500}
      className="block max-w-full"
    />
  );
}
