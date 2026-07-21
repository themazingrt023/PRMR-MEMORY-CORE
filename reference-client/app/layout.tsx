import "./style.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "PRMR Reference Project Client",
  description: "Independent project-management reference client for PRMR Memory Core."
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
