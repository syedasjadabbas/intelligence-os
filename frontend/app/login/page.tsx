"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Cpu, Lock, Mail, ArrowRight, ShieldCheck, AlertCircle, X } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      await login({ email, password });
      setIsLoading(false);
      window.location.href = "/";
    } catch (err: any) {
      setIsLoading(false);
      setError(
        err?.message || "Login failed or request timed out. Please verify your credentials and ensure the backend is running."
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-[#070b14] via-[#0d1527] to-[#0a1120]">
      {/* Background glow effects */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

      <div className="relative w-full max-w-md">
        {/* Brand header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-tr from-cyan-500 to-indigo-600 shadow-lg shadow-cyan-500/20 mb-4">
            <Cpu className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white">
            Intelligence <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-indigo-400">OS</span>
          </h1>
          <p className="text-sm text-slate-400 mt-2">
            Enterprise Grounded RAG & Contextual Intelligence
          </p>
        </div>

        {/* Card */}
        <div className="glass rounded-2xl p-8 shadow-2xl border border-white/10 relative backdrop-blur-xl">
          <h2 className="text-xl font-bold text-white mb-2">Sign in to your account</h2>
          <p className="text-xs text-slate-400 mb-6">
            Access your organization's isolated document store and chat stream.
          </p>

          {/* Visible Error Banner / Alert */}
          {error && (
            <div
              role="alert"
              className="mb-6 p-3.5 rounded-xl bg-rose-500/15 border border-rose-500/40 text-rose-300 text-xs flex items-start justify-between gap-3 shadow-lg shadow-rose-950/20"
            >
              <div className="flex items-start gap-2.5 min-w-0">
                <AlertCircle className="w-4 h-4 shrink-0 text-rose-400 mt-0.5" />
                <span className="font-medium leading-relaxed break-words">{error}</span>
              </div>
              <button
                type="button"
                onClick={() => setError(null)}
                className="text-rose-400/80 hover:text-rose-200 transition-colors p-0.5 shrink-0 cursor-pointer"
                aria-label="Dismiss error message"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Work Email
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (error) setError(null);
                  }}
                  placeholder="tony@stark.com"
                  className="w-full pl-10 pr-4 py-2.5 bg-slate-900/60 border border-slate-700/60 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/40 focus:border-cyan-500 transition-all"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Password
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (error) setError(null);
                  }}
                  placeholder="••••••••••••"
                  className="w-full pl-10 pr-4 py-2.5 bg-slate-900/60 border border-slate-700/60 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/40 focus:border-cyan-500 transition-all"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full mt-2 py-3 px-4 bg-gradient-to-r from-cyan-500 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-white font-medium rounded-xl text-sm shadow-lg shadow-cyan-500/25 transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            >
              {isLoading ? (
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Signing In...</span>
                </div>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          <div className="mt-6 pt-6 border-t border-slate-800 text-center">
            <p className="text-xs text-slate-400">
              New to Intelligence OS?{" "}
              <Link
                href="/register"
                className="text-cyan-400 hover:text-cyan-300 font-medium transition-colors"
              >
                Register an Organization
              </Link>
            </p>
          </div>
        </div>

        {/* Security badge */}
        <div className="mt-8 flex items-center justify-center gap-2 text-xs text-slate-500">
          <ShieldCheck className="w-4 h-4 text-emerald-500" />
          <span>Strict Multi-Tenant Cryptographic Isolation</span>
        </div>
      </div>
    </div>
  );
}
