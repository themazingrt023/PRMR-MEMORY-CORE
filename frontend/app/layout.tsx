import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Afternum Industries / PRMR Memory Core",
  description: "Controlled-alpha frontend for PRMR Memory Core."
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-body antialiased">{children}</body>
    </html>
  );
}
