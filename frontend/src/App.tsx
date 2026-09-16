import React from 'react';

export default function App(): React.ReactElement {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-950 text-slate-50 selection:bg-indigo-500 selection:text-white">
      <main className="flex flex-col items-center gap-4 p-8 text-center">
        <div className="inline-flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900/60 px-3 py-1 text-xs font-medium text-slate-400">
          <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
          Bootstrap Slice 0
        </div>
        <h1 className="text-5xl font-extrabold tracking-tight sm:text-6xl bg-gradient-to-r from-slate-100 via-slate-300 to-slate-500 bg-clip-text text-transparent">
          FlagOps
        </h1>
        <p className="max-w-md text-sm text-slate-400">
          Feature Flag & Application Configuration Management Service
        </p>
      </main>
    </div>
  );
}
