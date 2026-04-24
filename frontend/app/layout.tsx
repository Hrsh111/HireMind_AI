import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Algo Multi-Agent Interviewer',
  description: 'LiveKit + LangGraph interview panel with code execution',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
