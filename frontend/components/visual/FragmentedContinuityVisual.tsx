"use client";

import { useEffect, useRef } from "react";

type NodePoint = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
  opacity: number;
  phase: number;
};

export function FragmentedContinuityVisual() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !context) return;

    let width = 0;
    let height = 0;
    let frame = 0;
    let visible = true;
    let nodes: NodePoint[] = [];
    const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = rect.width;
      height = rect.height;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
      nodes = Array.from({ length: 54 }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.26,
        vy: (Math.random() - 0.5) * 0.26,
        size: 1.2 + Math.random() * 2.6,
        opacity: 0.18 + Math.random() * 0.46,
        phase: Math.random() * Math.PI * 2
      }));
    };

    const observer = new IntersectionObserver(
      ([entry]) => {
        visible = entry.isIntersecting;
      },
      { threshold: 0.08 }
    );

    const draw = () => {
      context.clearRect(0, 0, width, height);
      context.fillStyle = "rgba(5, 5, 5, 0.9)";
      context.fillRect(0, 0, width, height);

      if (!prefersReduced && visible) {
        for (const node of nodes) {
          node.x += node.vx;
          node.y += node.vy;
          node.phase += 0.018;
          if (node.x < 0 || node.x > width) node.vx *= -1;
          if (node.y < 0 || node.y > height) node.vy *= -1;
        }
      }

      for (let i = 0; i < nodes.length; i += 1) {
        for (let j = i + 1; j < nodes.length; j += 1) {
          const dx = nodes[i].x - nodes[j].x;
          const dy = nodes[i].y - nodes[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 130) {
            const alpha = (1 - dist / 130) * 0.16;
            context.beginPath();
            context.moveTo(nodes[i].x, nodes[i].y);
            context.lineTo(nodes[j].x, nodes[j].y);
            context.strokeStyle = `rgba(232, 238, 245, ${alpha})`;
            context.lineWidth = 0.55;
            context.stroke();
          }
        }
      }

      for (const node of nodes) {
        const pulse = Math.sin(node.phase) * 0.25 + 0.75;
        context.beginPath();
        context.arc(node.x, node.y, node.size * pulse, 0, Math.PI * 2);
        context.fillStyle = `rgba(242, 245, 247, ${node.opacity * pulse})`;
        context.fill();
      }

      const scanY = height * (0.42 + Math.sin(Date.now() / 2400) * 0.1);
      const gradient = context.createLinearGradient(0, scanY - 42, 0, scanY + 42);
      gradient.addColorStop(0, "rgba(232, 238, 245, 0)");
      gradient.addColorStop(0.5, "rgba(232, 238, 245, 0.08)");
      gradient.addColorStop(1, "rgba(232, 238, 245, 0)");
      context.fillStyle = gradient;
      context.fillRect(0, scanY - 42, width, 84);

      frame = requestAnimationFrame(draw);
    };

    resize();
    observer.observe(canvas);
    window.addEventListener("resize", resize);
    frame = requestAnimationFrame(draw);

    return () => {
      observer.disconnect();
      window.removeEventListener("resize", resize);
      cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <div className="relative min-h-[360px] overflow-hidden border border-white/[0.08]">
      <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" aria-hidden="true" />
      <div className="absolute inset-x-0 bottom-0 h-28 bg-gradient-to-t from-ink to-transparent" />
    </div>
  );
}
