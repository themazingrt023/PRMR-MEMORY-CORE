import "./style.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "PRMR Developer Console",
  description: "Separated authenticated developer console for PRMR Memory Core."
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
