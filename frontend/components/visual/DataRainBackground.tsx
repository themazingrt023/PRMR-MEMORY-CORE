"use client";

import { useEffect, useRef } from "react";

const glyphs = "0123456789x/DSPr~<>+=abgqfpw";

export function DataRainBackground({ className = "" }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;
    const cnv = canvas;
    const ctx = context;

    let width = 0;
    let height = 0;
    let waterSurface = 0;
    let frame = 0;
    let lastTime = 0;
    const fontSize = 16;
    const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let columns: Array<{ y: number; speed: number; opacity: number; length: number; hitWater: boolean }> = [];
    let ripples: Array<{ x: number; y: number; radius: number; life: number }> = [];

    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = cnv.clientWidth || window.innerWidth;
      height = cnv.clientHeight || window.innerHeight;
      waterSurface = height * 0.78;
      cnv.width = Math.max(1, Math.floor(width * dpr));
      cnv.height = Math.max(1, Math.floor(height * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const count = Math.ceil(width / fontSize);
      columns = Array.from({ length: count }, () => ({
        y: Math.random() * waterSurface - 120,
        speed: 0.7 + Math.random() * 2.2,
        opacity: 0.16 + Math.random() * 0.48,
        length: 10 + Math.floor(Math.random() * 20),
        hitWater: false
      }));
    }

    function spawnRipple(x: number) {
      ripples.push({ x, y: waterSurface, radius: 0, life: 1 });
      if (ripples.length > 30) ripples.shift();
    }

    function draw(timestamp = 0) {
      const dt = Math.min((timestamp - (lastTime || timestamp)) / 1000, 0.05) || 0.016;
      lastTime = timestamp;
      const time = timestamp / 1000;

      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = "#090909";
      ctx.fillRect(0, 0, width, height);
      ctx.font = `${fontSize}px ui-monospace, SFMono-Regular, Menlo, monospace`;
      ctx.textAlign = "center";
      ctx.textBaseline = "top";

      columns.forEach((column, index) => {
        const x = index * fontSize + fontSize / 2;
        const previous = column.y;
        column.y += column.speed * 60 * dt;

        for (let j = 0; j < column.length; j++) {
          const y = column.y - j * fontSize;
          if (y < -fontSize || y > waterSurface) continue;
          const fadeToWater = Math.max(0, Math.min(1, (waterSurface - y) / (fontSize * 3)));
          const alpha = column.opacity * Math.max(0, 1 - j / column.length) * fadeToWater;
          if (alpha < 0.02) continue;
          const char = glyphs[Math.floor(Math.random() * glyphs.length)];
          ctx.fillStyle = j === 0 ? `rgba(250, 253, 255, ${Math.min(alpha + 0.22, 0.9)})` : `rgba(194, 207, 220, ${alpha})`;
          ctx.shadowColor = "rgba(185, 215, 255, 0.26)";
          ctx.shadowBlur = j === 0 ? 10 : 0;
          ctx.fillText(char, x, y);
        }

        if (!column.hitWater && previous < waterSurface && column.y >= waterSurface) {
          column.hitWater = true;
          spawnRipple(x);
        }

        if (column.y - column.length * fontSize > waterSurface + 20) {
          column.y = -Math.random() * height * 0.5;
          column.speed = 0.7 + Math.random() * 2.2;
          column.opacity = 0.16 + Math.random() * 0.48;
          column.length = 10 + Math.floor(Math.random() * 20);
          column.hitWater = false;
        }
      });

      ctx.shadowBlur = 0;
      const waterGrad = ctx.createLinearGradient(0, waterSurface, 0, height);
      waterGrad.addColorStop(0, "rgba(9, 11, 13, 0.62)");
      waterGrad.addColorStop(1, "rgba(9, 9, 9, 0.96)");
      ctx.fillStyle = waterGrad;
      ctx.fillRect(0, waterSurface - 1, width, height - waterSurface + 1);

      ctx.beginPath();
      for (let x = 0; x <= width; x += 5) {
        const y = waterSurface + Math.sin(x * 0.012 + time * 0.8) * 1.4 + Math.sin(x * 0.027 + time * 0.42);
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = "rgba(226, 235, 244, 0.22)";
      ctx.lineWidth = 1.2;
      ctx.stroke();

      ripples = ripples.filter((ripple) => ripple.life > 0);
      ripples.forEach((ripple) => {
        ripple.radius += 28 * dt;
        ripple.life -= 0.38 * dt;
        for (let ring = 0; ring < 3; ring++) {
          const radius = ripple.radius - ring * 7;
          if (radius <= 0) continue;
          ctx.beginPath();
          ctx.ellipse(ripple.x, ripple.y + ring * 2, radius, radius * 0.28, 0, 0, Math.PI * 2);
          ctx.strokeStyle = `rgba(226, 235, 244, ${Math.max(0, ripple.life * (0.22 - ring * 0.045))})`;
          ctx.lineWidth = 1;
          ctx.stroke();
        }
      });

      if (!prefersReduced) frame = requestAnimationFrame(draw);
    }

    resize();
    if (!prefersReduced) draw();
    else {
      ctx.fillStyle = "rgba(226, 235, 244, 0.06)";
      ctx.fillRect(0, 0, width, height);
    }

    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      cancelAnimationFrame(frame);
    };
  }, []);

  return <canvas aria-hidden="true" className={`pointer-events-none absolute inset-0 h-full w-full ${className}`} ref={canvasRef} />;
}
