import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "IncidentSherpa",
  description: "Active incident-commander agent — live typed event timeline",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
