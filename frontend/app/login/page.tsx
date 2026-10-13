"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { ArrowRight, Lock, Mail } from "lucide-react";
import { AuthLayout } from "@/components/auth-layout";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, IconInput } from "@/components/ui/field";
import { getErrorMessage } from "@/lib/utils";

export default function LoginPage() {
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
    } catch (err: unknown) {
      setIsLoading(false);
      setError(
        getErrorMessage(err) ||
          "Login failed or request timed out. Please verify your credentials and ensure the backend is running."
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthLayout
      title="Sign in"
      description="Access your organization's isolated document store and chat workspace."
      footer={
        <>
          New to Intelligence OS?{" "}
          <Link
            href="/register"
            className="font-medium text-accent-strong underline-offset-4 transition-colors hover:text-fg hover:underline"
          >
            Register an Organization
          </Link>
        </>
      }
    >
      {error && (
        <Alert tone="danger" onDismiss={() => setError(null)} className="mb-5">
          {error}
        </Alert>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <Field label="Work email" htmlFor="login-email">
          <IconInput
            id="login-email"
            icon={Mail}
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              if (error) setError(null);
            }}
            placeholder="name@company.com"
          />
        </Field>

        <Field label="Password" htmlFor="login-password">
          <IconInput
            id="login-password"
            icon={Lock}
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              if (error) setError(null);
            }}
            placeholder="••••••••••••"
          />
        </Field>

        <Button
          type="submit"
          variant="primary"
          size="lg"
          disabled={isLoading}
          loading={isLoading}
          className="mt-2 w-full"
        >
          {isLoading ? (
            "Signing in…"
          ) : (
            <>
              Sign in
              <ArrowRight />
            </>
          )}
        </Button>
      </form>
    </AuthLayout>
  );
}
