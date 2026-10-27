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
  const [imports, setImports] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [training, setTraining] = useState(false);
  const [err, setErr] = useState("");
  const [trainMsg, setTrainMsg] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const loadModels = () => {
    api.modelStatus().then(setModels).catch(() => {});
    api.modelDetail().then(setModel).catch(() => {});
    api.datasetImports().then(setImports).catch(() => {});
  };
  useEffect(() => { loadModels(); }, []);

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
      if (r.status === "trained") {
        setTrainMsg(`Trained on ${r.n_samples} posts. R² ${r.metrics?.r2?.toFixed(3) ?? "—"}, MAE ${Math.round(r.metrics?.mae ?? 0).toLocaleString()}.`);
      } else {
        setTrainMsg(r.message || "Training did not run.");
      }
      loadModels();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setTraining(false);
    }
  };

  const downloadTemplate = async () => {
    setErr("");
    try {
      const blob = await api.datasetTemplate();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "signal-studio-template.csv";
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
        description="Historical posts train the prediction models. Every imported row is attributed to a platform and counted in analytics."
        actions={<button className="btn btn-signal" onClick={train} disabled={training}>{training ? "Training…" : "Train models"}</button>}
      />

      {(trainMsg || err) && (
        <div className={`mb-4 border px-4 py-3 text-[12px] ${err ? "border-[var(--red)] text-[var(--red)]" : "border-[var(--sage-deep)] bg-[var(--sage)] text-[#3E4C34]"}`}>
          {err || trainMsg}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[1.2fr_1fr] gap-4">
        <div className="space-y-4">
          <Panel title="Import CSV" aside={<button className="mono text-[9px] uppercase tracking-[0.1em] text-[var(--signal)]" onClick={downloadTemplate}>Download template</button>}>
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
