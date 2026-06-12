import type { Metadata } from "next";
import { Plus_Jakarta_Sans, JetBrains_Mono } from "next/font/google";
import "@openuidev/react-ui/components.css";
import "./globals.css";

const plusJakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

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
    <html lang="en" className={`dark ${plusJakarta.variable} ${jetbrainsMono.variable}`}>
      <body className="font-sans antialiased text-slate-200 bg-[#060814] selection:bg-sky-500/30 selection:text-sky-200 min-h-screen">
        {children}
      </body>
    </html>
  );
}
