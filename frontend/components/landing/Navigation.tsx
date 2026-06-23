import { AfternumMark } from "@/components/brand/AfternumMark";

const navLinks = [
  { href: "/#problem", label: "Problem" },
  { href: "/#solution", label: "Solution" },
  { href: "/#api", label: "API" },
  { href: "/#demo", label: "Demo" },
  { href: "/#evidence", label: "Evidence" },
  { href: "/#access", label: "Access" },
  { href: "/contact", label: "Contact" }
];

export function Navigation() {
  return (
    <header className="fixed left-0 right-0 top-0 z-50 bg-gradient-to-b from-ink/78 via-ink/28 to-transparent backdrop-blur-[2px]">
      <nav className="mx-auto flex h-20 items-center justify-between px-[5vw] transition-colors duration-500">
        <a className="flex items-center gap-3" href="/" aria-label="Afternum Industries home">
          <AfternumMark size="nav" />
          <div className="leading-tight">
            <p className="font-mono text-lg uppercase tracking-[-0.03em] text-mist drop-shadow-[0_0_14px_rgba(0,0,0,0.85)]">AFTERNUM</p>
          </div>
        </a>
        <div className="hidden items-center gap-7 md:flex lg:gap-10">
          {navLinks.map((link) => (
            <a className="nav-link" href={link.href} key={link.href}>
              {link.label}
            </a>
          ))}
        </div>
      </nav>
    </header>
  );
}
