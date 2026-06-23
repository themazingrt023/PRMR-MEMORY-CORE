export function SilverDivider({ className = "" }: { className?: string }) {
  return (
    <div
      className={`h-px w-full bg-gradient-to-r from-transparent via-silver/45 to-transparent ${className}`}
    />
  );
}
