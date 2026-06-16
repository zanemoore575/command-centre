import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'CAiS Command Center',
  description: 'Personal AI system for tracking your business journey',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
