import type { Metadata } from "next";
import "./globals.css";

const officialSiteUrl = "https://afternumindustries.co.uk";

export const metadata: Metadata = {
  metadataBase: new URL(officialSiteUrl),
  title: "Afternum Industries / PRMR Memory Core",
  description: "Controlled-alpha frontend for PRMR Memory Core.",
  alternates: {
    canonical: "/"
  },
  openGraph: {
    title: "Afternum Industries / PRMR Memory Core",
    description: "Controlled-alpha frontend for PRMR Memory Core.",
    type: "website",
    url: officialSiteUrl
  }
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-body antialiased">{children}</body>
    </html>
  );
}
