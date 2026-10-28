"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import Link from "next/link";
import { PageHeader, Panel, Empty } from "@/components/app/ui";

export default function Datasets() {
  const [file, setFile] = useState<File | null>(null);
  const [res, setRes] = useState<any>(null);
  const [models, setModels] = useState<any[]>([]);
  const [model, setModel] = useState<any>(null);
  const [coachModel, setCoachModel] = useState<any>(null);
  const [imports, setImports] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [training, setTraining] = useState(false);
  const [syncingAccounts, setSyncingAccounts] = useState(false);
  const [dataSummary, setDataSummary] = useState<any>(null);
  const [err, setErr] = useState("");
  const [trainMsg, setTrainMsg] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const loadModels = () => {
    api.modelStatus().then(setModels).catch(() => {});
    api.modelDetail().then(setModel).catch(() => {});
    api.coachStatus().then(setCoachModel).catch(() => setCoachModel({ available: false }));
    api.datasetImports().then(setImports).catch(() => {});
  };
  useEffect(() => { loadModels(); api.analyticsSummary().then(setDataSummary).catch(() => {}); }, []);

  const submit = async () => {
    if (!file) return;
    setLoading(true);
    setErr("");
    setRes(null);
    try {
      setRes(await api.importCsv(file));
      loadModels();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  const train = async () => {
    setTraining(true);
    setErr("");
    setTrainMsg("");
    try {
      const r: any = await api.train();
      const viewMessage = r.status === "trained"
        ? `View model trained on ${r.n_samples} posts. R² ${r.metrics?.r2?.toFixed(3) ?? "—"}, MAE ${Math.round(r.metrics?.mae ?? 0).toLocaleString()}.`
        : r.message || "View-model training did not run.";
      const coachMessage = r.growth_coach?.status === "trained"
        ? ` Growth Coach trained on ${r.growth_coach.n_samples} posts.`
        : r.growth_coach?.message
          ? ` Growth Coach: ${r.growth_coach.message}`
          : "";
      setTrainMsg(viewMessage + coachMessage);
      loadModels();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setTraining(false);
    }
  };

  const syncConnectedData = async () => {
    setSyncingAccounts(true);
    setErr("");
    setTrainMsg("");
    try {
      const accounts = await api.socialAccounts();
      const linked = accounts.filter((account: any) =>
        account.mode === "oauth" &&
        account.status === "connected" &&
        ["instagram", "youtube"].includes(account.platform)
      );
      if (linked.length === 0) {
        setTrainMsg("No live-linked Instagram or YouTube account found. Connect the accounts in Accounts first; CSV import remains optional.");
        return;
      }
      const results = await Promise.allSettled(linked.map((account: any) => api.syncSocial(account.id)));
      const liveCount = results.filter((result: any) =>
        result.status === "fulfilled" &&
        String(result.value?.sync_source || "").startsWith("live ")
      ).length;
      const notes = results
        .map((result: any) => result.status === "fulfilled" ? result.value?.sync_note : result.reason?.message)
        .filter(Boolean);
      const freshModel = await api.modelDetail().catch(() => ({ available: false }));
      const freshCoach = await api.coachStatus().catch(() => ({ available: false }));
      setModel(freshModel);
      setCoachModel(freshCoach);
      const summary = await api.analyticsSummary().catch(() => null);
      if (summary) setDataSummary(summary);
      loadModels();
      setTrainMsg(
        `Synced ${liveCount} of ${linked.length} live-linked account(s). ` +
        (freshModel.available
          ? `View model ${freshModel.version} is ready with ${freshModel.n_samples} real-view samples. `
          : `The view model is not ready: ${summary?.historical_posts ?? 0} posts are recorded; at least 10 real-view samples are required. `) +
        (freshCoach.available
          ? `Growth Coach ${freshCoach.version} is ready with ${freshCoach.n_samples} samples.`
          : `Growth Coach needs ${Math.max(0, Number(freshCoach.required ?? 10) - Number(freshCoach.n_samples_available ?? 0))} more real-view posts.`) +
        (notes.length ? ` Provider note: ${notes[0]}` : "")
      );
    } catch (e: any) {
      setErr(e.message || "Could not sync connected account data.");
    } finally {
      setSyncingAccounts(false);
    }
  };

  const downloadTemplate = async () => {
    setErr("");
    try {
      const blob = await api.datasetTemplate();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "socialboost-template.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setErr(e.message);
    }
  };

  return (
    <>
      <PageHeader
        eyebrow="Datasets"
        title={<>Import real performance.</>}
        description="SocialBoost can pull posts and real public metrics from connected Instagram and YouTube accounts. CSV import is optional, useful for older history that the providers do not expose."
        actions={
          <div className="flex flex-wrap gap-2">
            <button className="btn btn-ghost" onClick={syncConnectedData} disabled={syncingAccounts || training}>{syncingAccounts ? "Syncing accounts…" : "Sync connected data"}</button>
            <button className="btn btn-signal" onClick={train} disabled={training || syncingAccounts}>{training ? "Training…" : "Train models"}</button>
          </div>
        }
      />

      {(trainMsg || err) && (
        <div className={`mb-4 border px-4 py-3 text-[12px] ${err ? "border-[var(--red)] text-[var(--red)]" : "border-[var(--sage-deep)] bg-[var(--sage)] text-[#3E4C34]"}`}>
          {err || trainMsg}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[1.2fr_1fr] gap-4">
        <div className="space-y-4">
          <Panel title="Connected data first">
            <p className="text-[12px] leading-relaxed text-[var(--muted)]">Use the connected accounts to fetch the latest available posts into the same training and analytics dataset. Provider APIs do not expose every historical/private metric, so missing metrics stay blank rather than becoming invented zeroes.</p>
            <div className="grid grid-cols-2 gap-3 mt-4">
              <div className="border border-[var(--hairline)] p-3">
                <p className="mono text-[8px] uppercase tracking-[0.08em] text-[var(--muted)]">Stored posts</p>
                <p className="font-display text-[23px] font-semibold mt-1">{dataSummary?.historical_posts ?? "—"}</p>
              </div>
              <div className="border border-[var(--hairline)] p-3">
                <p className="mono text-[8px] uppercase tracking-[0.08em] text-[var(--muted)]">Model samples</p>
                <p className="font-display text-[23px] font-semibold mt-1">{model?.available ? model.n_samples : "—"}</p>
              </div>
            </div>
            <button className="btn btn-signal mt-4" onClick={syncConnectedData} disabled={syncingAccounts || training}>{syncingAccounts ? "Fetching Instagram + YouTube…" : "Fetch account data & refresh model"}</button>
          </Panel>

          <Panel title="Optional CSV history" aside={<button className="mono text-[9px] uppercase tracking-[0.1em] text-[var(--signal)]" onClick={downloadTemplate}>Download template</button>}>
            <div
              onClick={() => inputRef.current?.click()}
              className="border border-dashed border-[var(--hairline-strong)] px-6 py-10 text-center cursor-pointer hover:border-[var(--ink)]"
            >
              <p className="text-[13px] font-medium">{file ? file.name : "Select a CSV file"}</p>
              <p className="mono text-[9px] uppercase tracking-[0.1em] text-[var(--muted)] mt-2">platform, published_at, views required</p>
              <input ref={inputRef} type="file" accept=".csv" className="hidden" onChange={(e) => setFile(e.target.files?.[0] || null)} />
            </div>
            <div className="mt-4 flex gap-2">
              <button className="btn btn-signal" onClick={submit} disabled={!file || loading}>{loading ? "Importing…" : "Import rows"}</button>
              {file && <button className="btn btn-ghost" onClick={() => { setFile(null); setRes(null); }}>Clear</button>}
            </div>

            {res && (
              <div className="mt-5 border-t border-[var(--hairline)] pt-4">
                <p className="label mb-2">Last import</p>
                <dl>
                  <div className="kv"><dt>Rows in file</dt><dd>{res.total_rows_in_file}</dd></div>
                  <div className="kv"><dt>Imported</dt><dd className="text-[var(--sage-ink)]">{res.rows_imported}</dd></div>
                  <div className="kv"><dt>Rejected</dt><dd className={res.rows_rejected ? "text-[var(--signal)]" : ""}>{res.rows_rejected}</dd></div>
                  <div className="kv"><dt>Duplicates skipped</dt><dd>{res.rows_duplicate ?? 0}</dd></div>
                </dl>
                {res.warnings?.length > 0 && (
                  <ul className="mt-3 space-y-1.5">
                    {res.warnings.map((w: string, i: number) => (
                      <li key={i} className="text-[11px] text-[var(--muted)] border-l border-[var(--signal)] pl-2.5">{w}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            <p className="mt-5 mono text-[9px] leading-relaxed text-[var(--muted)]">
              Required columns: platform (instagram / youtube), published_at, views. A <span className="text-[var(--ink)]">post_id</span> column is
              optional but lets re-imports skip rows that are already stored.
            </p>
          </Panel>

          <Panel title={`Import history · ${imports.length}`} flush>
            {imports.length === 0 ? (
              <div className="p-5"><p className="text-[12px] text-[var(--muted)]">No files imported yet.</p></div>
            ) : (
              <ul>
                {imports.map((r) => (
                  <li key={r.id} className="px-5 py-3 border-b border-[var(--hairline)] last:border-b-0">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-[12px] truncate">{r.filename}</p>
                      <span className="mono text-[9px] text-[var(--muted)] shrink-0">{new Date(r.created_at).toLocaleDateString()}</span>
                    </div>
                    <p className="mono text-[8.5px] uppercase tracking-[0.08em] text-[var(--muted)] mt-1">
                      {r.rows_imported} imported · {r.rows_rejected} rejected
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>

        <div className="space-y-4">
          <Panel title="Active model" aside={model ? <span className={`tag ${model.available ? "tag-sage" : ""}`}>{model.available ? "ready" : "none"}</span> : undefined}>
            <div className="border-l-2 border-[var(--cobalt)] pl-3 mb-4">
              <p className="text-[11.5px] font-semibold">Random Forest models</p>
              <p className="text-[10.5px] text-[var(--muted)] leading-relaxed mt-1">RandomForestRegressor estimates views; RandomForestClassifier classifies above/below the workspace median. Inputs include duration, caption/title length, hashtags, publish hour/day and platform. They are trained only on this workspace's posts with actual view counts.</p>
            </div>
            {model?.available ? (
              <dl>
                <div className="kv"><dt>Version</dt><dd>{model.version}</dd></div>
                <div className="kv"><dt>Samples</dt><dd>{model.n_samples}</dd></div>
                <div className="kv"><dt>R²</dt><dd>{model.metrics?.r2 != null ? model.metrics.r2.toFixed(3) : "—"}</dd></div>
                <div className="kv"><dt>MAE</dt><dd>{model.metrics?.mae != null ? Math.round(model.metrics.mae).toLocaleString() : "—"}</dd></div>
                <div className="kv"><dt>Median views</dt><dd>{model.views_percentiles?.p50 != null ? Math.round(model.views_percentiles.p50).toLocaleString() : "—"}</dd></div>
              </dl>
            ) : (
              <p className="text-[12px] leading-relaxed text-[var(--muted)]">
                No model is trained for this workspace. Predictions return no score until one exists.
              </p>
            )}
            <div className="flex flex-wrap gap-2 mt-4">
              <Link href="/app/predictions" className="btn btn-ghost btn-sm">Open predictions</Link>
            </div>
          </Panel>

          <Panel title="Growth Coach · Content-aware model" aside={<span className={`tag ${coachModel?.available ? "tag-sage" : ""}`}>{coachModel?.available ? "ready" : "waiting for data"}</span>}>
            <p className="text-[11px] leading-relaxed text-[var(--muted)]">HistGradientBoostingRegressor predicts a personal growth index with low/high quantile ranges. TF-IDF + TruncatedSVD encodes caption/title text; StandardScaler normalises numeric features. Chronological TimeSeriesSplit checks out-of-sample ranking when enough history exists.</p>
            {coachModel?.available ? (
              <dl className="mt-3">
                <div className="kv"><dt>Version</dt><dd>{coachModel.version || "—"}</dd></div>
                <div className="kv"><dt>Training posts</dt><dd>{coachModel.n_samples ?? "—"}</dd></div>
                <div className="kv"><dt>Validation folds</dt><dd>{coachModel.cross_validation?.folds ?? 0}</dd></div>
                <div className="kv"><dt>Rank correlation</dt><dd>{coachModel.cross_validation?.rank_correlation == null ? "—" : Number(coachModel.cross_validation.rank_correlation).toFixed(3)}</dd></div>
              </dl>
            ) : (
              <p className="mono text-[9px] text-[var(--muted)] mt-3">{coachModel?.note || `At least ${coachModel?.required ?? 10} posts with real view counts are needed. Sync connected accounts to train automatically.`}</p>
            )}
            <button className="btn btn-ghost btn-sm mt-3" onClick={train} disabled={training || syncingAccounts}>{training ? "Training…" : "Train both models"}</button>
          </Panel>

          <Panel title="Model versions">
            {models.length === 0 ? (
              <p className="text-[12px] text-[var(--muted)]">No models trained yet.</p>
            ) : (
              <ul className="space-y-3">
                {models.map((m, i) => (
                  <li key={i} className="border border-[var(--hairline)] p-3">
                    <div className="flex items-center justify-between">
                      <span className="text-[12px] font-medium">{m.name.replace(/_/g, " ")}</span>
                      <span className="tag">{m.version}</span>
                    </div>
                    <p className="mono text-[8.5px] text-[var(--muted)] mt-1">{new Date(m.created_at).toLocaleString()}</p>
                    {m.metrics && (
                      <dl className="mt-2">
                        {Object.entries(m.metrics).slice(0, 5).map(([k, v]) => (
                          <div key={k} className="flex justify-between text-[10.5px] py-1 border-t border-[var(--hairline)]">
                            <dt className="text-[var(--muted)] capitalize">{k.replace(/_/g, " ")}</dt>
                            <dd className="mono">{typeof v === "number" ? v.toFixed(3) : String(v)}</dd>
                          </div>
                        ))}
                      </dl>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel title="Minimum to train">
            <p className="text-[12px] leading-relaxed text-[var(--ink-2)]">
              At least 10 rows with views are required. Below that the app refuses to train and says why, rather than producing a meaningless score.
            </p>
          </Panel>
        </div>
      </div>
    </>
  );
}
