import type { Metadata } from "next";
import { Lora, Raleway } from "next/font/google";
import "./globals.css";

const lora = Lora({ variable: "--font-lora", subsets: ["latin"], display: "swap" });
const raleway = Raleway({ variable: "--font-raleway", subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  title: "Bedtime Stories",
  description: "Calm bedtime stories for ages 5-10, checked by an AI reviewer before they reach you.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${lora.variable} ${raleway.variable}`}>
      <body className="antialiased">
        <div className="stars pointer-events-none fixed inset-0" aria-hidden="true" />
        <div className="relative">{children}</div>
      </body>
    </html>
  );
}
