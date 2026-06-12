import type { Metadata } from "next";
import "@openuidev/react-ui/components.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "IncidentSherpa",
  description:
    "Active incident-commander agent — live typed event timeline, causal chain, streaming postmortem",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body>{children}</body>
    </html>
  );
}
