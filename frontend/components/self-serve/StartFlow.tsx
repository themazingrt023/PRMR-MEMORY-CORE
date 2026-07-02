"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

type SafeAccount = {
  name: string;
  email: string;
  plan: string;
  verificationStatus: "unverified" | "verified";
  createdLocally: boolean;
  clientId?: string;
  vaultId?: string;
  namespace?: string;
};

export function StartFlow() {
  const router = useRouter();
  const [account, setAccount] = useState<SafeAccount | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    const raw = sessionStorage.getItem("prmr-v092-safe-account");
    setAccount(raw ? (JSON.parse(raw) as SafeAccount) : null);
  }, []);

  function verifyLocally() {
    if (!account) return;
    const next = { ...account, verificationStatus: "verified" as const };
    sessionStorage.setItem("prmr-v092-safe-account", JSON.stringify(next));
    setAccount(next);
    setMessage("Local MVP verification recorded. No email was sent.");
  }

  function activate() {
    if (!account || account.verificationStatus !== "verified") return;
    if (account.plan !== "free") {
      setMessage(
        account.plan === "builder"
          ? "Builder billing is not connected. Choose Free to continue in the local MVP."
          : "Controlled Pilot requires manual approval. Choose Free to continue in the local MVP."
      );
      return;
    }
    const suffix = crypto.randomUUID().replaceAll("-", "").slice(0, 10);
    const next = {
      ...account,
      clientId: `client_ss_${suffix}`,
      vaultId: `vault_ss_${suffix}`,
      namespace: "default"
    };
    sessionStorage.setItem("prmr-v092-safe-account", JSON.stringify(next));
    router.push("/dashboard");
  }

  if (!account) {
    return (
      <div className="mt-10 border border-white/10 p-6 text-mist/62">
        No local MVP account is present. <a className="text-white underline" href="/signup">Start at signup</a>.
      </div>
    );
  }

  return (
    <div className="mt-10 grid gap-4 lg:grid-cols-3">
      <Step number="01" title="Account" state="Complete">
        <p>{account.name}</p>
        <p>{account.email}</p>
      </Step>
      <Step number="02" title="Verify" state={account.verificationStatus}>
        <p>This action changes local test state only. It does not send an email.</p>
        {account.verificationStatus === "unverified" ? (
          <button className="ghost-button mt-5 px-4 py-3 font-mono text-xs uppercase" onClick={verifyLocally} type="button">
            Verify in local MVP
          </button>
        ) : null}
      </Step>
      <Step number="03" title="Plan" state={account.plan}>
        <p>Free activates locally. Builder billing is not live. Controlled Pilot remains manually approved.</p>
        <button
          className="silver-button mt-5 px-4 py-3 font-mono text-xs uppercase disabled:opacity-35"
          disabled={account.verificationStatus !== "verified"}
          onClick={activate}
          type="button"
        >
          Enter dashboard
        </button>
      </Step>
      <p aria-live="polite" className="text-sm text-mist/54 lg:col-span-3">{message}</p>
    </div>
  );
}

function Step({
  number,
  title,
  state,
  children
}: {
  number: string;
  title: string;
  state: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border border-white/10 bg-white/[0.015] p-6">
      <div className="flex items-center justify-between font-mono text-[10px] uppercase tracking-[0.16em] text-mist/42">
        <span>{number} / {title}</span>
        <span>{state}</span>
      </div>
      <div className="mt-6 space-y-2 text-sm leading-6 text-mist/62">{children}</div>
    </section>
  );
}
