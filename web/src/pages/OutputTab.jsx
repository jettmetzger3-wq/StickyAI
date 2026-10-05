import { api, fileUrl, fmtBytes, fmtTime } from "../api.js";
import { Button, Card, CopyButton } from "../ui.jsx";

export default function OutputTab({ d, slug }) {
  const yt = d.youtube;
  const f = d.final || {};
  const dl = (kind) => `/api/projects/${encodeURIComponent(slug)}/download/${kind}`;
  if (!f.video)
    return (
      <Card>
        <p className="text-sm text-stone-500 dark:text-zinc-400">The final video isn't made yet. It appears here when the Render and Mix steps finish.</p>
      </Card>
    );
  const tags = (yt?.tags || []).join(", ");
  return (
    <div className="space-y-4">
      <Card
        title="Video"
        actions={
          <>
            <a href={dl("video")}>
              <Button variant="primary">⬇ Full quality ({fmtBytes(f.video.size)})</Button>
            </a>
            {f.share && (
              <a href={dl("share")}>
                <Button>⬇ Share copy ({fmtBytes(f.share.size)})</Button>
              </a>
            )}
          </>
        }
      >
        <video src={fileUrl(slug, f.video.path, f.video.v)} controls className="w-full rounded-xl bg-black" poster={f.thumbnail ? fileUrl(slug, f.thumbnail.path, f.thumbnail.v) : undefined} />
      </Card>

      {yt && (
        <>
          <Card title="Titles (pick one)">
            <div className="space-y-2">
              {yt.titles.map((t, i) => (
                <div key={i} className="flex items-center justify-between gap-3 rounded-lg bg-stone-100 px-3 py-2 dark:bg-zinc-800">
                  <span className="font-medium">{t}</span>
                  <span className="flex items-center gap-2">
                    <span className={t.length > 70 ? "text-xs text-red-600" : "text-xs text-stone-400"}>{t.length}/100</span>
                    <CopyButton text={t} />
                  </span>
                </div>
              ))}
            </div>
          </Card>
          <Card title="Description" actions={<CopyButton text={yt.description} label="Copy description" />}>
            <textarea readOnly className="mono h-72 w-full text-xs" value={yt.description} />
            <p className="mt-2 text-xs text-stone-500 dark:text-zinc-400">
              Chapters use the real scene start times and start at 0:00, so YouTube turns them into chapters automatically.
            </p>
          </Card>
          <div className="grid gap-4 md:grid-cols-2">
            <Card title="Tags" actions={<CopyButton text={tags} label="Copy tags" />}>
              <div className="flex flex-wrap gap-1.5">
                {yt.tags.map((t) => (
                  <span key={t} className="rounded-full bg-stone-100 px-2 py-0.5 text-xs dark:bg-zinc-800">
                    {t}
                  </span>
                ))}
              </div>
              {yt.hashtags?.length > 0 && <div className="mt-2 text-sm text-sky-700 dark:text-sky-400">{yt.hashtags.join(" ")}</div>}
            </Card>
            <Card title="Chapters">
              <ul className="space-y-0.5 text-sm">
                {yt.chapters.map((c, i) => (
                  <li key={i}>
                    <span className="mr-2 font-mono text-stone-500">{c.time}</span>
                    {c.title}
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-stone-500">Video length {fmtTime(yt.duration)}</p>
            </Card>
          </div>
          {f.thumbnail && (
            <Card title="Thumbnail" actions={<a href={dl("thumbnail")}><Button>⬇ Download</Button></a>}>
              <img src={fileUrl(slug, f.thumbnail.path, f.thumbnail.v)} className="w-full max-w-2xl rounded-xl" alt="" />
            </Card>
          )}
          {yt.question && (
            <Card title="Pinned comment idea" actions={<CopyButton text={yt.question} />}>
              <p className="text-sm">{yt.question}</p>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
