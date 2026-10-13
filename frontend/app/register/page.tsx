"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { ArrowRight, Building2, Hash, Lock, Mail } from "lucide-react";
import { AuthLayout } from "@/components/auth-layout";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, IconInput } from "@/components/ui/field";
import { getErrorMessage } from "@/lib/utils";

export default function RegisterPage() {
  const router = useRouter();
  const { register } = useAuth();
  const [orgName, setOrgName] = useState("");
  const [orgSlug, setOrgSlug] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [adminPassword, setAdminPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Auto-generate slug as organization name is typed
  const handleOrgNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const name = e.target.value;
    setOrgName(name);
    const slug = name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
    setOrgSlug(slug);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await register({
        org_name: orgName,
        org_slug: orgSlug,
        admin_email: adminEmail,
        admin_password: adminPassword,
      });
      router.push("/");
    } catch (err: unknown) {
      setError(
        getErrorMessage(err) || "Failed to register organization. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout
      title="Register organization"
      description="Create an isolated tenant workspace with its own document store, indexes and admin account."
      footer={
        <>
          Already registered?{" "}
          <Link
            href="/login"
            className="font-medium text-accent-strong underline-offset-4 transition-colors hover:text-fg hover:underline"
          >
            Sign In Instead
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
        <Field label="Organization name" htmlFor="reg-org-name">
          <IconInput
            id="reg-org-name"
            icon={Building2}
            type="text"
            required
            autoComplete="organization"
            value={orgName}
            onChange={handleOrgNameChange}
            placeholder="Acme Corporation"
          />
        </Field>

        <Field
          label="Organization slug"
          htmlFor="reg-org-slug"
          hint="Tenant identifier. Generated from the name — edit if needed."
        >
          <IconInput
            id="reg-org-slug"
            icon={Hash}
            type="text"
            required
            value={orgSlug}
            onChange={(e) => setOrgSlug(e.target.value)}
            placeholder="acme-corporation"
            className="font-mono text-[13px]"
          />
        </Field>

        <div className="h-px bg-line" />

        <Field label="Admin work email" htmlFor="reg-admin-email">
          <IconInput
            id="reg-admin-email"
            icon={Mail}
            type="email"
            required
            autoComplete="email"
            value={adminEmail}
            onChange={(e) => setAdminEmail(e.target.value)}
            placeholder="name@company.com"
          />
        </Field>

        <Field label="Admin password" htmlFor="reg-admin-password">
          <IconInput
            id="reg-admin-password"
            icon={Lock}
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            value={adminPassword}
            onChange={(e) => setAdminPassword(e.target.value)}
            placeholder="Minimum 8 characters"
          />
        </Field>

        <Button
          type="submit"
          variant="primary"
          size="lg"
          disabled={loading}
          loading={loading}
          className="mt-2 w-full"
        >
          {loading ? (
            "Creating organization…"
          ) : (
            <>
              Create Organization
              <ArrowRight />
            </>
          )}
        </Button>
      </form>
    </AuthLayout>
  );
}
