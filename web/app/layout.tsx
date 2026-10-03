import type { Metadata, Viewport } from "next";
import { Manrope } from "next/font/google";

import "./globals.css";

/**
 * Manrope is the closest open face to Paytm's own: geometric, heavy at 800 for
 * headings, with tabular figures for money.
 *
 * next/font downloads it at build time and serves it from our own domain, so a
 * judge's phone never asks Google for anything and the type survives the venue
 * wifi being off.
 */
const manrope = Manrope({
  weight: ["400", "500", "600", "700", "800"],
  subsets: ["latin"],
  variable: "--ff-manrope",
  display: "swap",
});

export const metadata: Metadata = {
  title: "BAHI",
  description: "The udhaar book both sides can see. Synthetic demo data.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>): React.ReactElement {
  return (
    <html lang="en" className={manrope.variable}>
      <body>{children}</body>
    </html>
  );
}
