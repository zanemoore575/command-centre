# CAiS Command Center - Frontend

Next.js frontend for the CAiS Command Center personal AI system.

## Setup

1. Install dependencies:
```bash
npm install
```

2. Configure environment:
```bash
cp .env.local.example .env.local
# Edit .env.local if needed (default points to http://localhost:8000)
```

3. Run development server:
```bash
npm run dev
```

The app will be available at http://localhost:3000

## Building for Production

```bash
npm run build
npm start
```

## Project Structure

```
frontend/
├── src/
│   ├── app/              # Next.js pages (App Router)
│   │   ├── layout.tsx    # Root layout
│   │   ├── page.tsx      # Home/Dashboard
│   │   ├── journal/      # Journal pages
│   │   └── people/       # People pages
│   ├── components/       # React components
│   │   ├── journal/      # Journal-related components
│   │   ├── dashboard/    # Dashboard components
│   │   └── people/       # People components
│   ├── lib/              # Utilities
│   │   ├── api.ts        # API client
│   │   └── types.ts      # TypeScript types
│   └── hooks/            # Custom React hooks
│       ├── useJournal.ts # Journal data hooks
│       └── usePeople.ts  # People data hooks
├── public/               # Static assets
└── package.json
```

## Tech Stack

- **Framework**: Next.js 15 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **State Management**: SWR for data fetching
- **API Communication**: Fetch API

## Environment Variables

- `NEXT_PUBLIC_API_URL` - Backend API URL (default: http://localhost:8000)

## Development Notes

- This app uses the Next.js App Router (not Pages Router)
- All pages are in `src/app/` following the file-based routing convention
- API calls are centralized in `src/lib/api.ts`
- TypeScript is enforced for type safety
