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
  wobble: number;
  wobbleSpeed: number;
  trail: Array<{ x: number; y: number; a: number }>;
}

export function VoiceOrb({ amplitude, listening }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stateRef = useRef({
    particles: [] as Particle[],
    edges: [] as [number, number][],
    currentSpread: 1.0,
    coreGlow: 0.5,
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
      const NUM = 250;
      for (let i = 0; i < NUM; i++) {
        s.particles.push({
          theta: Math.random() * Math.PI * 2,
          phi: Math.acos(2 * Math.random() - 1),
          baseR: 0.6 + Math.random() * 0.4,
          currentR: 0.6 + Math.random() * 0.4,
          thetaV: (Math.random() - 0.5) * 0.005,
          phiV: (Math.random() - 0.5) * 0.003,
          size: 1.0 + Math.random() * 1.5,
          brightness: 0.5 + Math.random() * 0.5,
          wobble: Math.random() * Math.PI * 2,
          wobbleSpeed: 0.5 + Math.random() * 2.0,
          trail: [],
        });
      }
      for (let i = 0; i < NUM; i++) {
        for (let j = i + 1; j < NUM; j++) {
          if (Math.random() < 0.014) s.edges.push([i, j]);
        }
      }
      s.initialized = true;
    }

    const W = canvas.width, H = canvas.height;
    const CX = W / 2, CY = H * 0.45, BASE = 110;
    let raf: number;

    function project(p: Particle, spread: number) {
      const wo = Math.sin(p.wobble) * 0.18 * Math.min(spread, 1.5);
      const r = (p.currentR + wo) * BASE * spread;
      const x = r * Math.sin(p.phi) * Math.cos(p.theta);
      const y = r * Math.sin(p.phi) * Math.sin(p.theta);
      const z = r * Math.cos(p.phi);
      const sc = 500 / (500 + z);
      return { sx: CX + x * sc, sy: CY + y * sc, z, scale: sc, depth: Math.max(0.2, (z + BASE * spread * 1.5) / (3 * BASE * spread)) };
    }

    function frame() {
      if (!ctx) return;
      ctx.clearRect(0, 0, W, H);
      s.t += 0.016;
      const amp = s.amplitude;
      const isL = s.listening;
      let tS: number, tC: number;

      if (!isL && amp < 0.01) {
        tS = 0.85 + Math.sin(s.t * 0.6) * 0.05;
        tC = 0.4 + Math.sin(s.t * 1.0) * 0.1;
      } else if (isL && amp < 0.08) {
        tS = 0.45 + Math.sin(s.t * 1.2) * 0.04;
        tC = 0.7 + Math.sin(s.t * 1.8) * 0.15;
      } else {
        const b = Math.pow(amp, 0.45);
        tS = 0.45 + b * 3.0 + Math.sin(s.t * 3.5) * b * 0.25;
        tC = 0.6 + b * 0.4;
      }

      s.currentSpread += (tS - s.currentSpread) * 0.05;
      s.coreGlow += (tC - s.coreGlow) * 0.06;
      const rs = 0.4 + (s.currentSpread - 0.5) * 1.2;
      const isExp = s.currentSpread > 1.0;

      for (let i = 0; i < s.particles.length; i++) {
        const p = s.particles[i];
        p.theta += p.thetaV * rs;
        p.phi += p.phiV * rs;
        p.wobble += p.wobbleSpeed * 0.016 * (1 + amp * 4);
        if (isExp) p.currentR = p.baseR + (Math.random() - 0.5) * 0.025;
        else p.currentR += (p.baseR - p.currentR) * 0.03;
      }

      const oR = BASE * s.currentSpread * 2.0;
      const cg = ctx.createRadialGradient(CX, CY, 0, CX, CY, oR);
      cg.addColorStop(0, `rgba(180,215,255,${s.coreGlow * 0.25})`);
      cg.addColorStop(0.2, `rgba(150,200,250,${s.coreGlow * 0.12})`);
      cg.addColorStop(0.5, `rgba(120,180,240,${s.coreGlow * 0.04})`);
      cg.addColorStop(1, "rgba(100,160,220,0)");
      ctx.beginPath(); ctx.arc(CX, CY, oR, 0, Math.PI * 2); ctx.fillStyle = cg; ctx.fill();

      const cr = 12 + s.coreGlow * 40;
      const cGr = ctx.createRadialGradient(CX, CY, 0, CX, CY, cr);
      cGr.addColorStop(0, `rgba(255,255,255,${Math.min(1, s.coreGlow * 1.1)})`);
      cGr.addColorStop(0.2, `rgba(230,245,255,${s.coreGlow * 0.8})`);
      cGr.addColorStop(0.5, `rgba(190,225,250,${s.coreGlow * 0.35})`);
      cGr.addColorStop(1, "rgba(150,200,240,0)");
      ctx.beginPath(); ctx.arc(CX, CY, cr, 0, Math.PI * 2); ctx.fillStyle = cGr; ctx.fill();

      const proj = s.particles.map((p) => project(p, s.currentSpread));

      for (let i = 0; i < s.edges.length; i++) {
        const a = proj[s.edges[i][0]], b = proj[s.edges[i][1]];
        const dx = a.sx - b.sx, dy = a.sy - b.sy;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const maxD = 100 * s.currentSpread;
        if (dist > maxD) continue;
        const al = (1 - dist / maxD) * 0.5 * ((a.depth + b.depth) / 2);
        ctx.beginPath(); ctx.moveTo(a.sx, a.sy); ctx.lineTo(b.sx, b.sy);
        ctx.strokeStyle = `rgba(200,230,255,${al})`; ctx.lineWidth = 0.8; ctx.stroke();
      }

      for (let i = 0; i < s.particles.length; i++) {
        const p = proj[i], pt = s.particles[i];
        const sz = pt.size * p.scale * (1.0 + s.coreGlow * 0.5);
        const al = Math.min(1, p.depth * pt.brightness * (0.7 + s.coreGlow * 0.3));

        if (isExp) {
          pt.trail.push({ x: p.sx, y: p.sy, a: al * 0.3 });
          if (pt.trail.length > 4) pt.trail.shift();
          for (let ti = 0; ti < pt.trail.length; ti++) {
            const tt = pt.trail[ti];
            ctx.beginPath(); ctx.arc(tt.x, tt.y, sz * 0.4, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(200,230,255,${tt.a * (ti / pt.trail.length) * 0.5})`;
            ctx.fill();
          }
        } else {
          pt.trail = [];
        }

        ctx.beginPath(); ctx.arc(p.sx, p.sy, sz, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(240,248,255,${al})`; ctx.fill();
      }

      if (isExp) {
        const ns = Math.floor(10 + amp * 30);
        for (let i = 0; i < ns; i++) {
          const ang = Math.random() * Math.PI * 2;
          const d2 = BASE * s.currentSpread * (0.5 + Math.random() * 1.0);
          const sx = CX + Math.cos(ang) * d2, sy = CY + Math.sin(ang) * d2;
          ctx.beginPath(); ctx.arc(sx, sy, 0.5 + Math.random() * 1.2, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(240,250,255,${0.3 + Math.random() * 0.5})`; ctx.fill();
        }
      }

      raf = requestAnimationFrame(frame);
    }
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, []);

  return <canvas ref={canvasRef} width={700} height={500} className="block max-w-full" />;
}
