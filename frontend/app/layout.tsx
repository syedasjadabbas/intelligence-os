import type { Metadata } from "next";
import "@/app/globals.css";
import { AuthProvider } from "@/lib/auth-context";

export const metadata: Metadata = {
  title: "Intelligence OS | Enterprise Contextual RAG",
  description:
    "Private enterprise intelligence platform with multi-tenant hybrid search, grounded answers, and strict citation tracing.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark h-full">
      <body className="min-h-full flex flex-col bg-[#090d16] text-slate-100 antialiased selection:bg-cyan-500/30 selection:text-cyan-200">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
